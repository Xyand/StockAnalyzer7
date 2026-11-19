"""Flash-card trainer for the strategy.  Run:  python3 quiz.py [n_questions]"""
import random, sys
from hands import CLASSES, NCOMBOS
from shove_score import score, open_score
import strategy as st

SEATS = ["UTG", "UTG1", "LJ", "HJ", "CO", "BTN", "SB"]


def deal():
    return random.choices(CLASSES, weights=NCOMBOS)[0]


def question():
    kind = random.choice(["score", "shove", "call", "reshove", "open"])
    h = deal()
    if kind == "score":
        return f"All-in Score of {h}?", str(score(h)), None
    if kind == "shove":
        seat, S = random.choice(SEATS), random.randint(5, 15)
        return (f"{S}bb, folded to you in {seat}, holding {h}. Shove? (y/n)",
                "y" if st.should_shove(h, seat, S) else "n", f"score {score(h)} vs line {st.shove_line(seat, S)}")
    if kind == "call":
        seat, S = random.choice(SEATS), random.randint(5, 15)
        return (f"{seat} shoves {S}bb, you hold {h}. Call? (y/n)",
                "y" if st.should_call(h, seat, S) else "n", f"score {score(h)} vs line {st.call_line(seat, S)}")
    if kind == "reshove":
        seat = random.choice(SEATS[:-1])
        return (f"You have 18bb. {seat} opens, you hold {h}. Re-shove? (y/n)",
                "y" if score(h) >= st.reshove_line(seat) else "n", f"score {score(h)} vs line {st.reshove_line(seat)}")
    seat = random.choice(SEATS)
    return (f"40bb, folded to you in {seat}, holding {h}. Open-raise? (y/n)",
            "y" if st.should_open(h, seat) else "n", f"open score {open_score(h)} vs line {st.OPEN_LINE[seat]}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    right = 0
    for _ in range(n):
        q, a, why = question()
        ans = input(q + " ").strip().lower()
        ok = ans == a
        right += ok
        print("  correct" if ok else f"  wrong -> {a}", f"({why})" if why else "")
    print(f"\n{right}/{n} correct")
