"""
Generate comparison charts from data/student_schedules_1500.json.

Charts
------
  1. Block usage          — % of student-course selections per block (grouped bar)
  2. Weekly free time     — overlapping histograms, existing vs proposed
  3. Conflict rate        — grouped bar: valid vs conflicted attempts
  4. Free time per day    — side-by-side box plots by day
  5. Contact hours        — side-by-side box plots by class load (3/4/5)
  6. Class-day spread     — grouped bar: 2/3/4/5-day weeks
  7. Gap distribution     — % of gaps (before/between/after class) by duration bucket
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from schedule import Schedule, DAY_ORDER, DAY_NAMES
from analyze_student_schedules import (
    _student_metrics, _aggregate, DAY_START_M, DAY_END_M,
)

DATA_DIR = Path(__file__).parent.parent / "data"
OUT      = Path(__file__).parent.parent / "charts_comparison.png"

EX_COLOR = "#4C72B0"   # blue  — existing
PR_COLOR = "#DD8452"   # orange — proposed
ALPHA    = 0.82


# ---------------------------------------------------------------------------
# Load + compute metrics
# ---------------------------------------------------------------------------

def load_data():
    existing_sched = Schedule.from_json(DATA_DIR / "existing_schedule.json")
    proposed_sched = Schedule.from_json(DATA_DIR / "proposed_schedule.json")
    ex_block = {b.name: b for b in existing_sched.time_blocks}
    pr_block = {b.name: b for b in proposed_sched.time_blocks}

    with open(DATA_DIR / "student_schedules_1500.json") as f:
        data = json.load(f)

    ex_raw = data["existing"]
    pr_raw = data["proposed"]

    ex_metrics = [_student_metrics(s["courses"], ex_block) for s in ex_raw["schedules"]]
    pr_metrics = [_student_metrics(s["courses"], pr_block) for s in pr_raw["schedules"]]

    return ex_raw, pr_raw, _aggregate(ex_metrics), _aggregate(pr_metrics)


# ---------------------------------------------------------------------------
# Gap distribution
# ---------------------------------------------------------------------------

GAP_BUCKETS = [
    (  0,  60, "0–1 hr"),
    ( 60, 120, "1–2 hrs"),
    (120, 180, "2–3 hrs"),
    (180, 240, "3–4 hrs"),
    (240, 300, "4–5 hrs"),
    (300, None, "5+ hrs"),
]


def _all_gaps(schedules, block_map):
    """Collect every before/between/after gap (minutes) across all student days."""
    from collections import defaultdict
    gaps = []
    for s in schedules:
        by_day = defaultdict(list)
        for c in s["courses"]:
            b = block_map.get(c["block"])
            if b is None:
                continue
            for day in b.days:
                by_day[day].append(b)
        for day in DAY_ORDER:
            blocks = sorted(by_day.get(day, []), key=lambda b: b.start)
            if not blocks:
                continue
            gaps.append(blocks[0].start.hour * 60 + blocks[0].start.minute - DAY_START_M)
            for i in range(len(blocks) - 1):
                g = (blocks[i+1].start.hour * 60 + blocks[i+1].start.minute
                     - blocks[i].end.hour * 60 - blocks[i].end.minute)
                gaps.append(max(0, g))
            gaps.append(DAY_END_M - (blocks[-1].end.hour * 60 + blocks[-1].end.minute))
    return gaps


def _bucket_gaps(gaps):
    counts = Counter()
    for g in gaps:
        if g < 0:
            continue
        for lo, hi, label in GAP_BUCKETS:
            if hi is None or g < hi:
                counts[label] += 1
                break
    return counts


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _grouped_bars(ax, categories, vals_a, vals_b, label_a, label_b,
                  ylabel="", title="", pct=False, color_a=EX_COLOR, color_b=PR_COLOR):
    x  = np.arange(len(categories))
    w  = 0.38
    ba = ax.bar(x - w/2, vals_a, w, label=label_a, color=color_a, alpha=ALPHA, edgecolor="white")
    bb = ax.bar(x + w/2, vals_b, w, label=label_b, color=color_b, alpha=ALPHA, edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    if pct:
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    return ba, bb


def _side_boxplot(ax, data_a, data_b, labels, label_a, label_b,
                  ylabel="", title="", scale=1.0):
    """Two side-by-side box plots per category."""
    positions_a = [i * 3 + 0.6 for i in range(len(labels))]
    positions_b = [i * 3 + 1.8 for i in range(len(labels))]
    tick_pos    = [i * 3 + 1.2 for i in range(len(labels))]

    def bpkw(color):
        return dict(
            patch_artist=True,
            medianprops=dict(color="black", linewidth=2),
            boxprops=dict(facecolor=color, alpha=0.75),
            whiskerprops=dict(linewidth=1.2),
            capprops=dict(linewidth=1.2),
            flierprops=dict(marker=".", markersize=2, alpha=0.25, color=color),
        )

    bp_a = ax.boxplot([[v * scale for v in d] for d in data_a],
                      positions=positions_a, widths=0.9, **bpkw(EX_COLOR))
    bp_b = ax.boxplot([[v * scale for v in d] for d in data_b],
                      positions=positions_b, widths=0.9, **bpkw(PR_COLOR))

    ax.set_xticks(tick_pos)
    ax.set_xticklabels(labels)
    ax.set_xlim(-0.5, len(labels) * 3 - 0.5)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)

    # legend proxies
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=EX_COLOR, alpha=0.75, label=label_a),
                        Patch(facecolor=PR_COLOR, alpha=0.75, label=label_b)],
              fontsize=9)
    return bp_a, bp_b


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading data…")
    ex_raw, pr_raw, ex_agg, pr_agg = load_data()

    fig = plt.figure(figsize=(18, 30), constrained_layout=True)
    fig.suptitle(
        "Block Scheduling — Existing vs Proposed\n"
        "1,500 simulated student schedules · weighted by historical usage (F2016–F2020)",
        fontsize=15, fontweight="bold",
    )
    gs = fig.add_gridspec(5, 2, height_ratios=[1.3, 1.0, 1.1, 1.0, 1.0])

    # ── 1. Block usage (full width) ──────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :])
    ex_usage = ex_raw["block_usage"]
    pr_usage = pr_raw["block_usage"]
    ex_total = sum(ex_usage.values())
    pr_total = sum(pr_usage.values())

    # Top blocks by combined usage
    all_blocks = list(dict.fromkeys(list(ex_usage)[:12] + list(pr_usage)[:12]))
    ex_pcts = [100 * ex_usage.get(b, 0) / ex_total for b in all_blocks]
    pr_pcts = [100 * pr_usage.get(b, 0) / pr_total for b in all_blocks]

    _grouped_bars(ax1, all_blocks, ex_pcts, pr_pcts,
                  "Existing", "Proposed",
                  ylabel="% of all course selections",
                  title="Block usage — share of student-course selections per block",
                  pct=True)
    ax1.set_xticklabels(all_blocks, rotation=40, ha="right", fontsize=8)

    # ── 2. Weekly free time histogram ────────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, 0])
    wf_ex = [v / 60 for v in ex_agg["weekly_free"]]
    wf_pr = [v / 60 for v in pr_agg["weekly_free"]]
    bins = np.linspace(min(min(wf_ex), min(wf_pr)), max(max(wf_ex), max(wf_pr)), 35)
    ax2.hist(wf_ex, bins=bins, alpha=0.6, color=EX_COLOR, label="Existing", edgecolor="white", linewidth=0.3)
    ax2.hist(wf_pr, bins=bins, alpha=0.6, color=PR_COLOR, label="Proposed", edgecolor="white", linewidth=0.3)
    for vals, color, ls in [(wf_ex, EX_COLOR, "--"), (wf_pr, PR_COLOR, "-.")]:
        ax2.axvline(statistics.mean(vals), color=color, linestyle=ls, linewidth=1.6,
                    label=f"Mean {statistics.mean(vals):.1f}h")
    ax2.set_xlabel("Weekly free time (hours, 8am–5pm window)")
    ax2.set_ylabel("Students")
    ax2.set_title("Distribution of weekly free time")
    ax2.legend(fontsize=8)
    ax2.grid(axis="y", alpha=0.3)

    # ── 3. Conflict rate ─────────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 1])
    labels_cr = ["Existing", "Proposed"]
    valid_pcts    = [100 - ex_raw["conflict_pct"], 100 - pr_raw["conflict_pct"]]
    conflict_pcts = [ex_raw["conflict_pct"],        pr_raw["conflict_pct"]]
    x = np.arange(2)
    w = 0.4
    ax3.bar(x, valid_pcts,    w, label="Valid",    color="#2ca02c", alpha=ALPHA, edgecolor="white")
    ax3.bar(x, conflict_pcts, w, label="Conflict", color="#d62728", alpha=ALPHA,
            bottom=valid_pcts, edgecolor="white")
    for i, (v, c) in enumerate(zip(valid_pcts, conflict_pcts)):
        ax3.text(i, v / 2,     f"{v:.1f}%",  ha="center", va="center", fontsize=10,
                 fontweight="bold", color="white")
        ax3.text(i, v + c / 2, f"{c:.1f}%",  ha="center", va="center", fontsize=10,
                 fontweight="bold", color="white")
    ax3.set_xticks(x)
    ax3.set_xticklabels(labels_cr, fontsize=11)
    ax3.set_ylabel("% of schedule attempts")
    ax3.set_title(
        f"Schedule conflict rate\n"
        f"Existing: {ex_raw['n_attempts']:,} attempts  ·  "
        f"Proposed: {pr_raw['n_attempts']:,} attempts"
    )
    ax3.legend(fontsize=9)
    ax3.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax3.grid(axis="y", alpha=0.3)

    # ── 4. Free time per day (side-by-side box plots, full width) ────────────
    ax4 = fig.add_subplot(gs[2, :])
    day_labels = [DAY_NAMES[d] for d in DAY_ORDER]
    data_ex = [ex_agg["day_free"][d] for d in DAY_ORDER]
    data_pr = [pr_agg["day_free"][d] for d in DAY_ORDER]
    _side_boxplot(ax4, data_ex, data_pr, day_labels,
                  "Existing", "Proposed",
                  ylabel="Free time (minutes)",
                  title="Free time per day — distribution across 1,500 students  (8am–5pm window, class days only)",
                  scale=1.0)
    # annotate medians
    positions_a = [i * 3 + 0.6 for i in range(len(DAY_ORDER))]
    positions_b = [i * 3 + 1.8 for i in range(len(DAY_ORDER))]
    for i, day in enumerate(DAY_ORDER):
        med_a = statistics.median(data_ex[i])
        med_b = statistics.median(data_pr[i])
        ax4.text(positions_a[i], med_a + 8, f"{med_a:.0f}", ha="center", va="bottom",
                 fontsize=7.5, color=EX_COLOR, fontweight="bold")
        ax4.text(positions_b[i], med_b + 8, f"{med_b:.0f}", ha="center", va="bottom",
                 fontsize=7.5, color=PR_COLOR, fontweight="bold")

    # ── 5. Contact hours by class load ───────────────────────────────────────
    ax5 = fig.add_subplot(gs[3, 0])
    ex_loads = [s["n_classes"] for s in ex_raw["schedules"]]
    pr_loads = [s["n_classes"] for s in pr_raw["schedules"]]
    ex_by_load = {n: [] for n in (4, 5, 6)}
    pr_by_load = {n: [] for n in (4, 5, 6)}

    for s, m in zip(ex_raw["schedules"],
                    [dict(n=s["n_classes"], c=sum(
                        b.duration_minutes * len(b.days)
                        for b in []))
                     for s in ex_raw["schedules"]]):
        pass  # placeholder — recompute below from agg contact

    # Recompute contact by load using full metrics
    existing_sched = Schedule.from_json(DATA_DIR / "existing_schedule.json")
    proposed_sched = Schedule.from_json(DATA_DIR / "proposed_schedule.json")
    ex_block = {b.name: b for b in existing_sched.time_blocks}
    pr_block = {b.name: b for b in proposed_sched.time_blocks}

    for s in ex_raw["schedules"]:
        n = s["n_classes"]
        contact = sum(
            ex_block[c["block"]].duration_minutes * len(ex_block[c["block"]].days)
            for c in s["courses"] if c["block"] in ex_block
        )
        ex_by_load[n].append(contact / 60)

    for s in pr_raw["schedules"]:
        n = s["n_classes"]
        contact = sum(
            pr_block[c["block"]].duration_minutes * len(pr_block[c["block"]].days)
            for c in s["courses"] if c["block"] in pr_block
        )
        pr_by_load[n].append(contact / 60)

    load_labels = ["4 classes", "5 classes", "6 classes"]
    _side_boxplot(ax5,
                  [ex_by_load[n] for n in (4, 5, 6)],
                  [pr_by_load[n] for n in (4, 5, 6)],
                  load_labels, "Existing", "Proposed",
                  ylabel="Weekly contact hours",
                  title="Weekly contact hours by class load")
    positions_a5 = [i * 3 + 0.6 for i in range(3)]
    positions_b5 = [i * 3 + 1.8 for i in range(3)]
    for i, n in enumerate((4, 5, 6)):
        med_a = statistics.median(ex_by_load[n]) if ex_by_load[n] else 0
        med_b = statistics.median(pr_by_load[n]) if pr_by_load[n] else 0
        ax5.text(positions_a5[i], med_a + 0.05, f"{med_a:.1f}h", ha="center", va="bottom",
                 fontsize=7.5, color=EX_COLOR, fontweight="bold")
        ax5.text(positions_b5[i], med_b + 0.05, f"{med_b:.1f}h", ha="center", va="bottom",
                 fontsize=7.5, color=PR_COLOR, fontweight="bold")

    # ── 6. Class-day spread ───────────────────────────────────────────────────
    ax6 = fig.add_subplot(gs[3, 1])
    cd_ex = ex_agg["class_days"]
    cd_pr = pr_agg["class_days"]
    day_counts = [2, 3, 4, 5]
    ex_spread = [100 * cd_ex.count(d) / len(cd_ex) for d in day_counts]
    pr_spread = [100 * cd_pr.count(d) / len(cd_pr) for d in day_counts]
    _grouped_bars(ax6, [f"{d} days" for d in day_counts],
                  ex_spread, pr_spread,
                  "Existing", "Proposed",
                  ylabel="% of students",
                  title="Class-day spread — distinct days/week with at least one class",
                  pct=True)

    # ── 7. Gap distribution (full width) ─────────────────────────────────────
    ax7 = fig.add_subplot(gs[4, :])

    ex_gaps = _all_gaps(ex_raw["schedules"], ex_block)
    pr_gaps = _all_gaps(pr_raw["schedules"], pr_block)
    ex_bc = _bucket_gaps(ex_gaps)
    pr_bc = _bucket_gaps(pr_gaps)
    ex_gt = sum(ex_bc.values())
    pr_gt = sum(pr_bc.values())

    labels7  = [label for _, _, label in GAP_BUCKETS]
    ex_pcts7 = [100 * ex_bc[l] / ex_gt for l in labels7]
    pr_pcts7 = [100 * pr_bc[l] / pr_gt for l in labels7]

    _grouped_bars(ax7, labels7, ex_pcts7, pr_pcts7,
                  "Existing", "Proposed",
                  ylabel="% of all gaps",
                  title=(
                      "Gap distribution — before first class, between classes, after last class\n"
                      f"(8am–5pm window · Existing: {ex_gt:,} gaps · Proposed: {pr_gt:,} gaps)"
                  ),
                  pct=True)

    # annotate delta above each pair
    x7 = np.arange(len(labels7))
    w7 = 0.38
    for i, (ep, pp) in enumerate(zip(ex_pcts7, pr_pcts7)):
        d = pp - ep
        sign = "+" if d >= 0 else ""
        top = max(ep, pp) + 0.4
        ax7.text(i, top, f"{sign}{d:.1f}%", ha="center", va="bottom",
                 fontsize=8, color="dimgray", fontweight="bold")

    fig.savefig(OUT, dpi=130, bbox_inches="tight")
    print(f"Saved → {OUT}")


if __name__ == "__main__":
    main()
