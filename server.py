#!/usr/bin/env python3
"""Serwer aplikacji turniejowej.

  /admin  - panel organizatora (za PIN-em)
  /join   - zapis zawodnika z telefonu, jego mecze i wyniki

Uruchomienie:  python server.py
Zmienne środowiskowe (opcjonalne): PORT (8000), ADMIN_PIN (losowy 6 cyfr), DATA_FILE.
Tylko biblioteka standardowa Pythona.
"""
import copy
import hmac
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import schedule

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
DATA_FILE = os.environ.get('DATA_FILE', os.path.join(BASE_DIR, 'data.json'))
PORT = int(os.environ.get('PORT', '8000'))
ADMIN_PIN = os.environ.get('ADMIN_PIN') or '{:06d}'.format(secrets.randbelow(1000000))

UNRANKED = 999            # ranking zawodnika spoza klasyfikacji (najniższy)
MAX_PLACE = UNRANKED - 1  # miejsca z klasyfikacji muszą być wyższe niż UNRANKED
THRESHOLD = 5             # trafienia w walce w puli
MAX_BOARDS = 20
MAX_BODY = 2 * 1024 * 1024
MAX_FENCERS = 2000
ALLOWED_RANKING_HOSTS = {'pzszerm.pl', 'www.pzszerm.pl'}
PIN_FAIL_LIMIT = 10
PIN_FAIL_WINDOW = 60.0

STATIC_FILES = {
    '/admin': ('admin.html', 'text/html; charset=utf-8'),
    '/join': ('join.html', 'text/html; charset=utf-8'),
    '/static/qrcode.js': ('qrcode.js', 'application/javascript; charset=utf-8'),
}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------- normalizacja nazwisk ----------

_CTRL = re.compile(r'[\x00-\x1f\x7f]')


def clean(value):
    if not isinstance(value, str):
        return ''
    return ' '.join(_CTRL.sub(' ', value).split())


def fold(text):
    text = text.replace('ł', 'l').replace('Ł', 'L')
    text = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in text if not unicodedata.combining(c)).casefold()


def name_key(*parts):
    """Klucz nazwiska: bez polskich znaków i wielkości liter, kolejność wyrazów bez znaczenia."""
    return ' '.join(sorted(re.findall(r'\w+', fold(' '.join(parts)))))


def new_id():
    return uuid.uuid4().hex[:12]


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


# ---------- import klasyfikacji PZSzerm ----------

class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._stack = []
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self._stack.append([])
        elif tag == 'tr' and self._stack:
            self._stack[-1].append([])
        elif tag in ('td', 'th') and self._stack and self._stack[-1]:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._cell is not None and self._stack and self._stack[-1]:
            self._stack[-1][-1].append(' '.join(''.join(self._cell).split()))
            self._cell = None
        elif tag == 'table' and self._stack:
            self.tables.append(self._stack.pop())

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def _entries_from_rows(rows):
    """rows: lista wierszy (lista komórek). Zwraca wpisy klasyfikacji albo [] gdy brak nagłówka 'Miejsce'."""
    header_index = None
    for i, row in enumerate(rows):
        if any(fold(cell).startswith('miejsce') for cell in row):
            header_index = i
            break
    if header_index is None:
        return []
    header = [fold(cell) for cell in rows[header_index]]
    place_col = next(i for i, h in enumerate(header) if h.startswith('miejsce'))
    name_col = next((i for i, h in enumerate(header) if 'nazwisko' in h), place_col + 1)
    club_col = next((i for i, h in enumerate(header) if h == 'klub'), None)

    entries = []
    for row in rows[header_index + 1:]:
        if len(row) <= max(place_col, name_col):
            continue
        match = re.match(r'\s*(\d+)', row[place_col])
        name = clean(row[name_col])
        key = name_key(name)
        if not match or not key:
            continue
        place = int(match.group(1))
        if not 1 <= place <= MAX_PLACE:
            continue
        club = clean(row[club_col]) if club_col is not None and club_col < len(row) else ''
        entries.append({'place': place, 'name': name, 'club': club, 'key': key})
    return entries


def parse_ranking_html(html):
    parser = _TableParser()
    parser.feed(html)
    for table in parser.tables:
        entries = _entries_from_rows(table)
        if entries:
            return entries
    return []


