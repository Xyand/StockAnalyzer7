import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np, itertools
from hands import CLASSES, parts
from evaluate import ordering_loss, spot_evs
from analyze import POS
P = [parts(c) for c in CLASSES]
EVS = None

def score_fn(a, suited, gap_pen, pair_base, pair_mult, val=None):
    val = val or {r: r for r in range(2, 15)}
    out = []
    for hi, lo, k in P:
        if k == "p":
            out.append(pair_base + pair_mult * val[hi])
        else:
            g = min(hi - lo - 1, 3)
            out.append(a * val[hi] + val[lo] + (suited if k == "s" else 0) - gap_pen[g])
    return np.array(out, float)

best = None
for a in [1, 1.5, 2, 3]:
  for s in [1, 2, 3, 4]:
    for gp in [(0,0,0,0),(0,1,2,3),(0,0,1,2),(0,1,1,2),(0,1,2,2)]:
      for pb in [10, 15, 20, 25, 30]:
        for pm in [1, 2, 3]:
            sc = score_fn(a, s, gp, pb, pm)
            l = ordering_loss(sc, stacks=range(4, 16, 2))
            if best is None or l[0] < best[0][0]:
                best = (l, a, s, gp, pb, pm); print(best, flush=True)
