"""EV-loss evaluation of simplified (score-threshold) strategies vs Nash."""
import numpy as np
from hands import CLASSES, parts
from pushfold import N, pusher_ev, caller_ev
from analyze import RES, POS, STACKS


def spot_evs(S, p):
    r = RES[(S, p)]
    behind = POS[POS.index(p) + 1:]
    return pusher_ev(S, p, behind, [r["calls"][b] for b in behind])


def loss_for_range(ev, rng):
    """bb lost per dealt hand vs best response, playing range `rng` (bool) instead."""
    best = (N * np.maximum(ev, 0)).sum() / 1326
    got = (N * ev * rng).sum() / 1326
    return best - got


def best_threshold(ev, score):
    """Threshold on score maximising EV; returns (threshold, loss)."""
    best_t, best_l = None, 1e9
    for t in np.unique(score):
        l = loss_for_range(ev, score >= t)
        if l < best_l:
            best_t, best_l = t, l
    return best_t, best_l


def ordering_loss(score, stacks=range(4, 16), pos=None):
    """Average loss (bb/100 hands dealt into each spot) with optimal per-spot thresholds."""
    pos = pos or POS[:-1]
    ls = [best_threshold(spot_evs(S, p), score)[1] for S in stacks for p in pos]
    return 100 * np.mean(ls), 100 * np.max(ls)


def chen(label):
    hi, lo, k = parts(label)
    pts = {14: 10, 13: 8, 12: 7, 11: 6}.get(hi, hi / 2)
    if k == "p":
        return max(pts * 2, 5)
    s = pts + (2 if k == "s" else 0)
    gap = hi - lo - 1
    s -= [0, 1, 2, 4, 5, 5, 5, 5, 5, 5, 5, 5][gap]
    if gap <= 1 and hi < 12:
        s += 1
    return np.ceil(s)


if __name__ == "__main__":
    nash_rank = sum(spot_evs(S, p) / S for S in range(4, 16) for p in POS[:-1])
    print("Nash single ordering:", ordering_loss(nash_rank))
    print("Chen formula       :", ordering_loss(np.array([chen(c) for c in CLASSES])))
    sb = RES[(10, "SB")]["ev"]
    print("HU SB-10bb ordering:", ordering_loss(sb))
    print("Nash per-spot (0)  :", 0)