def parse_ranking_text(text):
    """Tabela skopiowana ze strony (komórki oddzielone tabulatorami)."""
    rows = [line.split('\t') for line in text.splitlines() if line.strip()]
    entries = _entries_from_rows(rows)
    if entries:
        return entries
    # brak nagłówka w wklejonym tekście: zakładamy kolejność Miejsce, Imię i Nazwisko, Rocznik, Klub
    entries = []
    for row in rows:
        if len(row) < 2:
            continue
        match = re.match(r'\s*(\d+)', row[0])
        name = clean(row[1])
        key = name_key(name)
        if not match or not key or not 1 <= int(match.group(1)) <= MAX_PLACE:
            continue
        club = clean(row[3]) if len(row) > 3 else ''
        entries.append({'place': int(match.group(1)), 'name': name, 'club': club, 'key': key})
    return entries


def check_ranking_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_RANKING_HOSTS \
            or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ApiError(400, 'Dozwolone są tylko adresy https://pzszerm.pl/...')


class _HostCheckingRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_ranking_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


BLOCKED_MESSAGE = (
    'Strona PZSzerm nie oddała tabeli serwerowi (wymaga przeglądarki z JavaScript i cookies). '
    'Serwer nie obchodzi tej weryfikacji. Otwórz link w przeglądarce, skopiuj całą tabelę '
    'klasyfikacji (od nagłówka „Miejsce”) i wklej ją w polu poniżej.'
)


def fetch_ranking(url):
    check_ranking_url(url)
    request = urllib.request.Request(url, headers={
        'User-Agent': 'TurniejApp/1.0 (narzedzie organizatora)',
        'Accept': 'text/html',
    })
    opener = urllib.request.build_opener(_HostCheckingRedirect)
    try:
        with opener.open(request, timeout=15) as response:
            body = response.read(MAX_BODY + 1)
    except urllib.error.HTTPError as e:
        raise ApiError(502, 'PZSzerm odpowiedział błędem {}.'.format(e.code))
    except (urllib.error.URLError, OSError) as e:
        raise ApiError(502, 'Nie udało się pobrać strony: {}'.format(getattr(e, 'reason', e)))
    if len(body) > MAX_BODY:
        raise ApiError(502, 'Odpowiedź PZSzerm jest zbyt duża.')
    entries = parse_ranking_html(body.decode('utf-8', errors='replace'))
    if not entries:
        raise ApiError(422, BLOCKED_MESSAGE)
    return entries


# ---------- walki ----------

def validate_scores(sa, sb):
    """None albo liczby 0..THRESHOLD; pełny wynik: zwycięzca dokładnie THRESHOLD, przegrany mniej."""
    for s in (sa, sb):
        if s is not None and (not is_int(s) or not 0 <= s <= THRESHOLD):
            raise ApiError(400, 'Wynik musi być liczbą całkowitą od 0 do {}.'.format(THRESHOLD))
    if sa is not None and sb is not None and (sa == sb or max(sa, sb) != THRESHOLD):
        raise ApiError(400, 'Zwycięzca musi mieć dokładnie {} trafień.'.format(THRESHOLD))


def has_result(bout):
    return bout['sa'] is not None and bout['sb'] is not None


def default_data():
    return {
        'registrationOpen': True,
        'ranking': {'entries': [], 'source': '', 'importedAt': None},
        'fencers': [],
        'pools': {'poolSize': 7, 'advanceCount': None, 'groups': []},
    }


