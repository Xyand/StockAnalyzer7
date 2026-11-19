"""Solve 8-max push/fold Nash (BB ante 1bb) for stacks 2..30bb and store results."""
import numpy as np, pickle
from multiprocessing import Pool
from pushfold import solve_spot, positions

N_PLAYERS = 8
STACKS = list(range(2, 31))
ANTE = 1.0


def job(args):
    S, i = args
    pos = positions(N_PLAYERS)
    p, behind = pos[i], pos[i + 1:]
    push, calls, ev = solve_spot(S, p, behind, ANTE, iters=500)
    return S, p, push, dict(zip(behind, calls)), ev


if __name__ == "__main__":
    jobs = [(S, i) for S in STACKS for i in range(N_PLAYERS - 1)]
    res = {}
    with Pool() as pool:
        for S, p, push, calls, ev in pool.imap_unordered(job, jobs):
            res[(S, p)] = dict(push=push, calls=calls, ev=ev)
    with open("data/nash_8max_bbante.pkl", "wb") as f:
        pickle.dump(dict(stacks=STACKS, positions=positions(N_PLAYERS), res=res, ante=ANTE), f)
    print("done", len(res))
