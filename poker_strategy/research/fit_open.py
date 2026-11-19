import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np, itertools
from hands import CLASSES, parts, NCOMBOS
from open_targets import TARGETS
N = np.array(NCOMBOS); P = [parts(c) for c in CLASSES]
T = {k: np.array([c in v for c in CLASSES]) for k, v in TARGETS.items()}

def score(A, suited, gp, pb, pm, offgap=None):
    out = []
    for hi, lo, k in P:
        h = A if hi == 14 else hi; l = lo
        if k == "p": out.append(pb + pm * h); continue
        g = min(hi - lo - 1, 4)
        pen = gp[g]
        out.append(2 * h + l + (suited if k == "s" else 0) - pen)
    return np.array(out, float)

def mismatch(sc):
    tot, ths = 0, {}
    for k, tgt in T.items():
        best = min(((N * ((sc >= t) != tgt)).sum(), t) for t in np.unique(sc))
        tot += best[0]; ths[k] = best[1]
    return tot, ths

res = []
for A in [14, 15, 16]:
  for s in [3, 4, 5, 6, 7, 8]:
    for gp in [(0,1,2,3,3),(0,1,2,3,4),(0,2,4,6,6),(0,1,3,5,6),(0,0,1,2,3),(0,1,2,4,6),(0,2,3,4,5)]:
      for pb, pm in [(26,2),(30,2),(34,2),(38,2),(30,2.5),(24,3),(40,1),(36,1.5)]:
        m, ths = mismatch(score(A, s, gp, pb, pm))
        res.append((m, A, s, gp, pb, pm, ths))
res.sort(key=lambda r: r[0])
for r in res[:6]: print(r)
print("--- unified variants")
from shove_score import SCORE
print("shove score as-is", mismatch(SCORE))
for A in [14, 15, 16]:
    for s in [3, 4, 5, 6]:
        for gp in [(0,1,2,3,3),(0,1,2,3,4),(0,1,2,4,5),(0,2,4,6,6),(0,1,3,5,6)]:
            m, th = mismatch(score(A, s, gp, 32, 2))
            if m < 240: print(m, A, s, gp, th)
