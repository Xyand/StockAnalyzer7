Exploratory fitting scripts, run from this folder (`python3 research/fit_thresh.py` also works). They
print the search tables that produced the constants in `strategy.py` / `shove_score.py`.
Some import each other and run their search when imported, so they are slow and verbose
by design. The final, verified numbers are in `../report.py`.
