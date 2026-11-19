"""Reference RFI (raise-first-in) ranges, 8-max MTT, ~25-40bb, big-blind ante.

These encode the *shape* of published chip-EV solver opening ranges
(frequencies cross-checked against Poker Academy / GTO-style MTT charts:
EP ~15-18%, HJ ~24%, CO ~30-33%, BTN ~45-48%). Mixed-frequency hands are
rounded to the nearest pure action. Used only as a fitting target for the
memorable Open Score -- they are not solver output produced by this repo.
"""
from hands import CLASSES, parts, NCOMBOS

def expand(spec):
    """Tiny range parser: '22+', 'A2s+', 'ATo+', 'K9s+', '98s', 'T8s+' (kicker up to hi-1)."""
    out = set()
    R = "23456789TJQKA"
    for tok in spec.split():
        plus = tok.endswith("+"); tok = tok.rstrip("+")
        if len(tok) == 2 and tok[0] == tok[1]:
            start = R.index(tok[0])
            for r in (R[start:] if plus else tok[0]):
                out.add(r + r)
            continue
        hi, lo, k = tok[0], tok[1], tok[2]
        los = R[R.index(lo):R.index(hi)] if plus else lo
        for l in los:
            out.add(hi + l + k)
    bad = out - set(CLASSES)
    assert not bad, bad
    return out

TARGETS = {
    "UTG": "33+ A3s+ ATo+ K9s+ KJo+ QTs+ QJo JTs T9s",
    "HJ":  "22+ A2s+ A9o+ K8s+ KTo+ Q9s+ QTo+ J9s+ JTo T9s 98s 87s 76s",
    "CO":  "22+ A2s+ A7o+ K5s+ K9o+ Q8s+ QTo+ J8s+ J9o+ T8s+ T9o 97s+ 86s+ 75s+ 65s 54s",
    "BTN": "22+ A2s+ A2o+ K2s+ K7o+ Q4s+ Q9o+ J6s+ J9o+ T6s+ T8o+ 96s+ 98o 85s+ 74s+ 64s+ 53s+ 43s",
}
TARGETS = {k: expand(v) for k, v in TARGETS.items()}

if __name__ == "__main__":
    for k, v in TARGETS.items():
        print(k, f"{sum(NCOMBOS[CLASSES.index(c)] for c in v)/1326:.1%}")
