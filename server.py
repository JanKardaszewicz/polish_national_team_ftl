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
import random
import re
import secrets
import socket
import sys
import threading
import time
import unicodedata
import uuid
from fractions import Fraction
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
THRESHOLD = 5             # trafienia w walce w grupie
MAX_BOARDS = 20
DE_THRESHOLD = 15         # trafienia w walce drabinki direct elimination
MAX_BODY = 2 * 1024 * 1024
MAX_FENCERS = 2000
PIN_FAIL_LIMIT = 10
PIN_FAIL_WINDOW = 60.0

STATIC_FILES = {
    '/admin': ('admin.html', 'text/html; charset=utf-8'),
    '/join': ('join.html', 'text/html; charset=utf-8'),
    '/static/qrcode.js': ('qrcode.js', 'application/javascript; charset=utf-8'),
    '/static/i18n.js': ('i18n.js', 'application/javascript; charset=utf-8'),
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
    """rows: lista wierszy (lista komórek). Zwraca (wpisy, pominięte wiersze); brak nagłówka 'Miejsce' daje ([], [])."""
    header_index = None
    for i, row in enumerate(rows):
        if any(fold(cell).startswith('miejsce') for cell in row):
            header_index = i
            break
    if header_index is None:
        return [], []
    header = [fold(cell) for cell in rows[header_index]]
    place_col = next(i for i, h in enumerate(header) if h.startswith('miejsce'))
    name_col = next((i for i, h in enumerate(header) if 'nazwisko' in h), place_col + 1)
    club_col = next((i for i, h in enumerate(header) if h == 'klub'), None)

    entries, skipped = [], []
    for row in rows[header_index + 1:]:
        match = re.match(r'\s*(\d+)', row[place_col]) if len(row) > max(place_col, name_col) else None
        name = clean(row[name_col]) if match else ''
        key = name_key(name)
        place = int(match.group(1)) if match else 0
        if not match or not key or not 1 <= place <= MAX_PLACE:
            text = ' | '.join(c for c in (clean(c) for c in row) if c)
            if text:
                skipped.append(text[:200])
            continue
        club = clean(row[club_col]) if club_col is not None and club_col < len(row) else ''
        entries.append({'place': place, 'name': name, 'club': club, 'key': key})
    return entries, skipped


def parse_ranking_html(html):
    """Zwraca (wpisy, pominięte wiersze) z pierwszej tabeli z nagłówkiem 'Miejsce'."""
    parser = _TableParser()
    parser.feed(html)
    for table in parser.tables:
        entries, skipped = _entries_from_rows(table)
        if entries:
            return entries, skipped[:200]
    return [], []


# ---------- walki ----------

def validate_scores(sa, sb):
    """None albo liczby 0..THRESHOLD; pełny wynik: różne liczby (zwycięzca ma więcej, może mniej niż THRESHOLD, np. 4:3 na czas)."""
    for s in (sa, sb):
        if s is not None and (not is_int(s) or not 0 <= s <= THRESHOLD):
            raise ApiError(400, 'Wynik musi być liczbą całkowitą od 0 do {}.'.format(THRESHOLD))
    if sa is not None and sb is not None and sa == sb:
        raise ApiError(400, 'Wynik nie może być remisem, ktoś musi wygrać.')


def has_result(bout):
    return bout['sa'] is not None and bout['sb'] is not None


def pool_stats(fencer_ids, bouts):
    """V, M, TS, TR dla każdego zawodnika grupy (tylko walki z pełnym wynikiem)."""
    stats = {fid: {'id': fid, 'V': 0, 'M': 0, 'TS': 0, 'TR': 0} for fid in fencer_ids}
    for b in bouts:
        if not has_result(b):
            continue
        a, c = stats[b['a']], stats[b['b']]
        a['M'] += 1
        c['M'] += 1
        a['TS'] += b['sa']
        a['TR'] += b['sb']
        c['TS'] += b['sb']
        c['TR'] += b['sa']
        (a if b['sa'] > b['sb'] else c)['V'] += 1
    return list(stats.values())


def rank_stats(rows):
    """Sortuje po V/M, wskaźniku (TS-TR), TS; remisy mają wspólne miejsce (etykieta np. '3T')."""
    for r in rows:
        r['Ind'] = r['TS'] - r['TR']
        r['VM'] = Fraction(r['V'], r['M']) if r['M'] else Fraction(0)
    key = lambda r: (-r['VM'], -r['Ind'], -r['TS'])
    rows = sorted(rows, key=key)
    place = 0
    for i, r in enumerate(rows):
        if i == 0 or key(rows[i - 1]) != key(r):
            place = i + 1
        r['place'] = place
    counts = {}
    for r in rows:
        counts[r['place']] = counts.get(r['place'], 0) + 1
    for r in rows:
        r['label'] = '{}T'.format(r['place']) if counts[r['place']] > 1 else str(r['place'])
    return rows


def bracket_order(size):
    """Kolejność rozstawienia w drabince o rozmiarze size (potęga 2): [1, 8, 4, 5, 2, 7, 3, 6] dla 8."""
    order = [1, 2]
    while len(order) < size:
        n = len(order) * 2
        order = [x for seed in order for x in (seed, n + 1 - seed)]
    return order[:size]


def snake_groups(ids, count):
    groups = [[] for _ in range(count)]
    for i, fid in enumerate(ids):
        row, col = divmod(i, count)
        groups[col if row % 2 == 0 else count - 1 - col].append(fid)
    return groups


def pool_complete(group):
    return all(has_result(b) for b in group['bouts'])


def default_data():
    return {
        'registrationOpen': True,
        'ranking': {'entries': [], 'skipped': [], 'source': '', 'importedAt': None},
        'fencers': [],
        'pools': {'poolSize': 7, 'advanceCount': None, 'groups': [], 'approved': False, 'round': 1},
        'rounds': [],      # zarchiwizowane tury grup (ranking po turze)
        'bracket': None,   # drabinka direct elimination
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
        data['pools'].setdefault('approved', False)
        data['pools'].setdefault('round', 1)
        for g in data['pools'].get('groups', []):
            g.setdefault('boards', 1)
            g.setdefault('boardsUsed', 1)
            g.setdefault('closed', False)
            for i, b in enumerate(g.get('bouts', [])):
                b.setdefault('id', new_id())
                b.setdefault('by', None)
                b.setdefault('disputed', False)
                b.setdefault('editRequested', False)
                b.setdefault('editApproved', False)
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
            raise ApiError(423, 'Lista zawodników jest zablokowana, bo grupy są utworzone.')

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

    def _auto_ranking(self, key, club, exclude_id):
        """Ranking i klub z zaimportowanej klasyfikacji PZSzerm; zwraca (ranking, źródło, klub)."""
        entry, source = self._lookup(key)
        ranking = UNRANKED
        if entry:
            if entry['place'] in self._used_rankings(exclude_id):
                source = 'conflict'
            else:
                ranking = entry['place']
            club = entry['club'] or club
        return ranking, source, club

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

            ranking, source, club = self._auto_ranking(key, club, None)

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
        if ranking is None:   # puste pole: ranking i klub z klasyfikacji PZSzerm, jak przy zapisie z telefonu
            self._check_duplicate(key, exclude_id)
            ranking, source, club = self._auto_ranking(key, club, exclude_id)
            return first, last, club, country, ranking, source
        if not is_int(ranking) or not 1 <= ranking <= 9999:
            raise ApiError(400, 'Ranking musi być liczbą całkowitą od 1 do 9999.')
        self._check_duplicate(key, exclude_id)
        if ranking != UNRANKED:
            for f in self.data['fencers']:
                if f['id'] != exclude_id and f['ranking'] == ranking:
                    raise ApiError(409, 'Ranking {} jest już przypisany do: {} {}.'.format(
                        ranking, f['lastName'], f['firstName']))
        return first, last, club, country, ranking, 'manual'

    def admin_add(self, body):
        with self.lock:
            self._require_unlocked()
            if len(self.data['fencers']) >= MAX_FENCERS:
                raise ApiError(403, 'Osiągnięto limit zawodników.')
            first, last, club, country, ranking, source = self._read_manual(body, None)
            self.data['fencers'].append({
                'id': new_id(),
                'firstName': first, 'lastName': last, 'club': club, 'country': country,
                'ranking': ranking, 'rankingSource': source,
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
            first, last, club, country, ranking, source = self._read_manual(body, fencer_id)
            fencer.update({'firstName': first, 'lastName': last, 'club': club,
                           'country': country, 'ranking': ranking, 'rankingSource': source})
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
                raise ApiError(409, 'Grupy są utworzone, zapisy nie mogą być otwarte.')
            self.data['registrationOpen'] = bool(is_open)
            self._save()
            return self.data['registrationOpen']

    # --- grupy ---

    def _club_keys(self):
        return {f['id']: name_key(f['club']) for f in self.data['fencers']}

    def set_pools(self, state):
        """Tworzy grupy (podział zawodników przychodzi z panelu, walki układa serwer) albo je usuwa."""
        with self.lock:
            if not isinstance(state, dict) or not isinstance(state.get('groups'), list):
                raise ApiError(400, 'Nieprawidłowe dane grup.')
            pool_size = state.get('poolSize')
            advance = state.get('advanceCount')
            total = len(self.data['fencers'])
            if not is_int(pool_size) or not 2 <= pool_size <= 500:
                raise ApiError(400, 'Nieprawidłowy rozmiar grupy.')
            if state['groups'] and pool_size > total:
                raise ApiError(400, 'Rozmiar grupy nie może być większy niż liczba zawodników ({}).'.format(total))
            if advance is not None and (not is_int(advance) or advance < 0 or (state['groups'] and advance > total)):
                raise ApiError(400, 'Nieprawidłowa liczba awansujących (maksymalnie {}).'.format(total))
            if len(state['groups']) > 500:
                raise ApiError(400, 'Zbyt wiele grup.')
            if state['groups'] and self._pools_locked():
                raise ApiError(409, 'Grupy już istnieją. Najpierw je usuń.')

            ids = {f['id'] for f in self.data['fencers']}
            clubs = self._club_keys()
            used = set()
            groups = []
            for g in state['groups']:
                if not isinstance(g, dict) or not isinstance(g.get('fencerIds'), list):
                    raise ApiError(400, 'Nieprawidłowa grupa.')
                members = g['fencerIds']
                if len(members) < 2 or any(not isinstance(m, str) or m not in ids or m in used for m in members):
                    raise ApiError(400, 'Grupa musi mieć co najmniej dwóch znanych, niepowtarzających się zawodników.')
                used.update(members)
                members = random.sample(members, len(members))  # skład wg rankingu, pozycje w grupie (kolejność walk) losowe
                boards = g.get('boards', 1)
                if not is_int(boards) or not 1 <= boards <= MAX_BOARDS:
                    raise ApiError(400, 'Górny limit plansz musi być liczbą od 1 do {}.'.format(MAX_BOARDS))
                bouts, boards_used = schedule.build_bouts(list(members), boards, clubs, new_id)
                groups.append({
                    'name': clean(g.get('name'))[:40] or 'Grupa',
                    'fencerIds': list(members),
                    'boards': boards,
                    'boardsUsed': boards_used,
                    'closed': False,
                    'bouts': bouts,
                })
            self.data['pools'] = {'poolSize': pool_size, 'advanceCount': advance, 'groups': groups,
                                  'approved': False, 'round': 1}
            self.data['rounds'] = []
            self.data['bracket'] = None
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

    def _require_not_approved(self):
        if self.data['pools'].get('approved'):
            raise ApiError(423, 'Grupy są zatwierdzone. Cofnij zatwierdzenie, żeby coś zmienić.')

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
            raise ApiError(404, 'Nie ma takiej grupy.')
        return groups[index]

    def admin_set_score(self, bout_id, sa, sb):
        with self.lock:
            self._require_not_approved()
            _g, bout = self._find_bout(bout_id)
            validate_scores(sa, sb)
            bout['sa'], bout['sb'] = sa, sb
            bout['by'] = 'admin' if (sa is not None or sb is not None) else None
            bout['disputed'] = False
            bout['editRequested'] = bout['editApproved'] = False
            self._save()

    def admin_set_referee(self, bout_id, referee_id):
        with self.lock:
            self._require_not_approved()
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
            self._require_not_approved()
            g = self._group(group_index)
            if not is_int(boards) or not 1 <= boards <= MAX_BOARDS:
                raise ApiError(400, 'Górny limit plansz musi być liczbą od 1 do {}.'.format(MAX_BOARDS))
            if any(b['sa'] is not None or b['sb'] is not None for b in g['bouts']):
                raise ApiError(409, 'W tej grupie są już wpisane wyniki. Zmiana plansz zmieniłaby kolejność walk.')
            bouts, boards_used = schedule.build_bouts(g['fencerIds'], boards, self._club_keys(), new_id)
            g['boards'], g['boardsUsed'], g['bouts'] = boards, boards_used, bouts
            self._save()

    def admin_move_fencer(self, fencer_id, to_index):
        """Przenosi zawodnika do innej grupy; walki obu grup są układane od nowa (tylko bez wyników)."""
        with self.lock:
            self._require_not_approved()
            target = self._group(to_index)
            source = next((g for g in self.data['pools']['groups'] if fencer_id in g['fencerIds']), None)
            if source is None:
                raise ApiError(404, 'Ten zawodnik nie jest w żadnej grupie.')
            if source is target:
                raise ApiError(400, 'Zawodnik jest już w tej grupie.')
            if len(source['fencerIds']) <= 2:
                raise ApiError(409, 'W grupie muszą zostać co najmniej dwie osoby.')
            for g in (source, target):
                if any(b['sa'] is not None or b['sb'] is not None for b in g['bouts']):
                    raise ApiError(409, 'W grupie "{}" są już wpisane wyniki. Przeniesienie zmieniłoby kolejność walk.'.format(g['name']))
            clubs = self._club_keys()
            source_ids = [x for x in source['fencerIds'] if x != fencer_id]
            target_ids = list(target['fencerIds'])
            target_ids.insert(random.randint(0, len(target_ids)), fencer_id)
            for g, ids in ((source, source_ids), (target, target_ids)):
                bouts, used = schedule.build_bouts(ids, g['boards'], clubs, new_id)
                g['fencerIds'], g['bouts'], g['boardsUsed'] = ids, bouts, used
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
            if self.data['pools'].get('approved'):
                raise ApiError(423, 'Grupy są zatwierdzone. Wynik poprawi organizator.')
            if mine is None or theirs is None:
                raise ApiError(400, 'Podaj oba wyniki.')
            validate_scores(mine, theirs)
            if g['closed']:
                raise ApiError(423, 'Grupa jest zamknięta. Wynik poprawi organizator.')
            if bout['disputed']:
                raise ApiError(423, 'Zgłoszono błąd w tym wyniku. Decyduje organizator.')
            if has_result(bout) and bout['by'] != me['id']:
                raise ApiError(409, 'Wynik wpisał już ktoś inny. Jeśli jest błędny, zgłoś błąd.')
            if has_result(bout) and not bout['editApproved']:
                raise ApiError(409, 'Wynik jest już wpisany. Poprawę musi zatwierdzić organizator.')
            if me['id'] == bout['a']:
                bout['sa'], bout['sb'] = mine, theirs
            else:
                bout['sa'], bout['sb'] = theirs, mine
            bout['by'] = me['id']
            bout['disputed'] = False
            bout['editRequested'] = bout['editApproved'] = False
            self._save()

    def player_request_edit(self, token, bout_id):
        with self.lock:
            me, g, bout = self._own_bout(token, bout_id)
            if self.data['pools'].get('approved'):
                raise ApiError(423, 'Grupy są zatwierdzone. Wynik poprawi organizator.')
            if g['closed']:
                raise ApiError(423, 'Grupa jest zamknięta. Skontaktuj się z organizatorem.')
            if not has_result(bout) or bout['by'] != me['id']:
                raise ApiError(409, 'Poprawę możesz zgłosić tylko do wyniku, który sam wpisałeś.')
            if bout['disputed']:
                raise ApiError(423, 'Zgłoszono błąd w tym wyniku. Decyduje organizator.')
            bout['editRequested'] = True
            self._save()

    def admin_approve_edit(self, bout_id):
        with self.lock:
            self._require_not_approved()
            _g, bout = self._find_bout(bout_id)
            if not has_result(bout) or bout['by'] in (None, 'admin'):
                raise ApiError(409, 'Do tej walki nie ma wyniku wpisanego przez zawodnika.')
            bout['editRequested'] = False
            bout['editApproved'] = True
            self._save()

    def player_dispute(self, token, bout_id):
        with self.lock:
            me, g, bout = self._own_bout(token, bout_id)
            if self.data['pools'].get('approved'):
                raise ApiError(423, 'Grupy są zatwierdzone. Wynik poprawi organizator.')
            if g['closed']:
                raise ApiError(423, 'Grupa jest zamknięta. Skontaktuj się z organizatorem.')
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
            approved = bool(self.data['pools'].get('approved'))

            def label(fid):
                f = by_id.get(fid)
                return '{} {}'.format(f['lastName'], f['firstName']) if f else '?'

            pool = None
            bouts = []
            refereeing = []
            for gi, g in enumerate(groups):
                if me['id'] in g['fencerIds'] and pool is None:
                    pool = {'name': g['name'], 'closed': g['closed'] or approved}
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
                            'disputed': b['disputed'], 'closed': g['closed'] or approved,
                            'noRest': (b['turn'] - 1) in my_turns,
                            'editRequested': b['editRequested'] and b['by'] == me['id'],
                            'editApproved': b['editApproved'] and b['by'] == me['id'],
                            'canEnter': (not g['closed'] and not approved and not b['disputed']
                                         and (not done or (b['by'] == me['id'] and b['editApproved']))),
                            'canRequestEdit': (not g['closed'] and not approved and done and not b['disputed']
                                               and b['by'] == me['id'] and not b['editRequested']
                                               and not b['editApproved']),
                            'canDispute': (not g['closed'] and not approved and done and not b['disputed']
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
                'poolResults': self._pool_results(me['id'], by_id),
            }

    def _my_group(self, fencer_id):
        return next((g for g in self.data['pools']['groups'] if fencer_id in g['fencerIds']), None)

    def _pool_results(self, fencer_id, by_id):
        """Szachownica własnej grupy, dostępna dla zawodnika dopiero po zakończeniu tej grupy."""
        g = self._my_group(fencer_id)
        if g is None or not g['bouts'] or not pool_complete(g) or any(b['disputed'] for b in g['bouts']):
            return None
        stats = {r['id']: r for r in rank_stats(pool_stats(g['fencerIds'], g['bouts']))}
        rows = []
        for x in g['fencerIds']:
            cells = []
            for y in g['fencerIds']:
                if x == y:
                    cells.append(None)
                    continue
                b = next(b for b in g['bouts'] if {b['a'], b['b']} == {x, y})
                mine, theirs = (b['sa'], b['sb']) if b['a'] == x else (b['sb'], b['sa'])
                if mine > theirs:
                    cells.append({'win': True, 'text': 'V' if mine == THRESHOLD else 'V{}'.format(mine)})
                else:
                    cells.append({'win': False, 'text': 'D{}'.format(mine)})
            st = stats[x]
            f = by_id.get(x, {})
            rows.append({'name': '{} {}'.format(f.get('lastName', '?'), f.get('firstName', '')).strip(),
                         'me': x == fencer_id, 'cells': cells, 'V': st['V'], 'M': st['M'],
                         'VM': '{:.2f}'.format(float(st['VM'])), 'TS': st['TS'], 'TR': st['TR'],
                         'Ind': st['Ind'], 'place': st['label']})
        return {'pool': g['name'], 'rows': rows}

    def player_ranking(self, token):
        """Ranking wszystkich grup; dostępny dla zawodnika po zakończeniu jego grupy."""
        with self.lock:
            me = self.find_by_token(token)
            if not me:
                raise ApiError(404, 'Nie znaleziono zapisu.')
            mine = self._my_group(me['id'])
            if mine is None or not pool_complete(mine):
                raise ApiError(403, 'Ranking będzie dostępny po zakończeniu Twojej grupy.')
            by_id = {f['id']: f for f in self.data['fencers']}
            groups = self.data['pools']['groups']
            rows = []
            for g in groups:
                for st in pool_stats(g['fencerIds'], g['bouts']):
                    st['pool'] = g['name']
                    rows.append(st)
            ranked = rank_stats(rows)
            complete = all(pool_complete(g) for g in groups)
            advance = self.data['pools'].get('advanceCount') or 0
            out = []
            for i, st in enumerate(ranked):
                f = by_id.get(st['id'], {})
                out.append({'place': st['label'], 'name': '{} {}'.format(f.get('lastName', '?'), f.get('firstName', '')).strip(),
                            'club': f.get('club', ''), 'pool': st['pool'], 'V': st['V'], 'M': st['M'],
                            'VM': '{:.2f}'.format(float(st['VM'])), 'TS': st['TS'], 'TR': st['TR'], 'Ind': st['Ind'],
                            'advance': complete and i < advance, 'me': st['id'] == me['id']})
            return {'rows': out, 'complete': complete, 'advanceCount': advance}

    # --- ranking PZSzerm ---

    def import_ranking(self, entries, skipped, source):
        with self.lock:
            self.data['ranking'] = {
                'entries': entries,
                'skipped': skipped,
                'source': source,
                'importedAt': time.time(),
            }
            updated = 0
            if not self._pools_locked():
                updated = self._rematch()
            self._save()
            return updated

    def ranking_preview(self):
        """Wczytana klasyfikacja do podglądu: kto został dopasowany do zapisanego zawodnika, jakie wiersze pominięto."""
        with self.lock:
            ranking = self.data['ranking']
            by_key = {}
            for f in self.data['fencers']:
                by_key.setdefault(name_key(f['firstName'], f['lastName']), []).append(
                    '{} {}'.format(f['lastName'], f['firstName']))
            entries = [{'place': e['place'], 'name': e['name'], 'club': e['club'],
                        'fencer': ', '.join(by_key.get(e['key'], []))}
                       for e in ranking['entries']]
            return {'entries': entries, 'skipped': ranking.get('skipped', []),
                    'source': ranking['source'], 'importedAt': ranking['importedAt']}

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

    # --- zatwierdzenie grup, druga tura, drabinka ---

    def _overall_ranking(self):
        """Ranking po grupach bieżącej tury; remisy rozstrzyga miejsce w klasyfikacji PZSzerm (do rozstawienia)."""
        by_id = {f['id']: f for f in self.data['fencers']}
        rows = []
        for g in self.data['pools']['groups']:
            for st in pool_stats(g['fencerIds'], g['bouts']):
                st['pool'] = g['name']
                rows.append(st)
        rows.sort(key=lambda r: (by_id[r['id']]['ranking'], by_id[r['id']]['createdAt']))
        return rank_stats(rows)

    def _ranking_snapshot(self):
        by_id = {f['id']: f for f in self.data['fencers']}
        out = []
        for r in self._overall_ranking():
            f = by_id[r['id']]
            out.append({'place': r['label'], 'name': '{} {}'.format(f['lastName'], f['firstName']),
                        'club': f['club'], 'pool': r['pool'], 'V': r['V'], 'M': r['M'],
                        'VM': '{:.2f}'.format(float(r['VM'])), 'TS': r['TS'], 'TR': r['TR'], 'Ind': r['Ind']})
        return out

    def approve_groups(self, approved):
        with self.lock:
            pools = self.data['pools']
            if not pools['groups']:
                raise ApiError(409, 'Nie ma utworzonych grup.')
            if not isinstance(approved, bool):
                raise ApiError(400, 'Oczekiwano pola approved (true/false).')
            if approved:
                bouts = [b for g in pools['groups'] for b in g['bouts']]
                if not all(has_result(b) for b in bouts):
                    raise ApiError(409, 'Nie wszystkie walki w grupach mają wyniki.')
                if any(b['disputed'] or b['editRequested'] for b in bouts):
                    raise ApiError(409, 'Są walki ze zgłoszonym błędem lub prośbą o poprawę. Rozstrzygnij je przed zatwierdzeniem.')
            elif self.data['bracket'] is not None:
                raise ApiError(409, 'Najpierw usuń drabinkę.')
            pools['approved'] = approved
            self._save()

    def create_round2(self, pool_size, boards):
        """Druga tura grup: wszyscy zawodnicy rozdzieleni wężem według rankingu po pierwszej turze."""
        with self.lock:
            pools = self.data['pools']
            if not pools.get('approved'):
                raise ApiError(409, 'Najpierw zatwierdź wszystkie grupy.')
            if pools.get('round', 1) >= 2:
                raise ApiError(409, 'Druga tura grup już istnieje.')
            if self.data['bracket'] is not None:
                raise ApiError(409, 'Najpierw usuń drabinkę.')
            ranked = self._overall_ranking()
            total = len(ranked)
            if not is_int(pool_size) or not 2 <= pool_size <= total:
                raise ApiError(400, 'Rozmiar grupy musi być liczbą całkowitą od 2 do {}.'.format(total))
            if not is_int(boards) or not 1 <= boards <= MAX_BOARDS:
                raise ApiError(400, 'Górny limit plansz musi być liczbą od 1 do {}.'.format(MAX_BOARDS))
            count = max(1, min(-(-total // pool_size), total // 2))
            clubs = self._club_keys()
            groups = []
            for k, members in enumerate(snake_groups([r['id'] for r in ranked], count)):
                members = random.sample(members, len(members))
                bouts, used = schedule.build_bouts(members, boards, clubs, new_id)
                groups.append({'name': 'Grupa {}'.format(k + 1), 'fencerIds': members, 'boards': boards,
                               'boardsUsed': used, 'closed': False, 'bouts': bouts})
            self.data['rounds'].append({'round': pools.get('round', 1), 'standings': self._ranking_snapshot()})
            advance = pools.get('advanceCount')
            self.data['pools'] = {'poolSize': pool_size, 'advanceCount': None if advance is None else min(advance, total),
                                  'groups': groups, 'approved': False, 'round': pools.get('round', 1) + 1}
            self._save()

    def create_bracket(self, advance):
        with self.lock:
            pools = self.data['pools']
            if not pools.get('approved'):
                raise ApiError(409, 'Najpierw zatwierdź wszystkie grupy.')
            if self.data['bracket'] is not None:
                raise ApiError(409, 'Drabinka już istnieje. Najpierw ją usuń.')
            ranked = self._overall_ranking()
            if advance is None:
                advance = pools.get('advanceCount')
            if not is_int(advance) or not 2 <= advance <= len(ranked):
                raise ApiError(400, 'Liczba zawodników w drabince musi być liczbą od 2 do {}.'.format(len(ranked)))
            seeds = [r['id'] for r in ranked[:advance]]
            size = 2
            while size < advance:
                size *= 2
            order = bracket_order(size)
            first = []
            for i in range(0, size, 2):
                a = seeds[order[i] - 1] if order[i] <= advance else None
                b = seeds[order[i + 1] - 1] if order[i + 1] <= advance else None
                bye = (a is None) != (b is None)
                first.append({'id': new_id(), 'a': a, 'b': b, 'sa': None, 'sb': None, 'bye': bye,
                              'winner': (a or b) if bye else None})
            rounds = [first]
            while len(rounds[-1]) > 1:
                rounds.append([{'id': new_id(), 'a': None, 'b': None, 'sa': None, 'sb': None, 'bye': False, 'winner': None}
                               for _ in range(len(rounds[-1]) // 2)])
            third = None
            if size >= 4 and not any(b['bye'] for b in rounds[-2]):
                third = {'id': new_id(), 'a': None, 'b': None, 'sa': None, 'sb': None, 'bye': False, 'winner': None}
            bracket = {'size': size, 'count': advance, 'seeds': seeds, 'rounds': rounds, 'third': third}
            self._propagate(bracket)
            self.data['bracket'] = bracket
            self._save()

    @staticmethod
    def _loser(bout):
        if bout is None or bout['winner'] is None or bout['bye']:
            return None
        return bout['b'] if bout['winner'] == bout['a'] else bout['a']

    def _propagate(self, bracket):
        """Wstawia zwycięzców do kolejnych walk i przegranych półfinałów do walki o 3. miejsce."""
        rounds = bracket['rounds']
        for r in range(1, len(rounds)):
            for i, bout in enumerate(rounds[r]):
                bout['a'] = rounds[r - 1][2 * i]['winner']
                bout['b'] = rounds[r - 1][2 * i + 1]['winner']
        if bracket['third'] is not None:
            semis = rounds[-2]
            bracket['third']['a'] = self._loser(semis[0])
            bracket['third']['b'] = self._loser(semis[1])

    def bracket_set_score(self, bout_id, sa, sb):
        with self.lock:
            bracket = self.data['bracket']
            if bracket is None:
                raise ApiError(404, 'Drabinka nie istnieje.')
            found = None
            for r, rnd in enumerate(bracket['rounds']):
                for i, b in enumerate(rnd):
                    if b['id'] == bout_id:
                        found = (r, i, b)
            if found is None and bracket['third'] is not None and bracket['third']['id'] == bout_id:
                found = (-1, 0, bracket['third'])
            if found is None:
                raise ApiError(404, 'Nie ma takiej walki.')
            r, i, bout = found
            if bout['bye'] or bout['a'] is None or bout['b'] is None:
                raise ApiError(409, 'W tej walce nie są jeszcze znani obaj zawodnicy.')
            for v in (sa, sb):
                if v is not None and (not is_int(v) or not 0 <= v <= DE_THRESHOLD):
                    raise ApiError(400, 'Wynik musi być liczbą całkowitą od 0 do {}.'.format(DE_THRESHOLD))
            if sa is not None and sb is not None and sa == sb:
                raise ApiError(400, 'Wynik nie może być remisem, ktoś musi wygrać.')
            new_winner = None
            if sa is not None and sb is not None:
                new_winner = bout['a'] if sa > sb else bout['b']
            if new_winner != bout['winner']:
                downstream = []
                if r >= 0 and r + 1 < len(bracket['rounds']):
                    downstream.append(bracket['rounds'][r + 1][i // 2])
                if r == len(bracket['rounds']) - 2 and bracket['third'] is not None:
                    downstream.append(bracket['third'])
                if any(d['sa'] is not None or d['sb'] is not None for d in downstream):
                    raise ApiError(409, 'Walka następnej rundy ma już wynik. Najpierw usuń jej wynik.')
            bout['sa'], bout['sb'], bout['winner'] = sa, sb, new_winner
            self._propagate(bracket)
            self._save()

    def delete_bracket(self):
        with self.lock:
            self.data['bracket'] = None
            self._save()

    # --- nowy turniej ---

    def new_tournament(self):
        """Archiwizuje bieżące dane do katalogu archiwum/ i czyści turniej (wczytana klasyfikacja zostaje)."""
        with self.lock:
            archive = None
            if self.data['fencers'] or self._pools_locked():
                directory = os.path.join(os.path.dirname(os.path.abspath(self.path)), 'archiwum')
                archive = time.strftime('turniej-%Y-%m-%d_%H-%M-%S.json')
                try:
                    os.makedirs(directory, exist_ok=True)
                    with open(os.path.join(directory, archive), 'w', encoding='utf-8') as f:
                        json.dump(self.data, f, ensure_ascii=False)
                except OSError as e:
                    raise ApiError(500, 'Nie udało się zapisać archiwum: {}'.format(e))
            fresh = default_data()
            fresh['ranking'] = self.data['ranking']
            self.data = fresh
            self._save()
            return archive

    # --- widok dla panelu ---

    def _board_offsets(self):
        """Fizyczne numery plansz: grupa 1 dostaje plansze 1..k1, grupa 2 kolejne itd."""
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
                'bracket': self.data['bracket'],
                'rounds': self.data['rounds'],
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
        if method == 'POST' and path == '/api/me/ranking':
            return self._json(200, STORE.player_ranking(self._read_body().get('token')))
        if method == 'POST' and path == '/api/bout/score':
            body = self._read_body()
            STORE.player_score(body.get('token'), body.get('id'), body.get('mine'), body.get('theirs'))
            return self._json(200, self._player_view(body.get('token')))
        if method == 'POST' and path == '/api/bout/request-edit':
            body = self._read_body()
            STORE.player_request_edit(body.get('token'), body.get('id'))
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
        if method == 'POST' and route == 'bout/approve-edit':
            STORE.admin_approve_edit(self._read_body().get('id'))
            return self._json(200, {'pools': STORE.admin_pools()})
        if method == 'POST' and route == 'bout/referee':
            body = self._read_body()
            STORE.admin_set_referee(body.get('id'), body.get('referee'))
            return self._json(200, {'pools': STORE.admin_pools()})
        if method == 'POST' and route == 'group/boards':
            body = self._read_body()
            STORE.admin_set_boards(body.get('group'), body.get('boards'))
            return self._json(200, {'pools': STORE.admin_pools()})
        if method == 'POST' and route == 'group/move':
            body = self._read_body()
            fencer_id = body.get('fencer')
            if not isinstance(fencer_id, str):
                raise ApiError(400, 'Podaj zawodnika.')
            STORE.admin_move_fencer(fencer_id, body.get('to'))
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
        if method == 'POST' and route == 'groups/approve':
            STORE.approve_groups(self._read_body().get('approved'))
            return self._json(200, {'ok': True})
        if method == 'POST' and route == 'round2':
            body = self._read_body()
            STORE.create_round2(body.get('poolSize'), body.get('boards'))
            return self._json(200, {'ok': True})
        if method == 'POST' and route == 'bracket':
            STORE.create_bracket(self._read_body().get('count'))
            return self._json(200, {'ok': True})
        if method == 'POST' and route == 'bracket/delete':
            STORE.delete_bracket()
            return self._json(200, {'ok': True})
        if method == 'PUT' and route == 'bracket/bout':
            body = self._read_body()
            STORE.bracket_set_score(body.get('id'), body.get('sa'), body.get('sb'))
            return self._json(200, {'ok': True})
        if method == 'POST' and route == 'tournament/new':
            return self._json(200, {'archive': STORE.new_tournament()})
        if method == 'POST' and route == 'ranking/file':
            body = self._read_body()
            text, name = body.get('text'), clean(body.get('filename'))
            if not isinstance(text, str) or not text.strip():
                raise ApiError(400, 'Plik jest pusty.')
            entries, skipped = parse_ranking_html(text)
            if not entries:
                raise ApiError(422, 'Nie rozpoznano tabeli w pliku. Zapisz stronę klasyfikacji jako '
                                    '„Strona internetowa, tylko HTML” (tabela musi mieć nagłówek „Miejsce”).')
            updated = STORE.import_ranking(entries, skipped, 'plik ' + (name or 'bez nazwy'))
            return self._json(200, {'count': len(entries), 'skipped': len(skipped), 'updated': updated})
        if method == 'GET' and route == 'ranking/entries':
            return self._json(200, STORE.ranking_preview())
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
