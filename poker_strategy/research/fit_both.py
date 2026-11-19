import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fit_open import score, mismatch
from evaluate import ordering_loss
res=[]
for A in [14,15,16]:
  for s in [3,4]:
    for gp in [(0,1,2,3,3),(0,2,4,6,6),(0,1,3,5,6),(0,2,3,4,4),(0,1,2,4,4)]:
      sc=score(A,s,gp,32,2)
      res.append((mismatch(sc)[0], round(ordering_loss(sc,stacks=range(4,16,2))[0],2), A,s,gp))
for r in sorted(res, key=lambda r: r[0]/200 + r[1]/0.4): print(r)
