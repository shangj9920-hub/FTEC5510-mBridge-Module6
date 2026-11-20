# -*- coding: utf-8 -*-
"""make_figures.py -- the two core figures, from run_module6.py's metrics.csv.

Figure 1  fig1_benefit.png   paired differences vs S1: mean delay of urgent
                             payments (seconds) and number of FX trades. Negative
                             is better. S2 is negative on both panels; S3/S4 trade
                             time for fewer trades.
Figure 2  fig2_fairness.png  change in completion rate vs S1 (percentage points),
                             split by URGENT / NORMAL: urgent payments are
                             protected, ordinary ones are sacrificed where
                             liquidity binds.

All values are same-seed paired differences over the 30 formal seeds; the 95%
confidence intervals are in comparison.csv. Pillow only, no matplotlib.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import statistics

from PIL import Image, ImageDraw, ImageFont

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"
S = 2

NICE = {
    "baseline": "Normal",
    "low_rmb_liquidity": "Low RMB",
    "payment_surge": "Surge",
    "tight_deadlines": "Tight due",
    "large_payments": "Large pmt",
    "delayed_inflows": "Delay in",
    "fx_capacity_shock": "FX shock",
}
ORDER = list(NICE)
COLORS = {"S2": (0x30, 0xA4, 0x6C), "S3": (0xF2, 0xA6, 0x5B), "S4": (0xD9, 0x4F, 0x4F),
          "URGENT": (0x5B, 0x8D, 0xEF), "NORMAL": (0xF2, 0xA6, 0x5B)}


def F(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, int(size * S))


class Canvas:
    def __init__(self, w, h):
        self.img = Image.new("RGB", (w * S, h * S), (255, 255, 255))
        self.d = ImageDraw.Draw(self.img)
        self.w, self.h = w, h

    def text(self, xy, s, size=11, bold=False, fill=(30, 30, 30), anchor="la"):
        self.d.text((xy[0] * S, xy[1] * S), s, font=F(size, bold), fill=fill, anchor=anchor)

    def line(self, xy, fill=(220, 224, 230), width=1):
        self.d.line([(x * S, y * S) for x, y in xy], fill=fill, width=max(1, int(width * S)))

    def rect(self, box, fill):
        self.d.rectangle([box[0] * S, box[1] * S, box[2] * S, box[3] * S], fill=fill)

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.img.save(path, dpi=(200, 200))


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def paired_diffs(rows, key, a, b="S1"):
    """Paired differences a-b per (scenario, seed). Returns {scenario: [diff, ...]}."""
    per = {}
    for r in rows:
        per.setdefault((r["scenario_id"], r["seed"]), {})[r["strategy_id"]] = r.get(key)
    out = {}
    for (sc, _seed), d in per.items():
        va, vb = d.get(a), d.get(b)
        if va in (None, "") or vb in (None, ""):
            continue
        try:
            out.setdefault(sc, []).append(float(va) - float(vb))
        except ValueError:
            continue
    return out


def diverging_panel(cv, box, series, title, unit, nd=0, show_xlabels=False, scale=1.0):
    """series: [(label, {scenario: [diffs]}, color)]; the axis is scaled to the cell means."""
    x0, y0, x1, y1 = box
    cv.text(((x0 + x1) / 2, y0 - 22), title, 12, True, anchor="ma")

    means = {}
    for label, d, _c in series:
        for sc, lst in d.items():
            if lst:
                means[(label, sc)] = statistics.mean(lst) * scale
    if not means:
        return
    vals = list(means.values())
    lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
    span = (hi - lo) or 1.0
    lo -= span * 0.18
    hi += span * 0.18
    span = hi - lo

    def ypos(v):
        return y1 - (y1 - y0) * (v - lo) / span

    steps = 4
    for i in range(steps + 1):
        v = lo + span * i / steps
        yy = ypos(v)
        cv.line([(x0, yy), (x1, yy)], (238, 241, 246), 1)
        cv.text((x0 - 6, yy), f"{v:,.{nd}f}", 8, False, (150, 150, 150), anchor="rm")
    cv.line([(x0, ypos(0)), (x1, ypos(0))], (110, 116, 126), 1.4)
    cv.text((x1 + 4, ypos(0)), "S1", 8, False, (130, 134, 142), anchor="lm")

    n = len(ORDER)
    slot = (x1 - x0) / n
    bw = slot * 0.72 / len(series)
    for i, sc in enumerate(ORDER):
        gx = x0 + slot * (i + 0.5)
        for j, (label, diffs, color) in enumerate(series):
            v = means.get((label, sc))
            if v is None:
                continue
            bx = gx + (j - (len(series) - 1) / 2) * bw - bw * 0.42
            yy = ypos(v)
            cv.rect((bx, min(yy, ypos(0)), bx + bw * 0.84, max(yy, ypos(0))), color)
            if abs(v) >= span * 0.035:      # skip labels on tiny bars so the text does not overlap
                cv.text((bx + bw * 0.42, yy + (-3 if v < 0 else 3)),
                        f"{v:,.{nd}f}", 7, False, (80, 80, 80),
                        anchor="mb" if v < 0 else "mt")
        if show_xlabels:
            cv.text((gx, y1 + 7), NICE.get(sc, sc), 8, True, (100, 100, 100), anchor="ma")
    cv.text((x0, y0 - 8), unit, 9, False, (140, 140, 140))


def legend(cv, xy, entries, note=""):
    lx, ly = xy
    for label, color in entries:
        cv.rect((lx, ly, lx + 12, ly + 10), color)
        cv.text((lx + 16, ly + 5), label, 10, False, (70, 70, 70), anchor="lm")
        lx += 28 + F(10).getlength(label) / S
    if note:
        cv.text((lx + 14, ly + 5), note, 10, False, (140, 140, 140), anchor="lm")


def fig1(rows, out):
    cv = Canvas(1080, 760)
    cv.text((24, 18), "Figure 1  Effect vs S1: dynamic scheduling buys time, waiting buys fewer trades", 18, True)
    cv.text((24, 46), "Same-seed paired differences, mean over 30 formal seeds; negative = better than S1", 11, False, (100, 100, 100))

    panels = [
        ((92, 104, 1030, 330), "Mean settlement delay, URGENT payments (s)", "s"),
        ((92, 448, 1030, 668), "FX trades (count)", "trades"),
    ]
    d1 = [("S2", paired_diffs(rows, "URGENT.mean_delay", "S2"), COLORS["S2"]),
          ("S3", paired_diffs(rows, "URGENT.mean_delay", "S3"), COLORS["S3"]),
          ("S4", paired_diffs(rows, "URGENT.mean_delay", "S4"), COLORS["S4"])]
    d2 = [("S2", paired_diffs(rows, "fx_initiated", "S2"), COLORS["S2"]),
          ("S3", paired_diffs(rows, "fx_initiated", "S3"), COLORS["S3"]),
          ("S4", paired_diffs(rows, "fx_initiated", "S4"), COLORS["S4"])]
    diverging_panel(cv, panels[0][0], d1, panels[0][1], panels[0][2], nd=0)
    diverging_panel(cv, panels[1][0], d2, panels[1][1], panels[1][2], nd=1, show_xlabels=True)
    legend(cv, (92, 716), [("S2 dynamic", COLORS["S2"]), ("S3 waiting", COLORS["S3"]),
                           ("S4 combined", COLORS["S4"])],
           "relative to S1 (skippable FIFO)")
    cv.save(out)
    return out


def fig2(rows, out):
    cv = Canvas(1080, 760)
    cv.text((24, 18), "Figure 2  Fairness cost: urgent completion rises, ordinary completion falls under stress", 18, True)
    cv.text((24, 46), "Completion difference S2 - S1, percentage points, mean over 30 formal seeds", 11, False, (100, 100, 100))

    panels = [
        ((92, 104, 1030, 330), "URGENT completion change (pp)", "pp"),
        ((92, 448, 1030, 668), "NORMAL completion change (pp)", "pp"),
    ]
    du = [("S2", paired_diffs(rows, "URGENT.completion", "S2"), COLORS["URGENT"])]
    dn = [("S2", paired_diffs(rows, "NORMAL.completion", "S2"), COLORS["NORMAL"])]
    diverging_panel(cv, panels[0][0], du, panels[0][1], panels[0][2], nd=1, scale=100.0)
    diverging_panel(cv, panels[1][0], dn, panels[1][1], panels[1][2], nd=1, show_xlabels=True, scale=100.0)
    legend(cv, (92, 716), [("URGENT", COLORS["URGENT"]), ("NORMAL", COLORS["NORMAL"])],
           "relative to S1; negative = worse")
    cv.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", default="Module6/module6_out/metrics.csv")
    ap.add_argument("--out", default="Module6/figures")
    a = ap.parse_args()
    rows = read_rows(a.metrics)
    print("written:", fig1(rows, os.path.join(a.out, "fig1_benefit.png")))
    print("written:", fig2(rows, os.path.join(a.out, "fig2_fairness.png")))


if __name__ == "__main__":
    main()
