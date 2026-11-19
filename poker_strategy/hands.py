"""169 starting-hand classes and combo helpers."""
import itertools

RANKS = "AKQJT98765432"
SUITS = "shdc"


def hand_classes():
    """Return the 169 class labels ordered pairs, suited, offsuit by rank."""
    out = []
    for i, r1 in enumerate(RANKS):
        for j, r2 in enumerate(RANKS):
            if i == j:
                out.append(r1 + r2)
            elif i < j:
                out.append(r1 + r2 + "s")
                out.append(r1 + r2 + "o")
    return out


CLASSES = hand_classes()
INDEX = {c: k for k, c in enumerate(CLASSES)}


def combos(label):
    """All specific 2-card combos (as string pairs) for a class label."""
    r1, r2 = label[0], label[1]
    if len(label) == 2:
        return [(r1 + a, r2 + b) for a, b in itertools.combinations(SUITS, 2)]
    if label[2] == "s":
        return [(r1 + s, r2 + s) for s in SUITS]
    return [(r1 + a, r2 + b) for a in SUITS for b in SUITS if a != b]


NCOMBOS = [len(combos(c)) for c in CLASSES]


def rank_val(ch):
    return 14 - RANKS.index(ch)


def parts(label):
    """(high rank value, low rank value, kind) with kind in {'p','s','o'}."""
    hi, lo = rank_val(label[0]), rank_val(label[1])
    kind = "p" if len(label) == 2 else label[2]
    return hi, lo, kind
