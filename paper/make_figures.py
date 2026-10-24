"""Figures for the revised manuscript, drawn in black and white at IEEE
column width (3.5 in) so they print legibly.

    python paper/make_figures.py          # from the repo root

Diagrams (fig1, fig2, fig3) need nothing else. The two charts read the
experiment CSVs in results/ (written by scripts/benchmark.py and
scripts/oversaturation.py with --csv), so they always show the committed
numbers. Output: paper/figures/*.png (600 dpi).
"""

import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402
from scipy import stats  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
RESULTS = ROOT / "results"
COL_W = 3.45  # inches, one IEEE column

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 7.5,
    "axes.linewidth": 0.6,
    "lines.linewidth": 0.9,
    "savefig.dpi": 600,
    "mathtext.fontset": "stix",
})

LABELS = {
    "fixed": "Fixed (20 s)",
    "webster": "Webster fixed",
    "actuated": "Actuated",
    "max_pressure": "Max-pressure",
    "density_levels": "Density levels",
    "adaptive": "Adaptive",
    "adaptive_hold": "Adaptive + hold",
}


# --- Diagram helpers ------------------------------------------------------

def box(ax, x, y, w, h, text, dashed=False, bold=False, fill="white", size=7):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.01,rounding_size=0.015",
                                linewidth=0.7, edgecolor="black", facecolor=fill,
                                linestyle=(0, (3, 2)) if dashed else "solid"))
    ax.text(x, y, text, ha="center", va="center", fontsize=size, fontweight="bold" if bold else "normal",
            linespacing=1.15)


def diamond(ax, x, y, w, h, text, size=6.6):
    ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)], closed=True,
                         linewidth=0.7, edgecolor="black", facecolor="white"))
    ax.text(x, y, text, ha="center", va="center", fontsize=size, linespacing=1.1)


def arrow(ax, x0, y0, x1, y1, text=None, text_pos=0.5, dx=0.0, dy=0.0, style="-|>", dashed=False):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=6, linewidth=0.7,
                                 color="black", linestyle=(0, (3, 2)) if dashed else "solid", shrinkA=0, shrinkB=0))
    if text:
        ax.text(x0 + (x1 - x0) * text_pos + dx, y0 + (y1 - y0) * text_pos + dy, text, fontsize=6.3,
                ha="center", va="center")


def canvas(height_in):
    fig = plt.figure(figsize=(COL_W, height_in))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, height_in / COL_W)
    ax.axis("off")
    return fig, ax


# --- Fig. 1: software architecture ---------------------------------------

def fig_architecture():
    fig, ax = canvas(2.55)
    top = 2.55 / COL_W
    lx, rx, w, h = 0.255, 0.765, 0.37, 0.11
    ys = [top - 0.10, top - 0.27, top - 0.44, top - 0.61]
    s = 6.2
    box(ax, 0.5, ys[0], 0.62, h, "Microscopic simulator (20 Hz)\n4-arm junction, 2 lanes/arm, 7 vehicle classes", size=s)
    box(ax, lx, ys[1], w, h, "Density estimation\nweight × (1.5 queued, 0.5 moving)", size=s)
    box(ax, lx, ys[2], w, h, "Signal controller\nfixed / adaptive / + hold", size=s)
    box(ax, lx, ys[3], w, h, "Emergency preemption\nyellow → all-red → priority", size=s)
    box(ax, rx, ys[1], w, h, "Virtual camera (2 Hz)\n200×240 px, 60 m view", dashed=True, size=s)
    box(ax, rx, ys[2], w, h, "Haar-cascade detector\n+ ByteTrack-style tracker", dashed=True, size=s)
    box(ax, rx, ys[3], w, h, "FastAPI + WebSocket,\nSQLite, React dashboard", dashed=True, size=s)
    arrow(ax, 0.40, ys[0] - h / 2, lx, ys[1] + h / 2)
    arrow(ax, 0.60, ys[0] - h / 2, rx, ys[1] + h / 2, dashed=True)
    for x, dashed in ((lx, False), (rx, True)):
        arrow(ax, x, ys[1] - h / 2, x, ys[2] + h / 2, dashed=dashed)
        arrow(ax, x, ys[2] - h / 2, x, ys[3] + h / 2, dashed=dashed)
    gap_l, gap_r = lx + w / 2, rx - w / 2
    arrow(ax, gap_l, ys[2], gap_r, ys[2], style="-", dashed=True)
    ax.text(0.5, ys[2] + 0.03, "display\nonly", fontsize=5.4, ha="center", va="center", style="italic",
            linespacing=1.0)
    # signal states back to the simulator
    ax.plot([lx - w / 2, 0.035, 0.035], [ys[3], ys[3], ys[0]], color="black", linewidth=0.7)
    arrow(ax, 0.035, ys[0], 0.19, ys[0])
    ax.text(0.018, (ys[0] + ys[3]) / 2, "signal states", rotation=90, fontsize=5.8, ha="center", va="center")
    arrow(ax, gap_l, ys[3], gap_r, ys[3])
    ax.text(0.5, ys[3] + 0.025, "phase", fontsize=5.6, ha="center", va="center")
    fig.savefig(OUT / "fig1_architecture.png")
    plt.close(fig)


