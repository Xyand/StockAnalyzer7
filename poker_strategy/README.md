# poker_strategy

A tournament poker strategy that is easy to memorise, backed by a custom Nash solver and simulations.

* **[STRATEGY.md](STRATEGY.md)**: the system itself, a single page to memorise.
* **[METHODOLOGY.md](METHODOLOGY.md)**: how it was derived and how much EV it gives up.

```bash
pip install -r requirements.txt
python3 equity.py          # (optional, ~5 min) rebuild data/equity169.npz
python3 solve_grid.py      # (optional, ~1 min) rebuild data/nash_8max_bbante.pkl
python3 report.py          # solver validation and EV-loss numbers
python3 simulate.py 300000 # Monte Carlo table simulation (~90 s on 4 cores)
python3 icm.py             # bubble factors and ICM line shifts
python3 exploit.py         # how to adjust lines against leaky opponents
python3 cheatsheet.py      # hand lists implied by the rules
python3 quiz.py 30         # flash-card trainer
```

| File | Purpose |
|---|---|
| `hands.py` | 169 hand classes and combos |
| `equity.py` | 169×169 equity matrix with card removal (eval7 Monte Carlo) |
| `pushfold.py` | N-handed push/fold Nash solver (fictitious play, supports bubble factors) |
| `reshove.py` | Nash solver for re-shoving over an open |
| `shove_score.py` | the All-in and Open scores |
| `strategy.py` | the rules as code, the single source of truth |
| `evaluate.py`, `analyze.py` | EV-loss tools |
| `simulate.py` | real-card table simulation with over-calls |
| `icm.py`, `exploit.py` | ICM and exploit adjustments |
| `research/` | the parameter searches that produced the constants |
