import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
from shove_score import SCORE
from evaluate import loss_for_range, best_threshold
from analyze import POS, RES
from pushfold import caller_ev
PS = POS[:-1]
def cev(S, p, c):
    return caller_ev(S, p, c, RES[(S, p)]["push"])[0]
spots = [(S, p, c) for S in range(5, 16) for p in PS for c in POS[POS.index(p)+1:]]
EV = {k: cev(*k) for k in spots}
def L(k, t): return 100 * loss_for_range(EV[k], SCORE >= t)
# ordering quality for calls
opt = {k: best_threshold(EV[k], SCORE) for k in spots}
print("call w/ SCORE ordering, per-spot opt thresholds: avg loss", np.mean([v[1] for v in opt.values()])*100)
nash_call_rank = sum(EV[k] / k[0] for k in spots)
print("call w/ single nash call ordering:", np.mean([best_threshold(EV[k], nash_call_rank)[1] for k in spots])*100)
print("BB call thresholds (score)")
print("S   " + " ".join(f"{p:>5}" for p in PS))
for S in range(5, 16):
    print(f"{S:<3} " + " ".join(f"{opt[(S,p,'BB')][0]:5.0f}" for p in PS))
print("thresholds by caller vs BTN shove, S=10:", {c: opt[(10,'BTN',c)][0] for c in ['SB','BB']})
print("vs UTG shove S=10:", {c: opt[(10,'UTG',c)][0] for c in POS[1:]})
print("vs CO shove S=10:", {c: opt[(10,'CO',c)][0] for c in POS[5:]})
SEAT = {'UTG': 27, 'UTG1': 26, 'LJ': 25, 'HJ': 24, 'CO': 22, 'BTN': 20, 'SB': 13}
def ev_rule(f):
    v = [L(k, f(*k)) for k in spots]
    vbb = [L(k, f(*k)) for k in spots if k[2] == 'BB']
    return round(np.mean(v), 2), round(np.mean(vbb), 2), round(max(v), 2)
print("optimum", round(np.mean([v[1] for v in opt.values()])*100, 2))
for name, f in {
  "seat+min(S,10)+2": lambda S, p, c: SEAT[p] + min(S, 10) + 2,
  "seat+min(S,10)+2, nonBB+1": lambda S, p, c: SEAT[p] + min(S, 10) + 2 + (c != 'BB'),
  "seat+min(S,10)+2 +SB shover+2": lambda S, p, c: SEAT[p] + min(S, 10) + 2 + 2*(p=='SB'),
  "seat+min(S,12)+2": lambda S, p, c: SEAT[p] + min(S, 12) + 2,
  "seat+min(S,12)+2+SB2+nonBB1": lambda S, p, c: SEAT[p] + min(S, 12) + 2 + 2*(p=='SB') + (c != 'BB'),
  "seat+min(S,12)+2+SB2": lambda S, p, c: SEAT[p] + min(S, 12) + 2 + 2*(p=='SB'),
  "seat+S//...: seat+min(S,10)+3": lambda S, p, c: SEAT[p] + min(S, 10) + 3,
}.items():
    print(name, ev_rule(f))
print("--- fit A_call(S) given SEAT, BB caller weighted all")
A = {}
for S in range(5, 16):
    ks = [k for k in spots if k[0] == S]
    A[S] = min(range(-10, 25), key=lambda a: sum(L(k, SEAT[k[1]] + a) for k in ks))
print(A)
print("fitted A", ev_rule(lambda S, p, c: SEAT[p] + A[S]))
print("A=S+2 capped 14", ev_rule(lambda S, p, c: SEAT[p] + min(S + 2, 14)))
print("A=S+2 capped 13", ev_rule(lambda S, p, c: SEAT[p] + min(S + 2, 13)))
print("A = 12 (S>=8) else S+3", ev_rule(lambda S, p, c: SEAT[p] + (min(S, 10) + 2 if S >= 6 else S - 1)))
def d(S): return -2 if S <= 6 else (2 if S <= 10 else 4)
print("shoveline + d", ev_rule(lambda S, p, c: SEAT[p] + min(S, 10) + d(S)))
def d2(S): return -2 if S <= 6 else (2 if S <= 10 else 3)
print("shoveline + d2", ev_rule(lambda S, p, c: SEAT[p] + min(S, 10) + d2(S)))