# --- Fig. 2: method workflow + green-end decision (new) ------------------

def fig_workflow():
    height = 4.15
    fig, ax = canvas(height)
    top = height / COL_W

    # (a) pipeline
    ax.text(0.02, top - 0.035, "(a) Per-step control pipeline", fontsize=7.2, fontweight="bold", va="center")
    stages = [
        ("Sense", "positions,\nspeeds, classes"),
        ("Score", "D = Σ w·m\nper approach"),
        ("Decide", "end the\ngreen? (b)"),
        ("Protect", "preemption,\nyellow/all-red"),
        ("Actuate", "signal\nheads"),
    ]
    y = top - 0.15
    bw = 0.158
    xs = [0.1 + i * 0.2 for i in range(5)]
    for x, (title, sub) in zip(xs, stages):
        box(ax, x, y, bw, 0.155, f"{title}\n", bold=True, size=6.8)
        ax.text(x, y - 0.03, sub, ha="center", va="center", fontsize=5.4, linespacing=1.1)
    for a, b in zip(xs, xs[1:]):
        arrow(ax, a + bw / 2 + 0.004, y, b - bw / 2 - 0.004, y)
    ax.text(0.5, y - 0.115, "repeated every 50 ms step; camera detection (Haar + tracker) runs alongside for display",
            fontsize=5.6, ha="center", style="italic")

    # (b) decision flowchart
    ax.text(0.02, top - 0.335, "(b) Green-end decision of the adaptive controller (+ discharge hold)",
            fontsize=7.2, fontweight="bold", va="center")
    cx = 0.36
    yy = [top - 0.43, top - 0.58, top - 0.73, top - 0.88, top - 1.03]
    box(ax, cx, yy[0], 0.5, 0.07, "each step of a green ($t_g$ = elapsed green)", size=6.4)
    diamond(ax, cx, yy[1], 0.36, 0.11, "$t_g \\geq G_{max}$ = 45 s ?")
    diamond(ax, cx, yy[2], 0.36, 0.11, "$t_g \\geq G_{min}$ = 8 s ?")
    diamond(ax, cx, yy[3], 0.40, 0.12, "vehicle within $z$ = 10 m\nof served stop line ?")
    diamond(ax, cx, yy[4], 0.40, 0.12, "$D_A \\leq \\theta \\, D_W$ ?\n($\\theta$ = 1.1)")
    end_x, keep_x = 0.84, 0.84
    box(ax, end_x, yy[1], 0.24, 0.075, "END green →\n3 s yellow, 1 s all-red", size=6.1)
    box(ax, keep_x, (yy[2] + yy[3]) / 2, 0.22, 0.075, "KEEP green\n(re-check next step)", size=6.1)
    arrow(ax, cx, yy[0] - 0.035, cx, yy[1] + 0.055)
    arrow(ax, cx, yy[1] - 0.055, cx, yy[2] + 0.055, text="no", dx=0.03)
    arrow(ax, cx, yy[2] - 0.055, cx, yy[3] + 0.06, text="yes", dx=0.03)
    arrow(ax, cx, yy[3] - 0.06, cx, yy[4] + 0.06, text="no", dx=0.03)
    arrow(ax, cx + 0.18, yy[1], end_x - 0.12, yy[1], text="yes", dy=0.018)
    keep_y = (yy[2] + yy[3]) / 2
    ax.plot([cx + 0.18, 0.66], [yy[2], yy[2]], color="black", linewidth=0.7)
    ax.text(0.62, yy[2] + 0.018, "no", fontsize=6.3, ha="center")
    ax.plot([cx + 0.20, 0.66], [yy[3], yy[3]], color="black", linewidth=0.7)
    ax.text(0.62, yy[3] + 0.018, "yes", fontsize=6.3, ha="center")
    ax.plot([0.66, 0.66], [yy[2], yy[3]], color="black", linewidth=0.7)
    arrow(ax, 0.66, keep_y, keep_x - 0.11, keep_y)
    # last decision: yes -> end (route on the far right), no -> keep
    ax.plot([cx + 0.20, 0.97, 0.97], [yy[4], yy[4], yy[1] - 0.0375], color="black", linewidth=0.7)
    arrow(ax, 0.97, yy[1] - 0.0375, end_x + 0.12, yy[1] - 0.0375, style="-|>")
    ax.text(0.80, yy[4] + 0.018, "yes", fontsize=6.3, ha="center")
    ax.plot([cx - 0.20, 0.06, 0.06], [yy[4], yy[4], yy[4] - 0.095], color="black", linewidth=0.7)
    ax.plot([0.06, keep_x, keep_x], [yy[4] - 0.095, yy[4] - 0.095, keep_y - 0.0375], color="black", linewidth=0.7)
    arrow(ax, keep_x, yy[4] - 0.095 + 0.001, keep_x, keep_y - 0.0375)
    ax.text(0.12, yy[4] + 0.018, "no", fontsize=6.3, ha="center")
    ax.text(0.03, yy[3] + 0.075, "discharge hold\n(new)", fontsize=5.8, style="italic", ha="left", va="center")
    fig.savefig(OUT / "fig2_workflow.png")
    plt.close(fig)


