"""Helpers to load the Nash grid and derive per-hand max shove/call stacks."""
import pickle, numpy as np
from hands import CLASSES

D = pickle.load(open(__file__.rsplit("/", 1)[0] + "/data/nash_8max_bbante.pkl", "rb"))
STACKS, POS, RES = D["stacks"], D["positions"], D["res"]


def max_push(p):
    """Largest stack (bb) at which each class is a Nash shove from p (0 if never)."""
    T = np.zeros(169)
    for S in STACKS:
        T = np.where(RES[(S, p)]["push"] >= 0.5, S, T)
    return T


def max_call(pusher, caller):
    T = np.zeros(169)
    for S in STACKS:
        T = np.where(RES[(S, pusher)]["calls"][caller] >= 0.5, S, T)
    return T
