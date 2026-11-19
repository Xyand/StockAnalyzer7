import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
from hands import CLASSES, parts
from evaluate import best_threshold
import fit_call as fc
P=[parts(c) for c in CLASSES]
def cs(A, s, g, pb=32, pm=2):
    V={r:r for r in range(2,15)}; V[14]=A
    return np.array([pb+pm*V[h] if k=='p' else 2*V[h]+V[l]+(s if k=='s' else 0)-g*min(h-l-1,3) for h,l,k in P],float)
for A in [14,15,16,17]:
  for s in [0,1,2]:
    for g in [0,1]:
      for pb in [30,32,34]:
        sc=cs(A,s,g,pb)
        print(A,s,g,pb, round(np.mean([best_threshold(fc.EV[k],sc)[1] for k in fc.spots])*100,3))
