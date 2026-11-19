"""The memorable hand score used for every preflop decision.

    Card values: A=16, K=13, Q=12, J=11, T=10, 9..2 face value.
    Unpaired:    2 x high card + low card, +3 if suited, -1 per gap (max -3).
    Pairs:       32 + 2 x rank   (22=36, 77=46, TT=52, AA=64).
"""
import numpy as np
from hands import CLASSES, parts

VAL = {r: r for r in range(2, 15)}
VAL[14] = 16


def score(label):
    hi, lo, k = parts(label)
    if k == "p":
        return 32 + 2 * VAL[hi]
    gap = min(hi - lo - 1, 3)
    return 2 * VAL[hi] + VAL[lo] + (3 if k == "s" else 0) - gap


shove_score = score
SCORE = np.array([score(c) for c in CLASSES], float)


def open_score(label):
    """Deep-stack opening: suited bonus doubled (+6), gaps cost 2 each (max -8)."""
    hi, lo, k = parts(label)
    if k == "p":
        return 32 + 2 * VAL[hi]
    gap = min(hi - lo - 1, 4)
    return 2 * VAL[hi] + VAL[lo] + (6 if k == "s" else 0) - 2 * gap


OPEN_SCORE = np.array([open_score(c) for c in CLASSES], float)
