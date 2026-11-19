# The Score System: an MTT strategy you can memorise

This system covers No-Limit Hold'em tournaments, 8-max, with a big-blind ante.
You memorise **one way to score a hand** and **one short list of numbers**.
Everything here comes from our own Nash solver and simulations; see
[METHODOLOGY.md](METHODOLOGY.md). Every number can be reproduced with `python3 report.py`.

---

## 1. Score your hand

| Card  | A  | K  | Q  | J  | T  | 9…2        |
|-------|----|----|----|----|----|------------|
| Value | **16** | 13 | 12 | 11 | 10 | face value |

**All-in Score** (use this for every shove or call):

* **Unpaired:** `2 × high + low`, then **+3 if suited** and **−1 per gap**
  (maximum −3). A gap is a missing rank between your cards: KQ = 0, KJ = 1, K9 = 3+.
* **Pairs:** `32 + 2 × rank`. So 22 = 36, 55 = 42, TT = 52, AA = 64.

**Open Score** (use this only when you open-raise or defend with 25bb or more): same base,
but suitedness and connectedness **count double**: **+6 suited, −2 per gap (maximum −8)**.

| Hand | AKo | AJo | A5s | A2o | KQo | K9s | QJs | T9s | 76s | 55 | 22 | 72o |
|------|-----|-----|-----|-----|-----|-----|-----|-----|-----|----|----|-----|
| All-in | 45 | 41 | 37 | 31 | 38 | 35 | 38 | 32 | 23 | 42 | 36 | 13 |
| Open   | 45 | 39 | 35 | 26 | 38 | 35 | 41 | 35 | 26 | 42 | 36 | 8 |

---

## 2. The numbers to memorise

| Seat | UTG | UTG1 | LJ | HJ | CO | BTN | SB |
|---|---|---|---|---|---|---|---|
| **Seat number** (shoving) | 27 | 26 | 25 | 24 | 22 | 20 | 13 |
| **Open line** (raising)   | 35 | 34 | 33 | 32 | 29 | 25 | 27 |

Mnemonic: each early seat is one less than the seat before (27-26-25-24 and 35-34-33-32).
Then **CO, BTN, SB = 22-20-13** for shoving and **29-25-27** for opening.
At 9-handed, treat the extra early seat as UTG.

"Stack" always means the **effective stack** in big blinds: the smaller of your stack and the
biggest stack that can still act behind you.

---

## 3. The rules

### A. Folded to you, 15bb or less: shove or fold
> **Shove if All-in Score ≥ Seat number + stack** (count the stack as 10 when it is above 10bb).

* At 10bb on the button the line is 20 + 10 = 30, so A2o (31), K8o (31) and T9s (32) are shoves and Q7o (28) is a fold.
* At 4bb or less: shove anything with Score 20 or more from any seat. From the SB, shove any two cards.

### B. Facing an all-in: call or fold
> **Work out the shover's line (their Seat number + stack), then adjust it:**
> **−2 at 6bb or less · +2 at 7–10bb · +4 at 11–15bb**

* Example: the button shoves 10bb and you are in the big blind. The line is 20 + 10 + 2 = 32.
  Call with K9s (35) and 22 (36). Fold A2o (31).
* If someone has already called the shove, add another +10.

### C. 15–25bb, someone opened before you: re-shove or fold
> **Re-shove if All-in Score ≥ the opener's Open line + 5.**

* The CO opens and you hold 18bb. The line is 29 + 5 = 34, so you shove K9s (35), A7o and 22, and fold QTo.

### D. 25bb or more, folded to you: open-raise
> **Open-raise if Open Score ≥ your Open line.** Also open 54s and 65s from the CO and BTN.

* Sizing: 2.2× (2× when you have under 30bb). From the SB, raise to 3× or fold.

### E. 25bb or more, big blind facing a min-raise
> **Defend (call or 3-bet) if Open Score ≥ the opener's Open line − 8.**
> That defends roughly 37% against UTG, 59% against CO and 70–78% against BTN or SB.

### F. Deep 3-bets (30bb or more), raise to about 3× the open
* **For value:** JJ+, AK. Against CO, BTN or SB opens, also TT, AQ, AJs and KQs.
* **As a bluff from the blinds against late opens:** A5s–A2s. Fold to a 4-bet.
* Below 25bb, use rule C (re-shove) instead of small 3-bets.

---

## 4. Adjustments

| Situation | Shove line | Call line |
|---|---|---|
| Bubble or pay jump, everyone at risk (bubble factor ≈ 1.5) | no change | **+8** |
| Hard bubble or final table with a medium stack (bubble factor ≈ 2) | no change | **+13** |
| Deep in the money, small pay jumps (bubble factor ≈ 1.3) | no change | **+5** |
| You cover everyone left to act (when you call, a medium stack has shoved into you) | **−6** | +7 |
| A bigger stack that covers you is still to act (when you call, that stack has shoved into you) | **+5** | +4 |
| The players behind call too little (nits) | **−10 or more** | — |
| The players behind call too much (stations) | about 0. Do not tighten up. | — |
| The shover is tighter or looser than the rules | — | move your line **by the same amount** |

The two adjustments that matter most:
1. On the bubble, **calling** tightens a lot and **shoving** hardly changes.
2. Against fields that fold too much, shove much wider. Against fields that call too much,
   keep your shoving lines and enjoy the calls.

---

## 5. Post-flop rules of thumb (from public solver studies; we did not compute these)
1. As the preflop raiser, **c-bet small (about ⅓ pot) often** on dry, high-card boards (A-high or K-high).
   **Check more** on low, connected boards, especially out of position.
2. Facing a bet, **defend at least**: 75% of your range against a ⅓-pot bet, 67% against
   a ½-pot bet and 50% against a pot-sized bet. Fold more only against players who never bluff.
3. On the turn and river, **bet big with strong hands and your best draws, and check your medium hands.**
4. When the stack-to-pot ratio is 3 or less and you have top pair or better, you are committed: get it in.

---

## 6. How strong is this?

| Strategy (all seats, 5–15bb) | EV lost vs exact Nash (bb per 100 spots) |
|---|---|
| Exact Nash ranges (169 hands × 7 seats × 11 stacks) | 0 |
| **Score system, shoving (rule A)** | **0.75** |
| **Score system, calling (rule B)** | **1.12** |
| **Score system, re-shove (rule C)** | **1.01** |
| Chen formula, even with a perfect line for every spot | 3.86 |

We also ran a table simulation with real cards and over-calls allowed, 1.5M hands per field.
**In every field we tested, the Score system did as well as or better than playing the solver's own
ranges**: +1.2 bb/100 against a Nash field, +1.7 against nits, +2.0 against calling stations,
and +0.25 against maniacs. See [METHODOLOGY.md](METHODOLOGY.md) for details.

Practice with: `python3 quiz.py 30`
