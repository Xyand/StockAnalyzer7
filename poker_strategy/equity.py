"""Build the 169x169 preflop all-in equity matrix (with card-removal combo counts).

E[i, j] = equity of class i vs class j, averaged over all non-conflicting combo pairs.
C[i, j] = number of non-conflicting combo pairs (used as weights in solvers).
Monte Carlo via eval7 (C implementation). ~20k boards per hero combo/villain class.
"""
import sys
import numpy as np
import eval7
from multiprocessing import Pool
from hands import CLASSES, combos

ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 20000


def row(i):
    hero = [tuple(eval7.Card(c) for c in hc) for hc in combos(CLASSES[i])]
    vill_all = [[tuple(eval7.Card(c) for c in vc) for vc in combos(lbl)] for lbl in CLASSES]
    E = np.zeros(169)
    C = np.zeros(169)
    for j in range(169):
        tot_eq, tot_n = 0.0, 0
        for h in hero:
            hs = set(str(c) for c in h)
            vr = [(v, 1.0) for v in vill_all[j] if not (hs & set(str(c) for c in v))]
            if not vr:
                continue
            eq = eval7.py_hand_vs_range_monte_carlo(list(h), vr, [], ITERS)
            tot_eq += eq * len(vr)
            tot_n += len(vr)
        C[j] = tot_n
        E[j] = tot_eq / tot_n if tot_n else 0.5
    return i, E, C


if __name__ == "__main__":
    E = np.zeros((169, 169))
    C = np.zeros((169, 169))
    with Pool() as p:
        for i, e, c in p.imap_unordered(row, range(169)):
            E[i], C[i] = e, c
            print(i, CLASSES[i], flush=True)
    # symmetrise MC noise: E[i,j] + E[j,i] should be 1
    E = 0.5 * (E + (1 - E.T))
    np.fill_diagonal(E, 0.5)
    np.savez_compressed("data/equity169.npz", E=E, C=C, classes=np.array(CLASSES))
    print("AA vs KK", E[0, CLASSES.index("KK")], "AKo vs QQ", E[CLASSES.index("AKo"), CLASSES.index("QQ")])
