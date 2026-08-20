"""
Monopoly landing-probability Monte Carlo simulation.

Method
------
Only ONE token's movement matters for "which square gets landed on most often" -
other players' turns don't influence this token's transition probabilities, so we
simulate a single token taking a huge number of turns and tally the square it
*ends* each turn on (the resting square after all doubles-chained rolls and any
card-driven movement have resolved). Relative frequency -> estimated probability.

Modeled mechanics (current configuration):
  1. Two six-sided dice, sum distribution - one roll per turn, no bonus rolls
     for doubles (doubles mechanic disregarded entirely: it neither grants an
     extra roll nor sends you to jail after three in a row).
  2. Landing on "Go To Jail" (square 30) sends you to jail (square 10, jailed).
     This is a fixed board-square rule, independent of cards or doubles.
  3. Chance / Community Chest cards are disregarded: landing on those squares
     has no effect on position, as if every card were a money-only no-op.
  4. Jail rule (doubles-free version): you simply serve up to 3 turns in jail;
     on the 3rd turn you're forced out, roll normally, and move.
"""

import random
from collections import Counter

# ----------------------------------------------------------------------------
# Board layout (index 0-39)
# ----------------------------------------------------------------------------
SQUARE_NAMES = [
    "GO", "Mediterranean Ave", "Community Chest 1", "Baltic Ave", "Income Tax",
    "Reading Railroad", "Oriental Ave", "Chance 1", "Vermont Ave", "Connecticut Ave",
    "Jail / Just Visiting", "St. Charles Place", "Electric Company", "States Ave",
    "Virginia Ave", "Pennsylvania Railroad", "St. James Place", "Community Chest 2",
    "Tennessee Ave", "New York Ave", "Free Parking", "Kentucky Ave", "Chance 2",
    "Indiana Ave", "Illinois Ave", "B&O Railroad", "Atlantic Ave", "Ventnor Ave",
    "Water Works", "Marvin Gardens", "Go To Jail", "Pacific Ave", "North Carolina Ave",
    "Community Chest 3", "Pennsylvania Ave", "Short Line Railroad", "Chance 3",
    "Park Place", "Luxury Tax", "Boardwalk",
]
BOARD_SIZE = 40
JAIL_POS = 10
GO_TO_JAIL_POS = 30
CHANCE_POS = {7, 22, 36}
CHEST_POS = {2, 17, 33}
RAILROADS = [5, 15, 25, 35]
UTILITIES = [12, 28]
ILLINOIS_AVE = 24
ST_CHARLES = 11
READING_RR = 5
BOARDWALK = 39


def nearest(position, targets):
    """Next target square at or after `position`, wrapping around the board."""
    ahead = [t for t in targets if t > position]
    return min(ahead) if ahead else min(targets)


# ----------------------------------------------------------------------------
# Card decks. Each card is a function: position -> (new_position, sent_to_jail)
# Money-only cards are represented as None (no-op for position).
# ----------------------------------------------------------------------------
def make_chance_deck():
    deck = [
        lambda p: (BOARDWALK, False),                    # Advance to Boardwalk
        lambda p: (0, False),                             # Advance to Go
        lambda p: (ILLINOIS_AVE, False),                  # Advance to Illinois Ave
        lambda p: (ST_CHARLES, False),                    # Advance to St. Charles Place
        lambda p: (nearest(p, RAILROADS), False),         # Advance to nearest Railroad
        lambda p: (nearest(p, UTILITIES), False),         # Advance to nearest Utility
        None,                                              # Bank pays dividend $50
        None,                                              # Get Out of Jail Free (kept; no-op here)
        lambda p: ((p - 3) % BOARD_SIZE, False),          # Go Back 3 Spaces
        lambda p: (JAIL_POS, True),                       # Go to Jail
        None,                                              # Make general repairs
        None,                                              # Pay poor tax $15
        lambda p: (READING_RR, False),                    # Take a trip to Reading Railroad
        None,                                              # Elected Chairman, pay each player $50
        None,                                              # Building loan matures, collect $150
        None,                                              # Won crossword competition, collect $100
    ]
    assert len(deck) == 16
    return deck


