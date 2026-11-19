"""Re-shove (3-bet all-in) over an open: Nash between re-shover and opener.

Opener raises to `open_size` with a fixed range (the Open Score line for his seat);
hero (behind) shoves S or folds; opener calls or folds. Players behind hero fold.
"""
import numpy as np
from pushfold import E, C, N, _posted, _allin_ev, pct
from shove_score import OPEN_SCORE, SCORE

OPEN_LINE = {"UTG": 35, "UTG1": 34, "LJ": 33, "HJ": 32, "CO": 29, "BTN": 25, "SB": 27}


def solve_reshove(S, opener, hero, open_size=2.2, ante=1.0, iters=800, open_range=None):
    O = (OPEN_SCORE >= OPEN_LINE[opener]).astype(float) if open_range is None else open_range
    dead = ante + (0.5 if "SB" not in (opener, hero) else 0) + (1.0 if "BB" not in (opener, hero) else 0)
    gain_fold = dead + open_size + _posted(hero)
    pot = 2 * S + dead
    risk_h = S - _posted(hero)
    risk_o = S - open_size
    shove = np.full(169, 0.3)
    call = np.full(169, 0.5)
    W = C * O[None, :]                         # hero hand h -> opener hand k weights
    for t in range(1, iters + 1):
        a = 1 / (t + 1)
        evh = (W * ((1 - call)[None, :] * gain_fold + call[None, :] * (E * pot - risk_h))).sum(1) / np.maximum(W.sum(1), 1e-12)
        Wo = C * shove[None, :]                # opener hand k -> hero hand h weights
        evo = (Wo * (E * pot - risk_o)).sum(1) / np.maximum(Wo.sum(1), 1e-12)
        shove = (1 - a) * shove + a * (evh > 0)
        call = (1 - a) * call + a * (evo > 0)
    evh = (W * ((1 - call)[None, :] * gain_fold + call[None, :] * (E * pot - risk_h))).sum(1) / np.maximum(W.sum(1), 1e-12)
    return shove, call * O, evh


if __name__ == "__main__":
    from evaluate import best_threshold, loss_for_range
    spots = [("UTG", "BB"), ("HJ", "BB"), ("CO", "BB"), ("BTN", "BB"), ("SB", "BB"),
             ("CO", "BTN"), ("BTN", "SB"), ("HJ", "CO"), ("UTG", "HJ")]
    print("Optimal re-shove Score line (All-in Score) | % of hands")
    print("S    " + " ".join(f"{o[:3]}>{h[:3]:<3}" for o, h in spots))
    for S in (12, 15, 18, 20, 25, 30):
        row = []
        for o, h in spots:
            sh, cl, ev = solve_reshove(S, o, h)
            t, l = best_threshold(ev, SCORE)
            row.append(f"{t:3.0f}/{pct(sh):3.0%}")
        print(f"{S:<4} " + " ".join(f"{r:>7}" for r in row))