class Store:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.data = self._load()

    def _load(self):
        data = default_data()
        try:
            with open(self.path, encoding='utf-8') as f:
                loaded = json.load(f)
        except FileNotFoundError:
            return data
        except (OSError, ValueError) as e:
            sys.exit('Nie można odczytać {} ({}). Napraw lub przenieś plik i uruchom ponownie.'.format(self.path, e))
        if isinstance(loaded, dict):
            for key in data:
                if key in loaded:
                    data[key] = loaded[key]
        self._upgrade(data)
        return data

    @staticmethod
    def _upgrade(data):
        """Uzupełnia pola, których nie było w starszych plikach danych."""
        for g in data['pools'].get('groups', []):
            g.setdefault('boards', 1)
            g.setdefault('boardsUsed', 1)
            g.setdefault('closed', False)
            for i, b in enumerate(g.get('bouts', [])):
                b.setdefault('id', new_id())
                b.setdefault('by', None)
                b.setdefault('disputed', False)
                b.setdefault('turn', i + 1)
                b.setdefault('slot', 1)
                b.setdefault('ref', None)
                b.setdefault('refManual', False)

    def _save(self):
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    # --- pomocnicze ---

    def _pools_locked(self):
        return bool(self.data['pools'].get('groups'))

    def _require_unlocked(self):
        if self._pools_locked():
            raise ApiError(423, 'Lista zawodników jest zablokowana, bo pule są utworzone.')

    def _used_rankings(self, exclude_id=None):
        return {f['ranking'] for f in self.data['fencers']
                if f['id'] != exclude_id and f['ranking'] != UNRANKED}

    def _check_duplicate(self, key, exclude_id):
        for f in self.data['fencers']:
            if f['id'] != exclude_id and name_key(f['firstName'], f['lastName']) == key:
                raise ApiError(409, 'Taki zawodnik jest już zapisany: {} {} (ranking {}).'.format(
                    f['lastName'], f['firstName'], f['ranking']))

    def _lookup(self, key):
        matches = [e for e in self.data['ranking']['entries'] if e['key'] == key]
        if len(matches) == 1:
            return matches[0], 'pzszerm'
        if len(matches) > 1:
            return None, 'ambiguous'
        return None, 'none'

    def _read_names(self, first, last):
        first, last = clean(first), clean(last)
        if not first:
            raise ApiError(400, 'Podaj imię.')
        if not last:
            raise ApiError(400, 'Podaj nazwisko.')
        if len(first) > 60 or len(last) > 60:
            raise ApiError(400, 'Imię i nazwisko mogą mieć maksymalnie 60 znaków.')
        key = name_key(first, last)
        if not key:
            raise ApiError(400, 'Podaj poprawne imię i nazwisko.')
        return first, last, key

    def _read_club(self, club):
        club = clean(club)
        if len(club) > 80:
            raise ApiError(400, 'Nazwa klubu może mieć maksymalnie 80 znaków.')
        return club

    def _fencer(self, fencer_id):
        return next((f for f in self.data['fencers'] if f['id'] == fencer_id), None)

    def admin_fencers(self):
        return [dict(f) for f in self.data['fencers']]

    # --- zapis zawodnika z telefonu ---

    def register(self, first, last, club):
        with self.lock:
            if not self.data['registrationOpen'] or self._pools_locked():
                raise ApiError(403, 'Zapisy są zamknięte.')
            if len(self.data['fencers']) >= MAX_FENCERS:
                raise ApiError(403, 'Osiągnięto limit zawodników.')
            first, last, key = self._read_names(first, last)
            club = self._read_club(club)
            self._check_duplicate(key, None)

            entry, source = self._lookup(key)
            ranking = UNRANKED
            if entry:
                if entry['place'] in self._used_rankings():
                    source = 'conflict'
                else:
                    ranking = entry['place']
                club = entry['club'] or club

            fencer = {
                'id': new_id(),
                'firstName': first,
                'lastName': last,
                'club': club,
                'country': 'POL',
                'ranking': ranking,
                'rankingSource': source,
                'token': secrets.token_urlsafe(16),
                'createdAt': time.time(),
            }
            self.data['fencers'].append(fencer)
            self._save()
            return fencer

    def find_by_token(self, token):
        if not isinstance(token, str) or not token:
            return None
        with self.lock:
            for f in self.data['fencers']:
                if hmac.compare_digest(f['token'], token):
                    return dict(f)
        return None

    # --- zarządzanie zawodnikami przez organizatora ---

    def _read_manual(self, body, exclude_id):
        first, last, key = self._read_names(body.get('firstName'), body.get('lastName'))
        club = self._read_club(body.get('club'))
        country = clean(body.get('country')).upper() or 'POL'
        if len(country) > 3:
            raise ApiError(400, 'Kraj to kod do 3 liter.')
        ranking = body.get('ranking')
        if not is_int(ranking) or not 1 <= ranking <= 9999:
            raise ApiError(400, 'Ranking musi być liczbą całkowitą od 1 do 9999.')
        self._check_duplicate(key, exclude_id)
        if ranking != UNRANKED:
            for f in self.data['fencers']:
                if f['id'] != exclude_id and f['ranking'] == ranking:
                    raise ApiError(409, 'Ranking {} jest już przypisany do: {} {}.'.format(
                        ranking, f['lastName'], f['firstName']))
        return first, last, club, country, ranking

    def admin_add(self, body):
        with self.lock:
            self._require_unlocked()
            if len(self.data['fencers']) >= MAX_FENCERS:
                raise ApiError(403, 'Osiągnięto limit zawodników.')
            first, last, club, country, ranking = self._read_manual(body, None)
            self.data['fencers'].append({
                'id': new_id(),
                'firstName': first, 'lastName': last, 'club': club, 'country': country,
                'ranking': ranking, 'rankingSource': 'manual',
                'token': secrets.token_urlsafe(16), 'createdAt': time.time(),
            })
            self._save()
            return self.admin_fencers()

    def admin_update(self, fencer_id, body):
        with self.lock:
            self._require_unlocked()
            fencer = self._fencer(fencer_id)
            if not fencer:
                raise ApiError(404, 'Nie ma takiego zawodnika.')
            first, last, club, country, ranking = self._read_manual(body, fencer_id)
            fencer.update({'firstName': first, 'lastName': last, 'club': club,
                           'country': country, 'ranking': ranking, 'rankingSource': 'manual'})
            self._save()
            return self.admin_fencers()

    def admin_delete(self, fencer_id):
        with self.lock:
            self._require_unlocked()
            before = len(self.data['fencers'])
            self.data['fencers'] = [f for f in self.data['fencers'] if f['id'] != fencer_id]
            if len(self.data['fencers']) == before:
                raise ApiError(404, 'Nie ma takiego zawodnika.')
            self._save()
            return self.admin_fencers()

    # --- zapisy otwarte / zamknięte ---

    def set_registration(self, is_open):
        with self.lock:
            if is_open and self._pools_locked():
                raise ApiError(409, 'Pule są utworzone, zapisy nie mogą być otwarte.')
            self.data['registrationOpen'] = bool(is_open)
            self._save()
            return self.data['registrationOpen']

    # --- pule ---

    def _club_keys(self):
        return {f['id']: name_key(f['club']) for f in self.data['fencers']}

    def set_pools(self, state):
        """Tworzy pule (podział zawodników przychodzi z panelu, walki układa serwer) albo je usuwa."""
        with self.lock:
            if not isinstance(state, dict) or not isinstance(state.get('groups'), list):
                raise ApiError(400, 'Nieprawidłowe dane pul.')
            pool_size = state.get('poolSize')
            advance = state.get('advanceCount')
            if not is_int(pool_size) or not 2 <= pool_size <= 500:
                raise ApiError(400, 'Nieprawidłowy rozmiar puli.')
            if advance is not None and (not is_int(advance) or advance < 0):
                raise ApiError(400, 'Nieprawidłowa liczba awansujących.')
            if len(state['groups']) > 500:
                raise ApiError(400, 'Zbyt wiele pul.')
            if state['groups'] and self._pools_locked():
                raise ApiError(409, 'Pule już istnieją. Najpierw je usuń.')

            ids = {f['id'] for f in self.data['fencers']}
            clubs = self._club_keys()
            used = set()
            groups = []
            for g in state['groups']:
                if not isinstance(g, dict) or not isinstance(g.get('fencerIds'), list):
                    raise ApiError(400, 'Nieprawidłowa pula.')
                members = g['fencerIds']
                if len(members) < 2 or any(not isinstance(m, str) or m not in ids or m in used for m in members):
                    raise ApiError(400, 'Pula musi mieć co najmniej dwóch znanych, niepowtarzających się zawodników.')
                used.update(members)
                boards = g.get('boards', 1)
                if not is_int(boards) or not 1 <= boards <= MAX_BOARDS:
                    raise ApiError(400, 'Liczba plansz musi być liczbą od 1 do {}.'.format(MAX_BOARDS))
                bouts, boards_used = schedule.build_bouts(list(members), boards, clubs, new_id)
                groups.append({
                    'name': clean(g.get('name'))[:40] or 'Pula',
                    'fencerIds': list(members),
                    'boards': boards,
                    'boardsUsed': boards_used,
                    'closed': False,
                    'bouts': bouts,
                })
            self.data['pools'] = {'poolSize': pool_size, 'advanceCount': advance, 'groups': groups}
            if groups:
                self.data['registrationOpen'] = False
            self._save()
            return self.data['registrationOpen']

    def set_advance(self, advance):
        with self.lock:
            if advance is not None and (not is_int(advance) or not 0 <= advance <= len(self.data['fencers'])):
                raise ApiError(400, 'Liczba awansujących musi być liczbą od 0 do {}.'.format(len(self.data['fencers'])))
            self.data['pools']['advanceCount'] = advance
            self._save()

    def _find_bout(self, bout_id):
        if isinstance(bout_id, str):
            for g in self.data['pools']['groups']:
                for b in g['bouts']:
                    if b['id'] == bout_id:
                        return g, b
        raise ApiError(404, 'Nie ma takiej walki.')

    def _group(self, index):
        groups = self.data['pools']['groups']
        if not is_int(index) or not 0 <= index < len(groups):
            raise ApiError(404, 'Nie ma takiej puli.')
        return groups[index]

    def admin_set_score(self, bout_id, sa, sb):
        with self.lock:
            _g, bout = self._find_bout(bout_id)
            validate_scores(sa, sb)
            bout['sa'], bout['sb'] = sa, sb
            bout['by'] = 'admin' if (sa is not None or sb is not None) else None
            bout['disputed'] = False
            self._save()

    def admin_set_referee(self, bout_id, referee_id):
        with self.lock:
            _g, bout = self._find_bout(bout_id)
            if referee_id is not None and not self._fencer(referee_id):
                raise ApiError(400, 'Nie ma takiego zawodnika.')
            if referee_id in (bout['a'], bout['b']):
                raise ApiError(400, 'Sędzią nie może być zawodnik walczący w tym meczu.')
            bout['ref'] = referee_id
            bout['refManual'] = True
            self._save()

    def admin_set_boards(self, group_index, boards):
        with self.lock:
            g = self._group(group_index)
            if not is_int(boards) or not 1 <= boards <= MAX_BOARDS:
                raise ApiError(400, 'Liczba plansz musi być liczbą od 1 do {}.'.format(MAX_BOARDS))
            if any(b['sa'] is not None or b['sb'] is not None for b in g['bouts']):
                raise ApiError(409, 'W tej puli są już wpisane wyniki. Zmiana plansz zmieniłaby kolejność walk.')
            bouts, boards_used = schedule.build_bouts(g['fencerIds'], boards, self._club_keys(), new_id)
            g['boards'], g['boardsUsed'], g['bouts'] = boards, boards_used, bouts
            self._save()

    def admin_set_closed(self, group_index, closed):
        with self.lock:
            g = self._group(group_index)
            if not isinstance(closed, bool):
                raise ApiError(400, 'Oczekiwano pola closed (true/false).')
            g['closed'] = closed
            self._save()

    # --- zawodnik: mecze i wyniki z telefonu ---

    def _own_bout(self, token, bout_id):
        me = self.find_by_token(token)
        if not me:
            raise ApiError(404, 'Nie znaleziono zapisu.')
        g, bout = self._find_bout(bout_id)
        if me['id'] not in (bout['a'], bout['b']):
            raise ApiError(403, 'To nie jest Twoja walka.')
        return me, g, bout

    def player_score(self, token, bout_id, mine, theirs):
        with self.lock:
            me, g, bout = self._own_bout(token, bout_id)
            if mine is None or theirs is None:
                raise ApiError(400, 'Podaj oba wyniki.')
            validate_scores(mine, theirs)
            if g['closed']:
                raise ApiError(423, 'Pula jest zamknięta. Wynik poprawi organizator.')
            if bout['disputed']:
                raise ApiError(423, 'Zgłoszono błąd w tym wyniku. Decyduje organizator.')
            if has_result(bout) and bout['by'] != me['id']:
                raise ApiError(409, 'Wynik wpisał już ktoś inny. Jeśli jest błędny, zgłoś błąd.')
            if me['id'] == bout['a']:
                bout['sa'], bout['sb'] = mine, theirs
            else:
                bout['sa'], bout['sb'] = theirs, mine
            bout['by'] = me['id']
            bout['disputed'] = False
            self._save()

    def player_dispute(self, token, bout_id):
        with self.lock:
            me, g, bout = self._own_bout(token, bout_id)
            if g['closed']:
                raise ApiError(423, 'Pula jest zamknięta. Skontaktuj się z organizatorem.')
            opponent = bout['b'] if me['id'] == bout['a'] else bout['a']
            if not has_result(bout) or bout['by'] != opponent:
                raise ApiError(409, 'Błąd można zgłosić tylko do wyniku wpisanego przez przeciwnika.')
            bout['disputed'] = True
            self._save()

    def player_view(self, token):
        with self.lock:
            me = self.find_by_token(token)
            if not me:
                return None
            groups = self.data['pools']['groups']
            offsets = self._board_offsets()
            by_id = {f['id']: f for f in self.data['fencers']}

            def label(fid):
                f = by_id.get(fid)
                return '{} {}'.format(f['lastName'], f['firstName']) if f else '?'

            pool = None
            bouts = []
            refereeing = []
            for gi, g in enumerate(groups):
                if me['id'] in g['fencerIds'] and pool is None:
                    pool = {'name': g['name'], 'closed': g['closed']}
                my_turns = {b['turn'] for b in g['bouts'] if me['id'] in (b['a'], b['b'])}
                for b in g['bouts']:
                    board = offsets[gi] + b['slot']
                    if me['id'] in (b['a'], b['b']):
                        opponent_id = b['b'] if me['id'] == b['a'] else b['a']
                        done = has_result(b)
                        mine = b['sa'] if me['id'] == b['a'] else b['sb']
                        theirs = b['sb'] if me['id'] == b['a'] else b['sa']
                        by = None
                        if b['by'] == me['id']:
                            by = 'me'
                        elif b['by'] == 'admin':
                            by = 'organizer'
                        elif b['by'] is not None:
                            by = 'opponent'
                        opponent = by_id.get(opponent_id, {})
                        ref = by_id.get(b['ref'])
                        bouts.append({
                            'id': b['id'], 'pool': g['name'], 'turn': b['turn'], 'board': board,
                            'opponent': {'name': label(opponent_id), 'club': opponent.get('club', '')},
                            'referee': label(b['ref']) if ref else None,
                            'mine': mine if done else None, 'theirs': theirs if done else None,
                            'hasResult': done, 'by': by if done else None,
                            'disputed': b['disputed'], 'closed': g['closed'],
                            'noRest': (b['turn'] - 1) in my_turns,
                            'canEnter': (not g['closed'] and not b['disputed']
                                         and (not done or b['by'] == me['id'])),
                            'canDispute': (not g['closed'] and done and not b['disputed']
                                           and b['by'] == opponent_id),
                        })
                    if b['ref'] == me['id']:
                        refereeing.append({
                            'id': b['id'], 'pool': g['name'], 'turn': b['turn'], 'board': board,
                            'fighters': [label(b['a']), label(b['b'])],
                            'done': has_result(b),
                        })
            nxt = next((x['id'] for x in bouts if not x['hasResult'] and not x['closed']), None)
            return {
                'fencer': {'firstName': me['firstName'], 'lastName': me['lastName'], 'club': me['club'],
                           'ranking': me['ranking'], 'rankingSource': me['rankingSource']},
                'pool': pool, 'bouts': bouts, 'next': nxt, 'refereeing': refereeing,
            }

    # --- ranking PZSzerm ---

    def import_ranking(self, entries, source):
        with self.lock:
            self.data['ranking'] = {
                'entries': entries,
                'source': source,
                'importedAt': time.time(),
            }
            updated = 0
            if not self._pools_locked():
                updated = self._rematch()
            self._save()
            return updated

    def _rematch(self):
        """Przelicza ranking zawodników spoza trybu ręcznego po nowym imporcie."""
        manual = [f for f in self.data['fencers'] if f['rankingSource'] == 'manual']
        used = {f['ranking'] for f in manual if f['ranking'] != UNRANKED}
        updated = 0
        for f in self.data['fencers']:
            if f['rankingSource'] == 'manual':
                continue
            entry, source = self._lookup(name_key(f['firstName'], f['lastName']))
            ranking = UNRANKED
            if entry:
                if entry['place'] in used:
                    source = 'conflict'
                else:
                    ranking = entry['place']
                    used.add(ranking)
                if entry['club']:
                    f['club'] = entry['club']
            if (f['ranking'], f['rankingSource']) != (ranking, source):
                updated += 1
            f['ranking'], f['rankingSource'] = ranking, source
        return updated

    # --- widok dla panelu ---

    def _board_offsets(self):
        """Fizyczne numery plansz: pula 1 dostaje plansze 1..k1, pula 2 kolejne itd."""
        offsets, total = [], 0
        for g in self.data['pools']['groups']:
            offsets.append(total)
            total += g['boardsUsed']
        return offsets

    def _decorated_pools(self):
        pools = copy.deepcopy(self.data['pools'])
        offsets = self._board_offsets()
        for gi, g in enumerate(pools['groups']):
            g['boardOffset'] = offsets[gi]
            turns_of = {}
            for b in g['bouts']:
                for fid in (b['a'], b['b']):
                    turns_of.setdefault(fid, set()).add(b['turn'])
            no_rest = no_ref = 0
            for b in g['bouts']:
                b['board'] = offsets[gi] + b['slot']
                b['noRestA'] = (b['turn'] - 1) in turns_of[b['a']]
                b['noRestB'] = (b['turn'] - 1) in turns_of[b['b']]
                if b['noRestA'] or b['noRestB']:
                    no_rest += 1
                if b['ref'] is None:
                    no_ref += 1
            g['warnings'] = {'noRest': no_rest, 'noReferee': no_ref,
                             'boardsReduced': g['boards'] > g['boardsUsed']}
        return pools

    def admin_pools(self):
        with self.lock:
            return self._decorated_pools()

    def admin_state(self):
        with self.lock:
            ranking = self.data['ranking']
            return {
                'fencers': self.admin_fencers(),
                'pools': self._decorated_pools(),
                'registrationOpen': self.data['registrationOpen'],
                'ranking': {'count': len(ranking['entries']), 'source': ranking['source'],
                            'importedAt': ranking['importedAt']},
            }