# --- Fig. 3: emergency preemption states ----------------------------------

def fig_preemption():
    fig, ax = canvas(1.62)
    w, h = 0.165, 0.11
    top_y, bot_y = 0.33, 0.09
    xs = [0.095, 0.365, 0.635, 0.905]
    for x, label in zip(xs, ["NORMAL\n(inner ctrl.)", "FORCE\nYELLOW", "ALL-RED\nCLEARING", "PREEMPT\nGREEN"]):
        box(ax, x, top_y, w, h, label, size=6.0)
    for x, label in zip(xs[1:3], ["RELEASE\nALL-RED", "RELEASE\nYELLOW"]):
        box(ax, x, bot_y, w, h, label, size=6.0)

    def label(x, y, text, ha="center"):
        ax.text(x, y, text, fontsize=5.6, ha=ha, va="center", linespacing=1.0)

    for a, b, text in ((0, 1, "EV, green ≥ 5 s"), (1, 2, "3 s"), (2, 3, "1 s")):
        arrow(ax, xs[a] + w / 2, top_y, xs[b] - w / 2, top_y)
        label((xs[a] + xs[b]) / 2, top_y + h / 2 + 0.03, text)
    ax.plot([xs[3], xs[3]], [top_y - h / 2, bot_y], color="black", linewidth=0.7)
    arrow(ax, xs[3], bot_y, xs[2] + w / 2, bot_y)
    label(xs[3] - 0.012, (top_y + bot_y) / 2, "EV passed\nor 20 s cap", ha="right")
    arrow(ax, xs[2] - w / 2, bot_y, xs[1] + w / 2, bot_y)
    label((xs[1] + xs[2]) / 2, bot_y + 0.035, "3 s")
    ax.plot([xs[1] - w / 2, xs[0]], [bot_y, bot_y], color="black", linewidth=0.7)
    arrow(ax, xs[0], bot_y, xs[0], top_y - h / 2)
    label(xs[0] + 0.012, (top_y + bot_y) / 2, "1 s, then green for\nthe held direction", ha="left")
    fig.savefig(OUT / "fig3_preemption.png")
    plt.close(fig)


# --- Data helpers ----------------------------------------------------------

def read_csv(name):
    path = RESULTS / name
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def mean_ci(values):
    values = [v for v in values if not math.isnan(v)]
    m = statistics.mean(values)
    half = stats.t.ppf(0.975, len(values) - 1) * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0
    return m, half


# --- Fig. 4: mean delay by controller at the paper's demand levels --------

def fig_delay_bars(controllers):
    rows = read_csv("table2_preemption_on.csv")
    levels = ["low", "medium", "high"]
    data = defaultdict(list)
    for r in rows:
        data[(r["level"], r["controller"])].append(float(r["mean_delay_s"]))
    fig, ax = plt.subplots(figsize=(COL_W, 1.9))
    n = len(controllers)
    width = 0.8 / n
    grays = [str(0.0 + 0.95 * i / max(1, n - 1)) for i in range(n)]
    hatches = ["", "////", "", "....", "xxxx", "", "\\\\\\\\"]
    for i, c in enumerate(controllers):
        means, halves = zip(*(mean_ci(data[(lv, c)]) for lv in levels))
        xs = [j + (i - (n - 1) / 2) * width for j in range(len(levels))]
        ax.bar(xs, means, width * 0.95, yerr=halves, color=grays[i], edgecolor="black", linewidth=0.5,
               hatch=hatches[i % len(hatches)], error_kw={"elinewidth": 0.5, "capsize": 1.2}, label=LABELS[c])
    ax.set_xticks(range(len(levels)))
    ax.set_xticklabels(["Low (1152 veh/h)", "Medium (1728 veh/h)", "High (2592 veh/h)"])
    ax.set_ylabel("Mean stopped delay (s)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=4, fontsize=5.6, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.3),
              handlelength=1.4, columnspacing=0.8)
    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / "fig4_delay_by_controller.png")
    plt.close(fig)


