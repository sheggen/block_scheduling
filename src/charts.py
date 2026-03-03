"""Generate summary charts for the Monte Carlo block scheduling simulation."""

from __future__ import annotations

import random
import statistics
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

sys.path.insert(0, str(Path(__file__).parent))
from schedule import Schedule, DAY_ORDER, DAY_NAMES
from simulate import (
    run,
    HISTORICAL_WEIGHTS, HISTORICAL_FALLBACK_WEIGHT,
    _eligible, _evening_eligible, _has_conflict, _pick_classes, _mins,
)

SEED  = 42
N     = 20_000
DATA_DIR = Path(__file__).parent.parent / "data"
OUT      = Path(__file__).parent.parent / "charts.png"
COLOR    = "#4C72B0"
ACCENT   = "#DD8452"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conflict_pairs(schedule: Schedule, n: int = 10_000, seed: int = 0) -> Counter:
    random.seed(seed)
    day_pool = [b for b in schedule.time_blocks if _eligible(b)]
    eve_pool = [b for b in schedule.time_blocks if _evening_eligible(b)]
    pool     = day_pool + eve_pool
    weights  = [HISTORICAL_WEIGHTS.get(b.name, HISTORICAL_FALLBACK_WEIGHT) for b in pool]
    counts: Counter = Counter()
    for _ in range(n):
        student = _pick_classes(pool, weights, random.randint(3, 5))
        if _has_conflict(student):
            for a, b in combinations(student, 2):
                if set(a.days) & set(b.days):
                    if _mins(a.start) < _mins(b.end) and _mins(b.start) < _mins(a.end):
                        counts[tuple(sorted([a.name, b.name]))] += 1
    return counts


