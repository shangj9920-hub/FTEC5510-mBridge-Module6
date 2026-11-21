# -*- coding: utf-8 -*-
"""make_appendix_figures.py -- the proposal 5.2 figures that are not the two core ones.

    fig3_queue_length.png      queue length over simulation time (baseline, surge)
    fig4_liquidity.png         RMB available balance over time (baseline, surge)
    fig5_delay_distribution.png  p50/p90/p95/p99 of settlement delay by priority

Inputs: `series.csv` (written by run_module6.py, one row per time step) and
`metrics.csv` (for the delay quantiles). Pillow only, no matplotlib.

    python module6/make_appendix_figures.py --metrics evidence/metrics.csv `
        --series evidence/series.csv --out evidence/figures
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics

from PIL import Image, ImageDraw, ImageFont

FONT = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"
S = 2
STRATS = ["S0", "S1", "S2", "S3", "S4"]
COLORS = {"S0": (0x9A, 0xA5, 0xB1), "S1": (0x5B, 0x8D, 0xEF), "S2": (0x30, 0xA4, 0x6C),
          "S3": (0xF2, 0xA6, 0x5B), "S4": (0xD9, 0x4F, 0x4F)}
TITLE = {"baseline": "Normal", "payment_surge": "Payment surge"}


def F(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, int(size * S))


class Canvas:
    def __init__(self, w, h):
        self.img = Image.new("RGB", (w * S, h * S), (255, 255, 255))
        self.d = ImageDraw.Draw(self.img)

    def text(self, xy, s, size=11, bold=False, fill=(30, 30, 30), anchor="la"):
        self.d.text((xy[0] * S, xy[1] * S), s, font=F(size, bold), fill=fill, anchor=anchor)

    def line(self, xy, fill=(220, 224, 230), width=1):
        self.d.line([(x * S, y * S) for x, y in xy], fill=fill, width=max(1, int(width * S)))

    def poly(self, pts, color, width=2):
        self.d.line([(x * S, y * S) for x, y in pts], fill=color, width=max(1, int(width * S)),
                    joint="curve")

    def rect(self, box, fill):
        self.d.rectangle([box[0] * S, box[1] * S, box[2] * S, box[3] * S], fill=fill)

    def save(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.img.save(path, dpi=(200, 200))


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def group_series(rows, scenario, key, scale=1.0):
    out = {}
    for r in rows:
        if r["scenario_id"] != scenario:
            continue
        out.setdefault(r["strategy_id"], []).append((float(r["time"]), float(r[key]) * scale))
    for v in out.values():
        v.sort()
    return out


def line_panel(cv, box, data, title, ylabel, xmax, ymax, legend=False):
    x0, y0, x1, y1 = box
    cv.text(((x0 + x1) / 2, y0 - 26), title, 12, True, anchor="ma")
    for i in range(5):
        yv = ymax * i / 4
        yy = y1 - (y1 - y0) * i / 4
        cv.line([(x0, yy), (x1, yy)], (238, 241, 246), 1)
        cv.text((x0 - 6, yy), f"{yv:,.0f}", 8, False, (150, 150, 150), anchor="rm")
    cv.line([(x0, y0), (x0, y1)], (170, 176, 186), 1)
    cv.line([(x0, y1), (x1, y1)], (170, 176, 186), 1)
    for i in range(5):
        xv = xmax * i / 4
        xx = x0 + (x1 - x0) * i / 4
        cv.text((xx, y1 + 6), f"{xv / 3600:.0f}h", 8, False, (150, 150, 150), anchor="ma")
    cv.text((x0 + 4, y0 - 9), ylabel, 9, False, (120, 124, 132))
    for st in STRATS:
        pts = data.get(st)
        if not pts:
            continue
        xy = [(x0 + (x1 - x0) * min(t, xmax) / xmax,
               y1 - (y1 - y0) * min(v, ymax) / ymax) for t, v in pts]
        cv.poly(xy, COLORS[st], 1.6)
    if legend:
        lx = x0
        for st in STRATS:
            cv.rect((lx, y1 + 20, lx + 10, y1 + 28), COLORS[st])
            cv.text((lx + 14, y1 + 24), st, 8, False, (80, 80, 80), anchor="lm")
            lx += 46


def fig_time(series, key, scale, title, subtitle, ylabel, out, scenarios=("baseline", "payment_surge")):
    cv = Canvas(1080, 640)
    cv.text((24, 18), title, 17, True)
    cv.text((24, 45), subtitle, 10, False, (100, 100, 100))
    width = 1000
    for i, scen in enumerate(scenarios):
        y0 = 100 + i * 260
        data = group_series(series, scen, key, scale)
        xmax = max(t for v in data.values() for t, _ in v)
        ymax = max(v for v in data.values() for _, v in v)
        ymax = max(1.0, ymax * 1.1)
        line_panel(cv, (88, y0, 88 + width, y0 + 190),
                   data, TITLE[scen] + " scenario",
                   ylabel, xmax, ymax, legend=(i == 1))
    cv.save(out)
    return out


def fig_distribution(metrics, out, scenario="payment_surge"):
    quant = [("p50_delay", "p50"), ("p90_delay", "p90"), ("p95_delay", "p95"), ("p99_delay", "p99")]
    cv = Canvas(900, 520)
    cv.text((24, 18), "Figure 5  Delay distribution, payment surge scenario", 16, True)
    cv.text((24, 44), "Settlement delay quantiles (s), mean over 30 seeds; S1 vs S2", 10, False, (100, 100, 100))

    def val(strategy, prio, key):
        v = [float(r[f"{prio}.{key}"]) for r in metrics
             if r["scenario_id"] == scenario and r["strategy_id"] == strategy]
        return statistics.mean(v)

    panels = [("NORMAL", (80, 96, 470, 430)), ("URGENT", (500, 96, 880, 430))]
    for prio, (x0, y0, x1, y1) in panels:
        cv.text(((x0 + x1) / 2, y0 - 24), f"{prio} payments", 12, True, anchor="ma")
        vals = [val(st, prio, k) for st in ("S1", "S2") for k, _ in quant]
        ymax = max(vals) * 1.15
        for i in range(5):
            yy = y1 - (y1 - y0) * i / 4
            cv.line([(x0, yy), (x1, yy)], (238, 241, 246), 1)
            cv.text((x0 - 6, yy), f"{ymax * i / 4:,.0f}", 8, False, (150, 150, 150), anchor="rm")
        cv.line([(x0, y1), (x1, y1)], (170, 176, 186), 1)
        slot = (x1 - x0) / len(quant)
        bw = slot * 0.3
        for gi, st in enumerate(("S1", "S2")):
            for qi, (key, _lab) in enumerate(quant):
                v = val(st, prio, key)
                h = (y1 - y0) * v / ymax
                bx = x0 + slot * (qi + 0.5) + (gi - 0.5) * bw * 1.1 - bw / 2
                cv.rect((bx, y1 - h, bx + bw, y1), COLORS[st])
                cv.text((bx + bw / 2, y1 - h - 3), f"{v:,.0f}", 7, False, (90, 90, 90), anchor="mb")
        for qi, (_key, lab) in enumerate(quant):
            cv.text((x0 + slot * (qi + 0.5), y1 + 6), lab, 8, True, (110, 110, 110), anchor="ma")
    lx = 80
    for st in ("S1", "S2"):
        cv.rect((lx, 470, lx + 12, 480), COLORS[st])
        cv.text((lx + 16, 475), f"{st} " + ("(skippable FIFO)" if st == "S1" else "(dynamic)"),
                9, False, (70, 70, 70), anchor="lm")
        lx += 150
    cv.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", default="evidence/metrics.csv")
    ap.add_argument("--series", default="evidence/series.csv")
    ap.add_argument("--out", default="evidence/figures")
    a = ap.parse_args()
    series = read_csv(a.series)
    metrics = read_csv(a.metrics)
    print("written:", fig_time(series, "queue_len", 1.0,
                               "Figure 3  Queue length over simulation time",
                               "Number of payments that have arrived and are not settled yet, "
                               "one run (seed 20001)",
                               "queue length (payments)", os.path.join(a.out, "fig3_queue_length.png")))
    print("written:", fig_time(series, "rmb_total", 1e-6,
                               "Figure 4  RMB balance over simulation time",
                               "RMB held (million), one run (seed 20001); the available path is in series.csv",
                               "RMB million held", os.path.join(a.out, "fig4_liquidity.png")))
    print("written:", fig_distribution(metrics, os.path.join(a.out, "fig5_delay_distribution.png")))


if __name__ == "__main__":
    main()