STORE = Store(DATA_FILE)
PIN_FAILS = {}
PIN_LOCK = threading.Lock()


def lan_url():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('10.255.255.255', 1))  # nie wysyła pakietów, tylko wybiera interfejs
        ip = sock.getsockname()[0]
    except OSError:
        ip = '127.0.0.1'
    finally:
        sock.close()
    return 'http://{}:{}'.format(ip, PORT)


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    server_version = 'TurniejApp'
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        # bez zapytania (query), bo w adresie osobistego QR jest token zawodnika
        sys.stderr.write('%s - %s\n' % (self.address_string(), (fmt % args).split('?')[0]))

    # --- odpowiedzi ---

    def _send(self, status, body, content_type, extra=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                   'application/json; charset=utf-8')

    def _read_body(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            raise ApiError(400, 'Nieprawidłowy nagłówek Content-Length.')
        if length > MAX_BODY:
            raise ApiError(413, 'Zbyt duże żądanie.')
        if length == 0:
            return {}
        try:
            body = json.loads(self.rfile.read(length).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, 'Nieprawidłowy JSON.')
        if not isinstance(body, dict):
            raise ApiError(400, 'Oczekiwano obiektu JSON.')
        return body

    # --- autoryzacja organizatora ---

    def _require_admin(self):
        ip = self.client_address[0]
        now = time.time()
        with PIN_LOCK:
            fails = [t for t in PIN_FAILS.get(ip, []) if now - t < PIN_FAIL_WINDOW]
            PIN_FAILS[ip] = fails
            if len(fails) >= PIN_FAIL_LIMIT:
                raise ApiError(429, 'Zbyt wiele błędnych prób PIN-u. Spróbuj za minutę.')
        provided = (self.headers.get('X-Admin-Pin') or '').encode('utf-8')
        if not hmac.compare_digest(provided, ADMIN_PIN.encode('utf-8')):
            with PIN_LOCK:
                PIN_FAILS.setdefault(ip, []).append(now)
            raise ApiError(401, 'Nieprawidłowy PIN.')

    # --- routing ---

    def do_GET(self):
        self._handle('GET')

    def do_POST(self):
        self._handle('POST')

    def do_PUT(self):
        self._handle('PUT')

    def do_DELETE(self):
        self._handle('DELETE')

    def _handle(self, method):
        try:
            path = urlparse(self.path).path
            if method == 'GET' and path == '/':
                self._send(302, b'', 'text/plain', {'Location': '/join'})
            elif method == 'GET' and path in STATIC_FILES:
                self._serve_static(path)
            elif path.startswith('/api/'):
                self._api(method, path)
            else:
                raise ApiError(404, 'Nie znaleziono.')
        except ApiError as e:
            self._json(e.status, {'error': e.message})
        except Exception as e:  # nieoczekiwany błąd: szczegóły tylko w logu serwera
            sys.stderr.write('Błąd: %r\n' % (e,))
            self._json(500, {'error': 'Błąd serwera.'})

    def _serve_static(self, path):
        filename, content_type = STATIC_FILES[path]
        try:
            with open(os.path.join(STATIC_DIR, filename), 'rb') as f:
                body = f.read()
        except OSError:
            raise ApiError(404, 'Nie znaleziono pliku.')
        self._send(200, body, content_type)

    def _player_view(self, token):
        view = STORE.player_view(token)
        if view is None:
            raise ApiError(404, 'Nie znaleziono zapisu.')
        return view

    def _api(self, method, path):
        # publiczne (zawodnik z telefonu)
        if method == 'GET' and path == '/api/registration':
            return self._json(200, {'open': STORE.data['registrationOpen'] and not STORE._pools_locked()})
        if method == 'POST' and path == '/api/register':
            body = self._read_body()
            fencer = STORE.register(body.get('firstName'), body.get('lastName'), body.get('club'))
            view = self._player_view(fencer['token'])
            view['token'] = fencer['token']
            return self._json(201, view)
        if method == 'POST' and path == '/api/me':
            return self._json(200, self._player_view(self._read_body().get('token')))
        if method == 'POST' and path == '/api/bout/score':
            body = self._read_body()
            STORE.player_score(body.get('token'), body.get('id'), body.get('mine'), body.get('theirs'))
            return self._json(200, self._player_view(body.get('token')))
        if method == 'POST' and path == '/api/bout/dispute':
            body = self._read_body()
            STORE.player_dispute(body.get('token'), body.get('id'))
            return self._json(200, self._player_view(body.get('token')))

        # organizator
        if path.startswith('/api/admin/'):
            self._require_admin()
            return self._admin_api(method, path[len('/api/admin/'):])

        raise ApiError(404, 'Nie znaleziono.')

    def _admin_api(self, method, route):
        if method == 'GET' and route == 'state':
            state = STORE.admin_state()
            state['lanUrl'] = lan_url()
            return self._json(200, state)
        if method == 'POST' and route == 'fencers':
            return self._json(201, {'fencers': STORE.admin_add(self._read_body())})
        if route.startswith('fencers/'):
            fencer_id = route[len('fencers/'):]
            if method == 'PUT':
                return self._json(200, {'fencers': STORE.admin_update(fencer_id, self._read_body())})
            if method == 'DELETE':
                return self._json(200, {'fencers': STORE.admin_delete(fencer_id)})
        if method == 'PUT' and route == 'pools':
            is_open = STORE.set_pools(self._read_body())
            return self._json(200, {'registrationOpen': is_open, 'pools': STORE.admin_pools()})
        if method == 'POST' and route == 'advance':
            body = self._read_body()
            STORE.set_advance(body.get('advanceCount'))
            return self._json(200, {'pools': STORE.admin_pools()})
        if method == 'PUT' and route == 'bout':
            body = self._read_body()
            STORE.admin_set_score(body.get('id'), body.get('sa'), body.get('sb'))
            return self._json(200, {'pools': STORE.admin_pools()})
        if method == 'POST' and route == 'bout/referee':
            body = self._read_body()
            STORE.admin_set_referee(body.get('id'), body.get('referee'))
            return self._json(200, {'pools': STORE.admin_pools()})
        if method == 'POST' and route == 'group/boards':
            body = self._read_body()
            STORE.admin_set_boards(body.get('group'), body.get('boards'))
            return self._json(200, {'pools': STORE.admin_pools()})
        if method == 'POST' and route == 'group/closed':
            body = self._read_body()
            STORE.admin_set_closed(body.get('group'), body.get('closed'))
            return self._json(200, {'pools': STORE.admin_pools()})
        if method == 'POST' and route == 'registration':
            is_open = self._read_body().get('open')
            if not isinstance(is_open, bool):
                raise ApiError(400, 'Oczekiwano pola open (true/false).')
            return self._json(200, {'registrationOpen': STORE.set_registration(is_open)})
        if method == 'POST' and route == 'ranking/fetch':
            url = clean(self._read_body().get('url'))
            entries = fetch_ranking(url)
            updated = STORE.import_ranking(entries, url)
            return self._json(200, {'count': len(entries), 'updated': updated})
        if method == 'POST' and route == 'ranking/paste':
            text = self._read_body().get('text')
            if not isinstance(text, str) or not text.strip():
                raise ApiError(400, 'Wklej tabelę klasyfikacji.')
            entries = parse_ranking_text(text)
            if not entries:
                raise ApiError(422, 'Nie rozpoznano tabeli. Skopiuj całą tabelę ze strony PZSzerm '
                                    '(od nagłówka „Miejsce”) i wklej ją ponownie.')
            updated = STORE.import_ranking(entries, 'wklejona tabela')
            return self._json(200, {'count': len(entries), 'updated': updated})
        raise ApiError(404, 'Nie znaleziono.')


def main():
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    base = lan_url()
    print('Serwer działa.')
    print('  Panel organizatora: http://localhost:{}/admin'.format(PORT))
    print('  Zapis zawodników:   {}/join'.format(base))
    print('  PIN organizatora:   {}'.format(ADMIN_PIN))
    print('Telefony muszą być w tej samej sieci Wi-Fi; przy pierwszym uruchomieniu zezwól Pythonowi')
    print('w zaporze Windows na dostęp do sieci prywatnej. Zatrzymanie: Ctrl+C.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nZatrzymano.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