def _selection_probs(schedule: Schedule) -> dict[str, float]:
    day_pool = [b for b in schedule.time_blocks if _eligible(b)]
    eve_pool = [b for b in schedule.time_blocks if _evening_eligible(b)]
    pool     = day_pool + eve_pool
    raw      = [HISTORICAL_WEIGHTS.get(b.name, HISTORICAL_FALLBACK_WEIGHT) for b in pool]
    total    = sum(raw)
    return {b.name: w / total * 100 for b, w in zip(pool, raw)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sched = Schedule.from_json(DATA_DIR / "existing_schedule.json")

    print("Running simulation…")
    res = run(sched, n=N, seed=SEED)

    print("Computing conflict pairs…")
    pairs = _conflict_pairs(sched, n=10_000, seed=SEED)

    probs = _selection_probs(sched)

    # -----------------------------------------------------------------------
    fig = plt.figure(figsize=(18, 22), constrained_layout=True)
    fig.suptitle(
        f"Block Scheduling — Monte Carlo Simulation\n"
        f"{sched.name}  ·  {N:,} simulated students",
        fontsize=15, fontweight="bold",
    )

    gs = fig.add_gridspec(4, 2, height_ratios=[1.1, 1, 1.1, 1.3])

    # ── 1. Block selection probability ──────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :])
    sorted_blocks = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    names, pcts = zip(*sorted_blocks)
    bar_colors = [ACCENT if pcts[i] < 3 else COLOR for i in range(len(pcts))]
    ax1.bar(range(len(names)), pcts, color=bar_colors, alpha=0.88, edgecolor="white", linewidth=0.5)
    ax1.set_xticks(range(len(names)))
    ax1.set_xticklabels(names, rotation=45, ha="right", fontsize=7.5)
    ax1.set_ylabel("Selection probability (%)")
    ax1.set_title("Block selection probability — derived from historical course counts (F2016–F2020)")
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
    ax1.grid(axis="y", alpha=0.3)

    # ── 2. Weekly free-time distribution ────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, 0])
    wg_hrs = [m / 60 for m in res.weekly_gaps]
    ax2.hist(wg_hrs, bins=40, color=COLOR, alpha=0.82, edgecolor="white", linewidth=0.4)
    mean_h   = statistics.mean(wg_hrs)
    median_h = statistics.median(wg_hrs)
    ax2.axvline(mean_h,   color="tomato",    linestyle="--", linewidth=1.5, label=f"Mean {mean_h:.1f}h")
    ax2.axvline(median_h, color="darkgreen", linestyle="--", linewidth=1.5, label=f"Median {median_h:.1f}h")
    ax2.set_xlabel("Weekly free time between classes (hours)")
    ax2.set_ylabel("Simulated students")
    ax2.set_title("Distribution of weekly free time (valid schedules only)")
    ax2.legend(fontsize=9)
    ax2.grid(axis="y", alpha=0.3)

    # ── 3. Conflict rate ─────────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    valid_pct    = 100 - res.conflict_pct
    conflict_pct = res.conflict_pct
    wedges, texts, autotexts = ax3.pie(
        [valid_pct, conflict_pct],
        labels=["Valid", "Conflict"],
        colors=["#2ca02c", "#d62728"],
        autopct="%1.1f%%",
        startangle=90,
        wedgeprops=dict(alpha=0.85),
    )
    for at in autotexts:
        at.set_fontsize(11)
        at.set_fontweight("bold")
        at.set_color("white")
    ax3.set_title(
        f"Schedule conflict rate\n"
        f"{res.n_conflicts:,} conflicts / {res.n_attempts:,} attempts"
    )

    # ── 4. Free time by day of week (box plots) ───────────────────────────
    ax4 = fig.add_subplot(gs[2, :])
    data_by_day = [[m / 60 for m in res.day_gaps[d]] for d in DAY_ORDER]
    bp = ax4.boxplot(
        data_by_day,
        patch_artist=True,
        medianprops=dict(color="black", linewidth=2),
        boxprops=dict(facecolor=COLOR, alpha=0.7),
        whiskerprops=dict(linewidth=1.2),
        capprops=dict(linewidth=1.2),
        flierprops=dict(marker=".", markersize=2, alpha=0.25, color=COLOR),
    )
    ax4.set_xticklabels([DAY_NAMES[d] for d in DAY_ORDER])
    ax4.set_ylabel("Free time (hours)")
    ax4.set_title("Free time per day — distribution across simulated students")
    ax4.grid(axis="y", alpha=0.3)

    # annotate medians
    for i, d in enumerate(DAY_ORDER, start=1):
        med = statistics.median(res.day_gaps[d]) / 60
        ax4.text(i, med + 0.05, f"{med:.1f}h", ha="center", va="bottom", fontsize=8, color="black")

    # ── 5. Contact hours by class load ───────────────────────────────────────
    ax5 = fig.add_subplot(gs[3, 0])
    n_cls_vals = [3, 4, 5]
    contact_data = [
        [m / 60 for m in res.class_mins_by_n[n]] for n in n_cls_vals
    ]
    bp5 = ax5.boxplot(
        contact_data,
        patch_artist=True,
        medianprops=dict(color="black", linewidth=2),
        boxprops=dict(facecolor=ACCENT, alpha=0.7),
        whiskerprops=dict(linewidth=1.2),
        capprops=dict(linewidth=1.2),
        flierprops=dict(marker=".", markersize=2, alpha=0.3, color=ACCENT),
    )
    ax5.set_xticklabels([f"{n} classes" for n in n_cls_vals])
    ax5.set_ylabel("Weekly contact hours")
    ax5.set_title("Weekly contact hours by class load")
    ax5.grid(axis="y", alpha=0.3)
    for i, data in enumerate(contact_data, start=1):
        med = statistics.median(data)
        ax5.text(i, med + 0.05, f"{med:.1f}h", ha="center", va="bottom", fontsize=8)

    # ── 6. Top conflict pairs ─────────────────────────────────────────────────
    ax6 = fig.add_subplot(gs[3, 1])
    top_n = 10
    top_pairs = pairs.most_common(top_n)
    pair_labels = [f"{a}  ×\n{b}" for (a, b), _ in reversed(top_pairs)]
    counts      = [c for _, c in reversed(top_pairs)]
    total_pairs = sum(pairs.values())
    colors_bar  = [plt.cm.Reds(0.4 + 0.5 * c / counts[-1]) for c in counts]
    bars = ax6.barh(range(top_n), counts, color=colors_bar, alpha=0.88, edgecolor="white")
    ax6.set_yticks(range(top_n))
    ax6.set_yticklabels(pair_labels, fontsize=7)
    ax6.set_xlabel("Conflict occurrences (10k simulations)")
    ax6.set_title(f"Top {top_n} most frequent conflict pairs")
    ax6.grid(axis="x", alpha=0.3)
    for bar, count in zip(bars, counts):
        ax6.text(
            bar.get_width() + 5, bar.get_y() + bar.get_height() / 2,
            f"{100*count/total_pairs:.1f}%",
            va="center", fontsize=7.5,
        )

    fig.savefig(OUT, dpi=130, bbox_inches="tight")
    print(f"Saved → {OUT}")


if __name__ == "__main__":
    main()
