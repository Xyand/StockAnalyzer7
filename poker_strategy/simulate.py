"""Monte Carlo table simulation (real cards, eval7) of push/fold play.

Each hand: 8 players, everyone S bb deep (reset every hand -> chip-EV per hand),
1bb big-blind ante, button rotates. First-in player shoves or folds; later players
call/fold; players after a caller may over-call (the analytic solver ignores this).
Hero's result is measured with common random numbers: the same deals are replayed
with each hero strategy, so differences are low-variance.
"""
import sys, random, numpy as np, eval7
from multiprocessing import Pool
from hands import CLASSES, INDEX
from pushfold import positions
from analyze import RES
from shove_score import SCORE
import strategy as st

POS = positions(8)
RANKS = "23456789TJQKA"


def label(c1, c2):
    r1, r2 = str(c1)[0], str(c2)[0]
    s = str(c1)[1] == str(c2)[1]
    if RANKS.index(r1) < RANKS.index(r2):
        r1, r2 = r2, r1
    if r1 == r2:
        return r1 + r2
    return r1 + r2 + ("s" if s else "o")


# ----- agents: shove(hand, pos, S) and call(hand, pusher_pos, my_pos, S, n_callers_before)
class Nash:
    name = "Nash"
    def shove(self, h, p, S, rng):
        return rng.random() < RES[(S, p)]["push"][INDEX[h]]
    def call(self, h, pp, me, S, ncall, rng):
        f = RES[(S, pp)]["calls"][me][INDEX[h]]
        if ncall:  # over-call: need a hand well inside the calling range
            return SCORE[INDEX[h]] >= st.call_line(pp, S) + 10
        return rng.random() < f


class Simple:
    name = "Simple rules"
    def shove(self, h, p, S, rng):
        return st.should_shove(h, p, S)
    def call(self, h, pp, me, S, ncall, rng):
        return SCORE[INDEX[h]] >= st.call_line(pp, S) + (10 if ncall else 0)


class Leaky:
    """Typical recreational leaks: shoves too tight, calls too loose / too tight."""
    def __init__(self, shove_adj, call_adj, name):
        self.sa, self.ca, self.name = shove_adj, call_adj, name
    def shove(self, h, p, S, rng):
        return SCORE[INDEX[h]] >= st.shove_line(p, S) + self.sa
    def call(self, h, pp, me, S, ncall, rng):
        return SCORE[INDEX[h]] >= st.call_line(pp, S) + self.ca + (10 if ncall else 0)


FIELDS = {
    "Nash field": lambda: Nash(),
    "Nit field (shoves +6 tight, calls +6 tight)": lambda: Leaky(6, 6, "nit"),
    "Calling station field (shoves +4 tight, calls -8 loose)": lambda: Leaky(4, -8, "station"),
    "Maniac field (shoves -8 loose, calls -4 loose)": lambda: Leaky(-8, -4, "maniac"),
}
HEROES = {"Nash": Nash, "Simple rules": Simple}


def play_hand(agents, S, deck_cards, rng, ante=1.0):
    """Returns net bb for each seat (index by position)."""
    n = len(POS)
    holes = [(deck_cards[2 * i], deck_cards[2 * i + 1]) for i in range(n)]
    board = deck_cards[2 * n: 2 * n + 5]
    labels = [label(*h) for h in holes]
    invest = np.zeros(n)
    invest[POS.index("SB")] = 0.5
    invest[POS.index("BB")] = 1.0
    dead_ante = ante
    pusher = None
    allin = []
    for i, p in enumerate(POS[:-1]):
        if agents[i].shove(labels[i], p, S, rng):
            pusher = i
            break
    if pusher is None:
        net = -invest.copy()
        net[POS.index("BB")] += invest.sum() + dead_ante
        net[POS.index("BB")] -= dead_ante  # BB paid the ante
        return net
    allin = [pusher]
    for j in range(pusher + 1, n):
        if agents[j].call(labels[j], POS[pusher], POS[j], S, len(allin) - 1, rng):
            allin.append(j)
    for k in allin:
        invest[k] = S
    pot = invest.sum() + dead_ante
    net = -invest.copy()
    net[POS.index("BB")] -= dead_ante
    if len(allin) == 1:
        net[pusher] += pot
        return net
    vals = {k: eval7.evaluate(list(holes[k]) + board) for k in allin}
    best = max(vals.values())
    winners = [k for k in allin if vals[k] == best]
    for k in winners:
        net[k] += pot / len(winners)
    return net


def run(args):
    field_name, S, n_hands, seed = args
    rng_deal = random.Random(seed)
    out = {h: 0.0 for h in HEROES}
    out_sq = {h: 0.0 for h in HEROES}
    diff_sq = 0.0
    deck = eval7.Deck()
    for t in range(n_hands):
        deck.shuffle()
        cards = deck.cards[:21]
        hero_seat = t % 8
        res = {}
        rseed = rng_deal.random()
        for hname, H in HEROES.items():
            agents = [FIELDS[field_name]() for _ in range(8)]
            agents[hero_seat] = H()
            r = play_hand(agents, S, cards, random.Random(rseed))[hero_seat]
            res[hname] = r
            out[hname] += r
        diff_sq += (res["Simple rules"] - res["Nash"]) ** 2
    return field_name, S, out, diff_sq, n_hands


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    stacks = [5, 8, 10, 12, 15]
    jobs = [(f, S, n, 1000 * i + S) for i, f in enumerate(FIELDS) for S in stacks for _ in range(1)]
    agg = {}
    with Pool() as pool:
        for f, S, out, dsq, nh in pool.imap_unordered(run, jobs):
            a = agg.setdefault(f, {"Nash": 0, "Simple rules": 0, "dsq": 0, "n": 0, "by_S": {}})
            for h in HEROES:
                a[h] += out[h]
            a["dsq"] += dsq; a["n"] += nh
            a["by_S"][S] = {h: 100 * out[h] / nh for h in HEROES}
    print(f"Hero results in bb/100 hands (8-max, BB ante, {n} hands per stack depth, stacks {stacks})")
    for f, a in agg.items():
        nh = a["n"]
        nash, simp = 100 * a["Nash"] / nh, 100 * a["Simple rules"] / nh
        mean_d = (a["Simple rules"] - a["Nash"]) / nh
        se = 100 * np.sqrt(max(a["dsq"] / nh - mean_d ** 2, 0) / nh)
        print(f"\n{f}\n  Nash hero {nash:+7.2f}   Simple hero {simp:+7.2f}   diff {simp - nash:+.2f} ± {se:.2f}")
        print("  by stack: " + "  ".join(f"{S}bb N{v['Nash']:+.1f}/S{v['Simple rules']:+.1f}" for S, v in sorted(a["by_S"].items())))
