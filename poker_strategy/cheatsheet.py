"""Print the hand lists implied by the rules (for players who prefer charts)."""
from hands import CLASSES
from pushfold import pct
import numpy as np
import strategy as st
from shove_score import score

def lst(f):
    hs = [h for h in CLASSES if f(h)]
    return f"{pct(np.array([f(h) for h in CLASSES], float)):4.0%}  " + " ".join(hs)

if __name__ == "__main__":
    for S in (5, 8, 10):
        print(f"\n### Open-shove ranges at {S}bb")
        for seat in ["UTG", "UTG1", "LJ", "HJ", "CO", "BTN", "SB"]:
            print(f"{seat:>4} (line {st.shove_line(seat, S)}): " + lst(lambda h: st.should_shove(h, seat, S)))
    print("\n### Open-raise ranges (25bb+)")
    for seat in ["UTG", "UTG1", "LJ", "HJ", "CO", "BTN", "SB"]:
        print(f"{seat:>4} (line {st.OPEN_LINE[seat]}): " + lst(lambda h: st.should_open(h, seat)))