# --- Fig. 5: above capacity, delay and throughput vs demand ---------------

MARKERS = {"fixed": "o", "webster": "s", "actuated": "^", "max_pressure": "v", "density_levels": "D",
           "adaptive": "x", "adaptive_hold": "*"}
STYLES = {"fixed": "-", "webster": "--", "actuated": ":", "max_pressure": "-.", "density_levels": (0, (1, 1)),
          "adaptive": "--", "adaptive_hold": "-"}


def fig_oversaturation(controllers, csv_name="oversaturation_preemption_off.csv",
                       out="fig5_above_capacity.png"):
    rows = [r for r in read_csv(csv_name) if r["ratio"] != "capacity"]
    ratios = sorted({float(r["ratio"]) for r in rows})
    delay, thru = defaultdict(list), defaultdict(list)
    for r in rows:
        delay[(float(r["ratio"]), r["controller"])].append(float(r["delay_all_lb_s"]))
        thru[(float(r["ratio"]), r["controller"])].append(float(r["throughput_vph"]))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(COL_W, 3.75), sharex=True)
    for c in controllers:
        kw = dict(marker=MARKERS[c], linestyle=STYLES[c], color="black", markersize=3.2,
                  linewidth=1.2 if c == "adaptive_hold" else 0.8, label=LABELS[c],
                  markerfacecolor="white" if c in ("fixed", "webster", "max_pressure", "density_levels") else "black")
        a1.plot(ratios, [statistics.mean(delay[(x, c)]) for x in ratios], **kw)
        a2.plot(ratios, [statistics.mean(thru[(x, c)]) for x in ratios], **kw)
    a1.set_yscale("log")
    a1.set_ylabel("Delay incl. waiting (s)")
    a2.set_ylabel("Throughput (veh/h)")
    a2.set_xlabel("Demand / fixed-time capacity")
    for a in (a1, a2):
        a.spines[["top", "right"]].set_visible(False)
        a.axvline(1.0, color="0.6", linewidth=0.5, linestyle=":")
    handles, labels = a1.get_legend_handles_labels()
    fig.legend(handles, labels, ncol=4, fontsize=5.4, frameon=False, loc="lower center", bbox_to_anchor=(0.5, 0.0),
               handlelength=2.2, columnspacing=0.8)
    fig.tight_layout(pad=0.3, h_pad=0.4, rect=(0, 0.08, 1, 1))
    fig.savefig(OUT / out)
    plt.close(fig)


def fig_peak_queue(controllers, csv_name="peak_period_series.csv", out="fig6_peak_queue.png"):
    """Queue (links + waiting to enter) over the 60-minute peak period."""
    rows = read_csv(csv_name)
    series = defaultdict(list)
    for r in rows:
        series[r["controller"]].append((float(r["t_s"]) / 60, float(r["mean_queue"])))
    fig, ax = plt.subplots(figsize=(COL_W, 2.55))
    ax.axvspan(15, 30, color="0.88", linewidth=0)
    ax.axvspan(10, 15, color="0.94", linewidth=0)
    ax.axvspan(30, 35, color="0.94", linewidth=0)
    ax.text(22.5, 0.97, "peak: 1.2× capacity", transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=6)
    smooth = 4  # 4 x 30 s = 2-minute moving average
    for c in controllers:
        if c not in series:
            continue
        t, q = zip(*sorted(series[c]))
        q_s = [statistics.mean(q[max(0, i - smooth + 1):i + 1]) for i in range(len(q))]
        ax.plot(t, q_s, linestyle=STYLES[c], color="black", linewidth=1.4 if c == "adaptive_hold" else 0.8,
                marker=MARKERS[c], markevery=(controllers.index(c) * 2, 14), markersize=3,
                markerfacecolor="white" if c in ("fixed", "webster", "max_pressure", "density_levels") else "black",
                label=LABELS[c])
    ax.set_xlabel("Time (min)")
    ax.set_ylabel("Queue incl. waiting to enter (veh)")
    ax.set_xlim(0, 60)
    ax.set_ylim(bottom=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=4, fontsize=5.4, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.22),
              handlelength=2.2, columnspacing=0.8)
    fig.tight_layout(pad=0.3)
    fig.savefig(OUT / out)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fig_architecture()
    fig_workflow()
    fig_preemption()
    controllers = list(LABELS)
    if (RESULTS / "table2_preemption_on.csv").exists():
        fig_delay_bars(controllers)
    if (RESULTS / "oversaturation_preemption_off.csv").exists():
        fig_oversaturation(controllers)
    if (RESULTS / "peak_period_series.csv").exists():
        fig_peak_queue(controllers)
    print("figures written to", OUT)


if __name__ == "__main__":
    main()
