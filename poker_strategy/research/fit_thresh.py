import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np, itertools
from shove_score import SCORE
from evaluate import loss_for_range, spot_evs
from analyze import POS
PS = POS[:-1]; ST = range(4, 16)
EV = {(S, p): spot_evs(S, p) for S in range(3, 21) for p in PS}
def L(S, p, t): return 100 * loss_for_range(EV[(S, p)], SCORE >= t)
# loss curve for threshold deviations
from evaluate import best_threshold
for d in [1, 2, 3, 4]:
    tot = np.mean([max(L(S,p,best_threshold(EV[(S,p)],SCORE)[0]+d), L(S,p,best_threshold(EV[(S,p)],SCORE)[0]-d)) for S in ST for p in PS])
    print("off by", d, "-> avg loss", round(tot, 2), "bb/100")
def evalf(f):
    return np.mean([L(S, p, f(S, p)) for S in ST for p in PS]), max(L(S, p, f(S, p)) for S in ST for p in PS)
print("per-spot optimum", evalf(lambda S, p: best_threshold(EV[(S,p)], SCORE)[0]))
# Model A: T = base[p] + min(S,10) + max(S-10,0)//2
def fitA(stackf):
    base = {}
    for p in PS:
        base[p] = min(range(0, 40), key=lambda b: sum(L(S, p, b + stackf(S)) for S in ST))
    return base, evalf(lambda S, p: base[p] + stackf(S))
for name, sf in [("min(S,10)+half above", lambda S: min(S, 10) + max(S - 10, 0) // 2),
                 ("S", lambda S: S), ("min(S,10)", lambda S: min(S, 10)),
                 ("S//2*... (S+min(S,8))//2", lambda S: (S + min(S, 8)) // 2),
                 ("buckets", lambda S: {4:0,5:4,6:6,7:7,8:8,9:9,10:9,11:10,12:10,13:10,14:11,15:11}[S])]:
    print(name, fitA(sf))
print("---- S=5..15 candidates")
ST2 = range(5, 16)
def evalf2(f):
    v = [L(S, p, f(S, p)) for S in ST2 for p in PS]
    return round(np.mean(v), 2), round(max(v), 2)
opt = evalf2(lambda S, p: best_threshold(EV[(S,p)], SCORE)[0]); print("optimum", opt)
cands = {
 "min(S,10)": lambda S: min(S, 10),
 "min(S,11)": lambda S: min(S, 11),
 "S<=10:S else 11": lambda S: S if S <= 10 else 11,
 "S<=8:S, 9-12:9.., ": lambda S: S if S <= 8 else (9 if S <= 10 else (10 if S <= 13 else 11)),
}
for name, sf in cands.items():
    base = {p: min(range(0, 40), key=lambda b: sum(L(S, p, b + sf(S)) for S in ST2)) for p in PS}
    print(name, base, evalf2(lambda S, p: base[p] + sf(S)))