def make_chest_deck():
    deck = [None] * 16
    deck[0] = lambda p: (0, False)          # Advance to Go
    deck[1] = lambda p: (JAIL_POS, True)    # Go to Jail
    deck[2] = None                           # Get Out of Jail Free (kept; no-op here)
    # remaining 13 cards are money-only -> no position effect
    return deck


class Deck:
    """Shuffled draw-without-replacement deck that reshuffles when exhausted."""

    def __init__(self, cards, rng):
        self.cards = list(cards)
        self.rng = rng
        self.order = []

    def draw(self):
        if not self.order:
            self.order = list(range(len(self.cards)))
            self.rng.shuffle(self.order)
        idx = self.order.pop()
        return self.cards[idx]


def resolve_landing(pos, chance_deck, chest_deck):
    """Apply the effect of landing on `pos`. Returns (new_pos, sent_to_jail).

    Card effects are disregarded: landing on a Chance or Community Chest
    square has no effect on position (as if you drew a money-only card every
    time). "Go To Jail" is a board square, not a card, and still sends you
    to jail.
    """
    if pos == GO_TO_JAIL_POS:
        return JAIL_POS, True
    return pos, False


def simulate(n_turns, seed=None):
    rng = random.Random(seed)
    chance_deck = Deck(make_chance_deck(), rng)
    chest_deck = Deck(make_chest_deck(), rng)

    pos = 0
    in_jail = False
    jail_strikes = 0

    counts = Counter()

    for _ in range(n_turns):
        if in_jail:
            # Doubles mechanic disregarded: no early release via doubles.
            # You simply serve up to 3 turns, then are forced out and move.
            jail_strikes += 1
            if jail_strikes >= 3:
                in_jail = False
                jail_strikes = 0
                d1, d2 = rng.randint(1, 6), rng.randint(1, 6)
                pos = (pos + d1 + d2) % BOARD_SIZE
                pos, sent = resolve_landing(pos, chance_deck, chest_deck)
                if sent:
                    in_jail = True
            # else: stay put in jail, turn ends, position unchanged
        else:
            d1, d2 = rng.randint(1, 6), rng.randint(1, 6)
            pos = (pos + d1 + d2) % BOARD_SIZE
            pos, sent = resolve_landing(pos, chance_deck, chest_deck)
            if sent:
                in_jail = True
                jail_strikes = 0

        counts[pos] += 1

    return counts


if __name__ == "__main__":
    N = 5_000_000
    counts = simulate(N, seed=42)

    total = sum(counts.values())
    results = [(i, SQUARE_NAMES[i], counts.get(i, 0), counts.get(i, 0) / total) for i in range(BOARD_SIZE)]
    results.sort(key=lambda r: -r[3])

    print(f"Simulated {N:,} turns\n")
    print(f"{'Rank':<5}{'Square':<25}{'Landings':>12}{'Probability':>14}")
    print("-" * 56)
    for rank, (i, name, c, p) in enumerate(results, 1):
        print(f"{rank:<5}{name:<25}{c:>12,}{p*100:>13.3f}%")

    # sanity check
    print(f"\nTotal probability sums to: {sum(p for *_, p in results):.6f}")

