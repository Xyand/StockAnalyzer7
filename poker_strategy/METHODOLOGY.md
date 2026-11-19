# How the Score System was built and tested

All numbers below are reproduced by `python3 report.py`, `python3 simulate.py 300000`,
`python3 icm.py` and `python3 exploit.py`. Saved outputs are in `data/`.

## 1. Equity engine (`equity.py`)
* A 169×169 matrix of preflop all-in equities. For every hero combo against every villain class,
  we ran 20,000 Monte Carlo boards with the `eval7` C evaluator.
* Card removal is exact: the matrix stores the count of non-conflicting combo pairs, and
  the solvers use those counts as weights.
* Sanity checks: AA vs KK = 81.9% (true value 81.9%), AKo vs QQ = 43.3% (true value about 43%).

## 2. Push/fold Nash solver (`pushfold.py`, `solve_grid.py`)
* Chip-EV, 8-max, blinds 0.5/1 with a 1bb big-blind ante, equal stacks of 2–30bb.
* In each spot one player is first in and shoves. Each player behind calls or folds, and the first
  caller goes heads-up. The solver ignores over-calls; the simulation in section 6 includes them.
* We solved by fictitious play (averaged best responses).
* **Validation against the published heads-up Nash result:** at 10bb, no ante, the SB shoves
  58.3% and the BB calls 37.4%. The widely published heads-up Nash figures are about 58% and 37%.
* 8-max shove frequencies at 10bb: UTG 18%, HJ 28%, CO 33%, BTN 43%, SB 71%.
  These fit public guidance, which puts early position around 10–14% without antes and says antes
  widen ranges by 20–30%.

## 3. Finding a memorable hand ranking (`evaluate.py`, `research/fit_*.py`)
We measured each candidate ranking by its **EV loss against exact Nash**. Each spot got its best
threshold on that ranking, and we averaged the loss over every seat at 5–15bb.

| Ranking | Loss (bb per 100 spots) |
|---|---|
| Best possible single ranking (built from Nash EVs) | 0.27 |
| **All-in Score** (A=16; 2×high + low; +3 suited; −1 per gap, max −3; pairs 32 + 2r) | **0.47** |
| Chen formula | 3.86 |

* We grid-searched the score's parameters: the value of the ace, the suited bonus, the gap
  penalty and the pair formula.
* Counting the ace as 16 was the biggest single improvement. A loss of 1.04 dropped to 0.41.
* The same score also gives a good ordering for calling: 0.43 with optimal lines.

## 4. Turning thresholds into a formula
* The best line for each spot fits well as `Seat number + min(stack, 10)`. Average loss is 0.75
  and the worst spot loses 4.4, at 5bb UTG.
* Missing the best line by one point costs about 0.8 bb/100, so the formula's rounding is cheap.
* Call lines came out as roughly the shover's own line + 2, so rule B is anchored to the
  shover's line. The fitted offsets are −2 at ≤6bb, +2 at 7–10bb and +4 at 11–15bb.
  Average loss is 1.12, against 0.43 with a perfect line in every spot.

## 5. Deeper stacks
* **Re-shove (`reshove.py`):** a two-player Nash between the opener, who raises to 2.2× with their
  Open-line range, and a re-shover at 12–30bb.
  * The rule "opener's Open line + 5" loses 1.01 bb/100. The best line in each spot would lose 0.53.
  * A refinement brings the loss down to 0.70: use +4, use +6 against BTN or SB opens, and add 1 above 20bb.
* **Open ranges:** we did not solve postflop play here, because that needs a full solver tree.
  * Instead, we used published chip-EV MTT solver frequencies (with BB ante) as targets:
    EP about 15–18%, HJ about 24%, CO about 31%, BTN about 46%.
    Sources: Poker Academy MTT charts, which give 15.6/31.2/41.5% EP/CO/BTN at 20bb with a 1bb ante,
    and GTO-style MTT RFI charts, which give UTG 11–15% and BTN about 47.5% with ante.
  * We encoded solver-shaped reference ranges in `open_targets.py` and grid-searched
    a score that reproduces them.
  * Doubling the suited bonus and the gap penalty gave the best fit while keeping the same base
    formula. It mismatches about 12% of combos, almost all of them borderline hands.
* **BB defence and deep 3-bets:** these follow published solver tendencies and pot odds.
  They are not computed here, and are labelled that way in STRATEGY.md.

## 6. Table simulation (`simulate.py`)
* Real cards (eval7), 8-max, BB ante, with stacks of 5, 8, 10, 12 and 15bb.
* Over-calls are allowed: a player behind a caller needs to clear their line by 10 points.
* We replayed the same deals with the hero playing either the Nash ranges or the Score rules,
  so the comparison uses common random numbers. Each field got 300,000 hands per stack depth.

| Field | Nash hero | Score-rules hero | Difference |
|---|---|---|---|
| Nash bots | +0.29 | +1.48 | **+1.20 ± 0.19** |
| Nits (shove +6 tight, call +6 tight) | +2.89 | +4.56 | **+1.67 ± 0.14** |
| Calling stations (call 8 points loose) | +9.60 | +11.60 | **+2.00 ± 0.19** |
| Maniacs (shove 8 loose, call 4 loose) | +2.91 | +3.16 | **+0.25 ± 0.16** |

Results are in bb/100 hands. The Score rules beat the solver's own ranges. The main reason is
that the no-over-call model makes Nash too loose from early position at short stacks, where
multiway pots are common. The tighter formula lines happen to correct for that.

## 7. ICM (`icm.py`)
* We computed Malmuth-Harville ICM and bubble factors. With 4 players left, 3 paid
  (50/30/20) and equal stacks, the bubble factor is 1.87.
* We re-solved push/fold with losses weighted by the bubble factor. The best lines moved like this:

| Bubble factor (shover / caller) | Shove line | Call line |
|---|---|---|
| 1.3 / 1.3 | +1.0 | +5.6 |
| 1.5 / 1.5 | −0.6 | +8.1 |
| 2.0 / 2.0 | −4.1 | +13.4 |
| 1.1 / 1.6 (you are the big stack shoving) | −6.6 | +4.4 |
| 1.6 / 1.1 (you are the medium stack, big stack behind) | +4.9 | +6.9 |

## 8. Exploits (`exploit.py`)
* Callers who are 4 to 8 points too tight: the best response shoves 13 to 22 points wider.
* Callers who are too loose: the shove line barely moves.
* A shover who is k points off the rule: move your call line by about k.

## Limitations
* Push/fold is chip-EV and assumes equal stacks. With unequal stacks, use the effective stack.
* Between 12 and 20bb, real solvers also use min-raises, which this system replaces with
  pure shoves and re-shoves. That costs a little EV but is far simpler.
* The postflop advice is general solver lore, not output from this repository.
