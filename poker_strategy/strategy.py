"""The memorable short-stack strategy as code (single source of truth for docs + sims)."""
from shove_score import score, open_score

SEAT = {"UTG": 27, "UTG1": 26, "UTG2": 26, "LJ": 25, "HJ": 24, "CO": 22, "BTN": 20, "SB": 13}
OPEN_LINE = {"UTG": 35, "UTG1": 34, "UTG2": 34, "LJ": 33, "HJ": 32, "CO": 29, "BTN": 25, "SB": 27}


def shove_line(seat, stack):
    """Minimum All-in Score to open-shove (folded to you)."""
    if stack <= 4:
        return 0 if seat == "SB" else 20
    return SEAT[seat] + min(stack, 10)


def call_line(shover_seat, stack):
    """Minimum All-in Score to call a shove from `shover_seat` (stack = effective)."""
    base = SEAT[shover_seat] + min(stack, 10)
    if stack <= 4:
        return 20
    return base + (-2 if stack <= 6 else (2 if stack <= 10 else 4))


def reshove_line(opener_seat):
    """Minimum All-in Score to 3-bet shove 12-25bb over an open."""
    return OPEN_LINE[opener_seat] + 5


def should_shove(hand, seat, stack):
    return score(hand) >= shove_line(seat, stack)


def should_call(hand, shover_seat, stack):
    return score(hand) >= call_line(shover_seat, stack)


def should_open(hand, seat):
    o = open_score(hand)
    if seat in ("CO", "BTN") and len(hand) == 3 and hand[2] == "s" and \
            "AKQJT98765432".index(hand[0]) + 1 == "AKQJT98765432".index(hand[1]) and hand[1] in "65432" and hand != "32s":
        return True  # low suited connectors 54s-65s from CO/BTN
    return o >= OPEN_LINE[seat]
