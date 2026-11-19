import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
from fit_score import score_fn
from evaluate import ordering_loss
res=[]
for A in [14,15,16,17,18]:
  for K in [13,14]:
    for gp in [(0,1,2,2),(0,1,2,3),(0,0,1,2)]:
      for pb,pm in [(30,2),(28,2),(32,2),(26,2.5),(20,3)]:
        for s in [2,3]:
          val={r:r for r in range(2,15)}; val[14]=A; val[13]=K
          l=ordering_loss(score_fn(2,s,gp,pb,pm,val),stacks=range(4,16,2))
          res.append((l[0],l[1],A,K,gp,pb,pm,s))
res.sort()
for r in res[:8]: print(r)
