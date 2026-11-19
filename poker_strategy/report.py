"""Reproduce every number quoted in STRATEGY.md / METHODOLOGY.md."""
import numpy as np
from hands import CLASSES
from pushfold import pct, solve_spot, caller_ev, N
from analyze import RES, POS
from shove_score import SCORE
from evaluate import spot_evs, loss_for_range, best_threshold, chen, ordering_loss
import strategy as st

print("== Solver validation (heads-up, no ante; published Nash @10bb: SB ~58%, BB ~37%)")
p, c, _ = solve_spot(10, "SB", ["BB"], ante=0.0, iters=1500)
print(f"   SB shove {pct(p):.1%}   BB call {pct(c[0]):.1%}")

print("\n== 8-max Nash shove % (BB ante 1bb)  vs  simple-rule shove %")
print("S    " + "  ".join(f"{q:>9}" for q in POS[:-1]))
for S in (5, 8, 10, 12, 15):
    row = []
    for q in POS[:-1]:
        rule = np.array([st.should_shove(h, q, S) for h in CLASSES], float)
        row.append(f"{pct(RES[(S, q)]['push']):3.0%}/{pct(rule):3.0%}")
    print(f"{S:<4} " + "  ".join(f"{r:>9}" for r in row))

ST = range(5, 16)
sh = [100 * loss_for_range(spot_evs(S, q), np.array([st.should_shove(h, q, S) for h in CLASSES])) for S in ST for q in POS[:-1]]
ch_sc = np.array([chen(h) for h in CLASSES])
chen_l = [100 * best_threshold(spot_evs(S, q), ch_sc)[1] for S in ST for q in POS[:-1]]
nash_rank = sum(spot_evs(S, q) / S for S in ST for q in POS[:-1])
print("\n== EV loss vs exact Nash, bb per 100 folded-to spots, stacks 5-15bb, all seats")
print(f"   Simple shove rule (formula lines):           {np.mean(sh):.2f}  (worst spot {max(sh):.2f})")
print(f"   All-in Score w/ per-spot optimal line:       {ordering_loss(SCORE, ST)[0]:.2f}")
print(f"   Best possible single hand ranking:           {ordering_loss(nash_rank, ST)[0]:.2f}")
print(f"   Chen formula w/ per-spot optimal line:       {np.mean(chen_l):.2f}")

cl = []
for S in ST:
    for q in POS[:-1]:
        for cc in POS[POS.index(q) + 1:]:
            ev = caller_ev(S, q, cc, RES[(S, q)]["push"])[0]
            cl.append(100 * loss_for_range(ev, np.array([st.should_call(h, q, S) for h in CLASSES])))
print(f"   Simple call rule:                            {np.mean(cl):.2f}  (worst spot {max(cl):.2f})")

from reshove import solve_reshove
spots = [("UTG", "BB"), ("HJ", "BB"), ("CO", "BB"), ("BTN", "BB"), ("SB", "BB"), ("CO", "BTN"), ("BTN", "SB"), ("HJ", "CO"), ("UTG", "HJ")]
rl, ro = [], []
for S in (12, 15, 18, 20, 25):
    for o, h in spots:
        ev = solve_reshove(S, o, h, iters=500)[2]
        rl.append(100 * loss_for_range(ev, SCORE >= st.reshove_line(o)))
        ro.append(100 * best_threshold(ev, SCORE)[1])
print(f"   Re-shove rule (open line +5), 12-25bb:       {np.mean(rl):.2f}  (per-spot optimal line {np.mean(ro):.2f})")
