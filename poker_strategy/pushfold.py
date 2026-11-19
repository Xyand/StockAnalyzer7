"""Chip-EV push/fold Nash solver (first-in shove) for N-handed tables.

Model
-----
* Everyone has S big blinds behind (equal stacks; effective stack = S).
* Blinds 0.5/1, optional big-blind ante (dead money, default 1bb = modern MTT standard).
* Folded to the pusher at position p, who either folds or shoves S.
* Each player behind (in order) folds or calls. The first caller goes heads-up all-in;
  over-calls are ignored (they are rare at equilibrium and barely move ranges).
* Card removal between pusher and caller is exact (169x169 combo counts).
* Solved by fictitious play (averaged best responses), which converges to the
  well-known HU Nash numbers and is stable multi-way.
EV is measured in bb relative to folding at the decision point.
"""
import numpy as np
from hands import CLASSES, NCOMBOS

_D = np.load(__file__.rsplit("/", 1)[0] + "/data/equity169.npz")
E = _D["E"]          # E[i,j] equity of class i vs class j
C = _D["C"]          # non-conflicting combo-pair counts
N = np.array(NCOMBOS, dtype=float)

_LATE = ["LJ", "HJ", "CO", "BTN", "SB", "BB"]
_EARLY = ["UTG", "UTG1", "UTG2"]


def positions(n):
    """Seat names for an n-handed table (2..9), first to act preflop first."""
    if n == 2:
        return ["SB", "BB"]
    late = _LATE[-n:] if n <= 6 else _LATE
    return _EARLY[:max(0, n - 6)] + late


def _posted(name):
    return 0.5 if name == "SB" else (1.0 if name == "BB" else 0.0)


def _pot_called(S, pusher, caller, ante):
    dead = ante
    if "SB" not in (pusher, caller):
        dead += 0.5
    if "BB" not in (pusher, caller):
        dead += 1.0
    return 2 * S + dead


def _allin_ev(eq, pot, risk, bf=1.0):
    """EV of an all-in with equity eq; losses weighted by bubble factor bf (bf=1: chip EV)."""
    return eq * (pot - risk) - (1 - eq) * bf * risk


def caller_ev(S, pusher, caller, push_range, ante=1.0, bf=1.0):
    """EV(call) - EV(fold) for each caller class vs a pusher's range."""
    w = C * push_range[None, :]                 # weights over pusher hands, given caller hand
    tot = w.sum(1)
    eq = (w * E).sum(1) / np.maximum(tot, 1e-12)
    pot = _pot_called(S, pusher, caller, ante)
    return _allin_ev(eq, pot, S - _posted(caller), bf), tot


def pusher_ev(S, pusher, behind, call_ranges, ante=1.0, bf=1.0):
    """EV(shove) - EV(fold) for each pusher class given callers' ranges (in order)."""
    pot0 = 1.5 + ante
    ev = np.zeros(169)
    p_still = np.ones(169)                      # P(no one has called yet | pusher hand)
    rowsum = C.sum(1)
    for j, name in enumerate(behind):
        r = call_ranges[j]
        pc = (C * r[None, :]).sum(1) / rowsum   # P(this player calls | pusher hand)
        eq = (C * r[None, :] * E).sum(1) / np.maximum((C * r[None, :]).sum(1), 1e-12)
        pot = _pot_called(S, pusher, name, ante)
        ev += p_still * pc * _allin_ev(eq, pot, S - _posted(pusher), bf)
        p_still *= (1 - pc)
    ev += p_still * pot0
    return ev


def solve_spot(S, pusher, behind, ante=1.0, iters=600, bf_push=1.0, bf_call=1.0):
    """Fictitious play for one first-in shove spot. Returns (push, [calls], evs)."""
    push = np.ones(169) * 0.5
    calls = [np.ones(169) * 0.2 for _ in behind]
    for t in range(1, iters + 1):
        a = 1.0 / (t + 1)
        evp = pusher_ev(S, pusher, behind, calls, ante, bf_push)
        br_p = (evp > 0).astype(float)
        new_calls = []
        for j, name in enumerate(behind):
            evc, _ = caller_ev(S, pusher, name, push, ante, bf_call)
            new_calls.append((evc > 0).astype(float))
        push = (1 - a) * push + a * br_p
        calls = [(1 - a) * c + a * b for c, b in zip(calls, new_calls)]
    evp = pusher_ev(S, pusher, behind, calls, ante, bf_push)
    return push, calls, evp


def solve_table(S, n=8, ante=1.0, iters=600):
    """All first-in shove spots at an n-handed table. Returns dict pos -> (push, calls dict)."""
    pos = positions(n)
    out = {}
    for i, p in enumerate(pos[:-1]):
        behind = pos[i + 1:]
        push, calls, evp = solve_spot(S, p, behind, ante, iters)
        out[p] = dict(push=push, calls=dict(zip(behind, calls)), ev=evp)
    return out


def pct(r):
    return float((r * N).sum() / 1326)


def range_str(r, thr=0.5):
    return " ".join(c for c, x in zip(CLASSES, r) if x >= thr)


if __name__ == "__main__":
    # Validation: classic heads-up Nash (no ante). Published value at 10bb: SB shoves ~58%, BB calls ~37%.
    for S in (5, 10, 15, 20):
        push, calls, _ = solve_spot(S, "SB", ["BB"], ante=0.0, iters=1500)
        print(f"HU no-ante {S:>2}bb: SB push {pct(push):5.1%}  BB call {pct(calls[0]):5.1%}")
