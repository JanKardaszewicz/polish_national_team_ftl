"""Układanie walk w puli: tury, plansze i sędziowie.

Szablon tur liczymy raz dla pary (liczba zawodników, liczba plansz), bo pule o tym samym
rozmiarze mają taki sam układ; dopiero sędziów dobieramy osobno dla każdej puli (kluby).
"""
import random
from functools import lru_cache


def _build_turns(n, boards, rng):
    """Jedna próba: zachłanne układanie tur z losową kolejnością remisów."""
    remaining = [(i, j) for i in range(n) for j in range(i + 1, n)]
    fights = [0] * n
    last = [-10] * n
    turns = []
    t = 0
    while remaining:
        previous = {p for pair in turns[-1] for p in pair} if turns else set()
        order = remaining[:]
        rng.shuffle(order)
        order.sort(key=lambda p: (
            (p[0] in previous) + (p[1] in previous),   # najpierw pary, które odpoczywały
            fights[p[0]] + fights[p[1]],               # potem ci, którzy walczyli najmniej
            -min(t - last[p[0]], t - last[p[1]]),      # potem ci, którzy najdłużej czekali
        ))
        busy = set()
        chosen = []
        for i, j in order:
            if len(chosen) == boards:
                break
            if i in busy or j in busy:
                continue
            chosen.append((i, j))
            busy.update((i, j))
        for i, j in chosen:
            remaining.remove((i, j))
            fights[i] += 1
            fights[j] += 1
            last[i] = last[j] = t
        turns.append(tuple(chosen))
        t += 1
    return turns


def _cost(turns, ideal_turns, n):
    """Mniej = lepiej: najpierw brak zbędnych tur, potem walki pod rząd, potem najdłuższa seria."""
    in_turns = [[] for _ in range(n)]
    for t, turn in enumerate(turns):
        for i, j in turn:
            in_turns[i].append(t)
            in_turns[j].append(t)
    consecutive = 0
    longest = 0
    for ts in in_turns:
        streak = 1
        for a, b in zip(ts, ts[1:]):
            if b == a + 1:
                consecutive += 1
                streak += 1
                longest = max(longest, streak)
            else:
                streak = 1
    return (len(turns) - ideal_turns) * 1000 + consecutive * 10 + longest


@lru_cache(maxsize=256)
def template(n, boards):
    """Zwraca (tury, użyte_plansze). Tura to krotka par (i, j) w kolejności plansz."""
    if n < 2:
        return (), 1
    used = max(1, min(boards, n // 2))
    pairs = n * (n - 1) // 2
    ideal = -(-pairs // used)
    restarts = 400 if n <= 12 else 80
    rng = random.Random(n * 100 + used)
    best = None
    for _ in range(restarts):
        turns = _build_turns(n, used, rng)
        cost = _cost(turns, ideal, n)
        if best is None or cost < best[0]:
            best = (cost, turns)
            if cost <= 1:      # idealny układ: pełne tury i nikt nie walczy dwa razy z rzędu
                break
    return tuple(best[1]), used


def assign_referees(n, turns, clubs):
    """Dla każdej walki wybiera sędziego spośród zawodników puli, którzy nie walczą w tej turze.

    Preferencje (od najważniejszej): nie walczy też w następnej turze, sędziował dotąd najmniej,
    inny klub niż walczący, nie walczył w poprzedniej turze. Zwraca listę tur; w turze lista
    (indeks_sędziego albo None, czy_walczy_zaraz_potem).
    """
    fighting = [{p for pair in turn for p in pair} for turn in turns]
    counts = [0] * n
    result = []
    for t, turn in enumerate(turns):
        used = set()
        row = []
        for i, j in turn:
            best = None
            for r in range(n):
                if r in fighting[t] or r in used:
                    continue
                next_busy = t + 1 < len(turns) and r in fighting[t + 1]
                prev_busy = t > 0 and r in fighting[t - 1]
                same_club = bool(clubs[r]) and clubs[r] in (clubs[i], clubs[j])
                key = (next_busy, counts[r], same_club, prev_busy, r)
                if best is None or key < best[0]:
                    best = (key, r)
            if best is None:
                row.append((None, False))
            else:
                r = best[1]
                used.add(r)
                counts[r] += 1
                row.append((r, best[0][0]))
        result.append(row)
    return result


def build_bouts(fencer_ids, boards, clubs_by_id, new_id):
    """Zwraca (walki w kolejności chronologicznej, użyte plansze)."""
    n = len(fencer_ids)
    if n < 2:
        return [], 1
    turns, used = template(n, boards)
    clubs = [clubs_by_id.get(fid, '') for fid in fencer_ids]
    referees = assign_referees(n, turns, clubs)
    bouts = []
    for t, turn in enumerate(turns):
        for s, (i, j) in enumerate(turn):
            ref, _tight = referees[t][s]
            bouts.append({
                'id': new_id(),
                'a': fencer_ids[i],
                'b': fencer_ids[j],
                'sa': None,
                'sb': None,
                'by': None,
                'disputed': False,
                'turn': t + 1,
                'slot': s + 1,
                'ref': fencer_ids[ref] if ref is not None else None,
                'refManual': False,
            })
    return bouts, used
