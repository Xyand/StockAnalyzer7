"""ICM (Malmuth-Harville), bubble factors, and how they shift the Score lines."""
import numpy as np
from functools import lru_cache
from pushfold import solve_spot, pusher_ev, caller_ev, positions
from shove_score import SCORE
from evaluate import best_threshold


def icm(stacks, payouts):
    stacks = tuple(float(s) for s in stacks)
    payouts = tuple(payouts) + (0,) * (len(stacks) - len(payouts))

    @lru_cache(None)
    def rec(alive, place):
        if place >= len(payouts) or payouts[place] == 0 or not alive:
            return np.zeros(len(stacks))
        tot = sum(stacks[i] for i in alive)
        out = np.zeros(len(stacks))
        for i in alive:
            p = stacks[i] / tot
            out[i] += p * payouts[place]
            out += p * rec(tuple(j for j in alive if j != i), place + 1)
        return out

    return rec(tuple(range(len(stacks))), 0)


def bubble_factor(stacks, payouts, hero, villain):
    """$ lost when hero loses an all-in vs villain / $ won when hero wins it."""
    base = icm(stacks, payouts)
    risk = min(stacks[hero], stacks[villain])
    win, lose = list(stacks), list(stacks)
    win[hero] += risk; win[villain] -= risk
    lose[hero] -= risk; lose[villain] += risk
    g = icm(win, payouts)[hero] - base[hero]
    l = base[hero] - icm(lose, payouts)[hero]
    return l / g


def threshold_shift(S=10, n=8, bf_push=1.5, bf_call=1.5, ante=1.0):
    """Average change of the optimal Score line (shove and BB-call) vs chip EV."""
    pos = positions(n)
    dsh, dca = [], []
    for i, p in enumerate(pos[:-1]):
        behind = pos[i + 1:]
        base = solve_spot(S, p, behind, ante, 400)
        icmr = solve_spot(S, p, behind, ante, 400, bf_push, bf_call)
        t0 = best_threshold(base[2], SCORE)[0]
        t1 = best_threshold(icmr[2], SCORE)[0]
        c0 = best_threshold(caller_ev(S, p, "BB", base[0], ante)[0], SCORE)[0]
        c1 = best_threshold(caller_ev(S, p, "BB", icmr[0], ante, bf_call)[0], SCORE)[0]
        dsh.append(t1 - t0); dca.append(c1 - c0)
    return np.mean(dsh), np.mean(dca)


if __name__ == "__main__":
    pay = [50, 30, 20]
    print("Bubble factors, 4-left 3-paid (50/30/20), stacks in bb:")
    for st in ([10, 10, 10, 10], [30, 20, 10, 5], [40, 15, 15, 10]):
        print(" stacks", st, "BF hero0 vs others:",
              [round(bubble_factor(st, pay, 0, j), 2) for j in range(1, 4)],
              " BF hero2 vs 0:", round(bubble_factor(st, pay, 2, 0), 2))
    print("\nScore-line shift at 10bb (avg over positions):")
    for bp, bc, name in [(1.3, 1.3, "mild ICM (deep in money / early bubble)"),
                         (1.5, 1.5, "bubble, equal stacks"),
                         (2.0, 2.0, "tight bubble / final table, medium stacks"),
                         (1.1, 1.6, "you are big stack, they are medium"),
                         (1.6, 1.1, "you are medium, big stack behind")]:
        s, c = threshold_shift(10, 8, bp, bc)
        print(f"  BF push {bp} / call {bc}  ({name}): shove line {s:+.1f}, call line {c:+.1f}")