# ----------------------------------------------------------------------------
# Optional: bar chart of the landing-probability distribution, in board order
# ----------------------------------------------------------------------------
def plot_distribution(counts, total, out_path="landing_probabilities.png"):
    import matplotlib.pyplot as plt

    probs = [counts.get(i, 0) / total * 100 for i in range(BOARD_SIZE)]
    colors = []
    for i in range(BOARD_SIZE):
        if i == JAIL_POS:
            colors.append("#c0392b")
        elif i == GO_TO_JAIL_POS:
            colors.append("#7f8c8d")
        elif i in CHANCE_POS:
            colors.append("#e67e22")
        elif i in CHEST_POS:
            colors.append("#2980b9")
        else:
            colors.append("#27ae60")

    fig, ax = plt.subplots(figsize=(16, 6))
    ax.bar(range(BOARD_SIZE), probs, color=colors)
    ax.set_xticks(range(BOARD_SIZE))
    ax.set_xticklabels(SQUARE_NAMES, rotation=90, fontsize=7)
    ax.axhline(100 / BOARD_SIZE, linestyle="--", color="black", linewidth=1,
               label=f"Uniform baseline ({100/BOARD_SIZE:.2f}%)")
    ax.set_ylabel("Landing probability (%)")
    ax.set_title(f"Monopoly landing-square probabilities ({total:,} simulated turns)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"\nSaved chart to {out_path}")

# ----------------------------------------------------------------------------
# Board-shaped heatmap: lays the 40 squares out in their actual perimeter
# positions (an 11x11 grid, like the real board) and colors each cell by its
# landing probability.
# ----------------------------------------------------------------------------
def _pos_to_rc(i):
    """Map board index (0-39) to (row, col) in an 11x11 grid, matching the
    real Monopoly layout: GO at bottom-right, going counter-clockwise."""
    if i == 0:
        return (10, 10)
    if 1 <= i <= 9:
        return (10, 10 - i)
    if i == 10:
        return (10, 0)
    if 11 <= i <= 19:
        return (20 - i, 0)
    if i == 20:
        return (0, 0)
    if 21 <= i <= 29:
        return (0, i - 20)
    if i == 30:
        return (0, 10)
    if 31 <= i <= 39:
        return (i - 30, 10)
    raise ValueError(i)


def plot_board_heatmap(counts, total, out_path="board_heatmap.png",
                        title=None, exclude_from_scale=(JAIL_POS, GO_TO_JAIL_POS)):
    """
    exclude_from_scale: squares whose values are left OUT of the color-scale
    computation (vmin/vmax), so a structural outlier like Jail doesn't wash
    out the color contrast among the other 38 squares. Excluded squares are
    still drawn and labeled with their true value, just color-clipped to the
    scale's endpoint and hatched to flag that they're off-scale.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors

    probs = {i: counts.get(i, 0) / total * 100 for i in range(BOARD_SIZE)}
    scale_vals = [p for i, p in probs.items() if i not in exclude_from_scale]
    vmin, vmax = min(scale_vals), max(scale_vals)
    cmap = cm.get_cmap("YlOrRd")
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

    fig, ax = plt.subplots(figsize=(12, 12))

    for i in range(BOARD_SIZE):
        row, col = _pos_to_rc(i)
        off_scale = i in exclude_from_scale
        clipped = min(max(probs[i], vmin), vmax)
        color = cmap(norm(clipped))
        is_corner = i in (0, 10, 20, 30)
        rect = patches.Rectangle((col, 10 - row), 1, 1,
                                  facecolor=color,
                                  edgecolor="black", linewidth=1.2,
                                  hatch="///" if off_scale else None)
        ax.add_patch(rect)

        # label: square name (wrapped) + probability
        name = SQUARE_NAMES[i]
        words = name.split()
        wrapped = "\n".join(words) if len(words) <= 2 else \
            "\n".join([" ".join(words[:len(words)//2]), " ".join(words[len(words)//2:])])
        fontsize = 6.5 if not is_corner else 7.5
        # pick readable text color against the cell's fill
        r, g, b, _ = color
        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        text_color = "white" if brightness < 0.55 else "black"
        ax.text(col + 0.5, 10 - row + 0.62, wrapped, ha="center", va="center",
                fontsize=fontsize, color=text_color, fontweight="bold" if is_corner else "normal")
        ax.text(col + 0.5, 10 - row + 0.22, f"{probs[i]:.2f}%", ha="center", va="center",
                fontsize=7, color=text_color)

    # blank interior
    ax.add_patch(patches.Rectangle((1, 1), 9, 9, facecolor="#f7f3e9", edgecolor="black", linewidth=1.5))
    ax.text(5.5, 5.5, "MONOPOLY\nLanding-probability heatmap", ha="center", va="center",
            fontsize=16, fontweight="bold", color="#555555")

    ax.set_xlim(0, 11)
    ax.set_ylim(0, 11)
    ax.set_aspect("equal")
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=14, pad=15)

    sm = cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label(f"Landing probability (%)  [scale fit to the {BOARD_SIZE - len(exclude_from_scale)} non-hatched squares]")

    if exclude_from_scale:
        names = ", ".join(f"{SQUARE_NAMES[i]} ({probs[i]:.2f}%)" for i in exclude_from_scale)
        fig.text(0.5, 0.01, f"Hatched squares are off-scale (true value shown, color capped): {names}",
                  ha="center", fontsize=9, color="#555555")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved board heatmap to {out_path}")
