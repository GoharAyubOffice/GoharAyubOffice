#!/usr/bin/env python3
"""
Generates an animated 2D-platformer contribution graph as an SVG,
plus a top-languages card. Both are written to ./dist.

Run inside GitHub Actions with GITHUB_TOKEN + GH_USER set.
Run locally with no token to render demo data.
"""

import json
import math
import os
import sys
import urllib.request
from datetime import date

USER = os.environ.get("GH_USER", "GoharAyubOffice")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "dist")

# ---------------------------------------------------------------- theming

THEMES = {
    "dark": {
        "bg": "none",
        "empty": "#151b23",
        "grid": ["#0d4429", "#026d33", "#26a540", "#39d353"],
        "dim": "#1b2430",
        "ground": "#2b3440",
        "text": "#8b949e",
        "title": "#e6edf3",
        "hero": "#ff7a45",
        "hero_dark": "#c9491f",
        "spark": "#ffd75e",
    },
    "light": {
        "bg": "none",
        "empty": "#ebedf0",
        "grid": ["#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "dim": "#dfe3e8",
        "ground": "#c8ced6",
        "text": "#57606a",
        "title": "#1f2328",
        "hero": "#e8590c",
        "hero_dark": "#a63a02",
        "spark": "#d4a017",
    },
}

# ---------------------------------------------------------------- geometry

WEEKS = 53
CELL = 12
GAP = 3
PITCH = CELL + GAP
PAD_L = 26
PAD_T = 46
GROUND_Y = PAD_T + 7 * PITCH + 10
W = PAD_L * 2 + WEEKS * PITCH
H = GROUND_Y + 46

HOP = 0.30          # seconds per week
SAMPLES = 6         # parabola samples per hop
TAIL = 1.4          # pause at the end before looping
TOTAL = WEEKS * HOP + TAIL

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------------------------------------------------------------- data

QUERY = """
query($login:String!) {
  user(login:$login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          firstDay
          contributionDays { contributionCount date weekday }
        }
      }
    }
  }
}
"""


def fetch_contributions():
    if not TOKEN:
        return demo_weeks(), None
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "platformer-contrib-graph",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = []
    for wk in cal["weeks"]:
        days = [0] * 7
        for d in wk["contributionDays"]:
            days[d["weekday"]] = d["contributionCount"]
        weeks.append({"first": wk["firstDay"], "days": days})
    return weeks, cal["totalContributions"]


def demo_weeks():
    """Deterministic pseudo-data so the layout can be checked offline."""
    weeks = []
    for w in range(WEEKS):
        days = []
        for d in range(7):
            v = int(4 * abs(math.sin(w * 0.41 + d * 0.9)) * (0.4 + 0.6 * math.cos(w * 0.13) ** 2))
            days.append(max(0, v - (1 if d in (0, 6) else 0)))
        weeks.append({"first": f"2026-01-{(w % 28) + 1:02d}", "days": days})
    return weeks


def level_of(count, ceiling):
    """Map a day's contribution count onto a 0-4 intensity level."""
    if count <= 0:
        return 0
    step = max(1, ceiling / 4)
    return min(4, int(math.ceil(count / step)))


# ---------------------------------------------------------------- sprite

def sprite(t):
    """A small pixel character, drawn from rects. Origin at its feet, centred."""
    p = 2.6  # pixel unit
    body, dark, eye = t["hero"], t["hero_dark"], "#0d1117" if t is THEMES["dark"] else "#ffffff"

    def r(x, y, w, h, fill):
        return f'<rect x="{x*p}" y="{y*p}" width="{w*p}" height="{h*p}" fill="{fill}"/>'

    # body block, 7px wide, 8px tall, feet at y=0 so we build upward with negatives
    parts = [
        r(-3, -8, 6, 6, body),      # torso/head
        r(-3, -9, 6, 1, dark),      # cap
        r(-4, -7, 1, 3, dark),      # left arm
        r(3, -7, 1, 3, dark),       # right arm
        r(-2, -7, 1, 1, eye),       # eye
        r(1, -7, 1, 1, eye),        # eye
    ]
    legs_a = r(-3, -2, 2, 2, dark) + r(1, -2, 2, 2, dark)
    legs_b = r(-2, -2, 2, 2, dark) + r(0, -2, 2, 2, dark)

    return f"""<g class="hero">
  {''.join(parts)}
  <g><g>{legs_a}</g>
    <animate attributeName="opacity" values="1;0;1" keyTimes="0;0.5;1" dur="0.24s" repeatCount="indefinite"/>
  </g>
  <g opacity="0">{legs_b}
    <animate attributeName="opacity" values="0;1;0" keyTimes="0;0.5;1" dur="0.24s" repeatCount="indefinite"/>
  </g>
</g>"""


# ---------------------------------------------------------------- svg

def build(weeks, total, theme_name):
    t = THEMES[theme_name]
    ceiling = max((max(w["days"]) for w in weeks), default=1) or 1

    # per-week platform: stack height = number of active days that week
    tops, stacks = [], []
    for w in weeks:
        levels = sorted([level_of(c, ceiling) for c in w["days"]], reverse=True)
        stack = [l for l in levels if l > 0]
        stacks.append(stack)
        tops.append(GROUND_Y - len(stack) * PITCH)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="\'Segoe UI\',Ubuntu,Helvetica,sans-serif">'
    ]

    # ---- header
    label = f"{total:,} contributions in the last year" if total is not None else "the last year, as a level"
    parts.append(
        f'<text x="{PAD_L}" y="24" fill="{t["title"]}" font-size="15" font-weight="600">'
        f'{USER}</text>'
        f'<text x="{PAD_L}" y="40" fill="{t["text"]}" font-size="11">{label}</text>'
    )

    # ---- month ticks
    seen = set()
    for i, w in enumerate(weeks):
        try:
            m = int(w["first"].split("-")[1])
        except (ValueError, IndexError):
            continue
        if m not in seen and i < WEEKS - 2:
            seen.add(m)
            x = PAD_L + i * PITCH
            parts.append(
                f'<text x="{x}" y="{GROUND_Y + 26}" fill="{t["text"]}" font-size="9">{MONTHS[m-1]}</text>'
            )

    # ---- ground line
    parts.append(
        f'<rect x="{PAD_L - 6}" y="{GROUND_Y + 2}" width="{WEEKS * PITCH + 6}" height="3" '
        f'rx="1.5" fill="{t["ground"]}"/>'
    )

    # ---- platforms: each cell lights up as the hero reaches its column
    for i, stack in enumerate(stacks):
        x = PAD_L + i * PITCH
        reach = (i * HOP) / TOTAL
        if not stack:
            y = GROUND_Y - PITCH
            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{t["empty"]}" opacity="0.55"/>'
            )
            continue
        for j, lvl in enumerate(stack):
            y = GROUND_Y - (j + 1) * PITCH
            lit = t["grid"][lvl - 1]
            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" '
                f'fill="{lit}" opacity="0.32">'
                f'<animate attributeName="opacity" values="0.32;1;1;0.32" '
                f'keyTimes="0;{reach:.5f};0.985;1" calcMode="linear" '
                f'dur="{TOTAL:.2f}s" repeatCount="indefinite"/></rect>'
            )

    # ---- hero flight path
    xs, ys, times = [], [], []
    for i in range(WEEKS):
        y0 = tops[i]
        y1 = tops[i + 1] if i + 1 < WEEKS else tops[i]
        x0 = PAD_L + i * PITCH + CELL / 2
        x1 = x0 + PITCH
        lift = 22 + abs(y1 - y0) * 0.35
        for s in range(SAMPLES):
            k = s / SAMPLES
            xs.append(x0 + (x1 - x0) * k)
            ys.append(y0 + (y1 - y0) * k - lift * 4 * k * (1 - k))
            times.append((i + k) * HOP / TOTAL)
    xs.append(PAD_L + WEEKS * PITCH + CELL / 2)
    ys.append(tops[-1])
    times.append(1.0)

    values = ";".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    keytimes = ";".join(f"{k:.5f}" for k in times)

    parts.append(f'<g>{sprite(t)}'
                 f'<animateTransform attributeName="transform" type="translate" '
                 f'values="{values}" keyTimes="{keytimes}" '
                 f'dur="{TOTAL:.2f}s" calcMode="linear" repeatCount="indefinite"/></g>')

    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------- languages

def fetch_languages():
    if not TOKEN:
        return [("C#", 41.2), ("TypeScript", 22.8), ("Python", 14.6),
                ("JavaScript", 11.1), ("HTML", 6.0), ("Shell", 4.3)]
    headers = {"Authorization": f"bearer {TOKEN}", "User-Agent": "lang-card"}
    totals = {}
    page = 1
    while page <= 4:
        req = urllib.request.Request(
            f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}&type=owner",
            headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            repos = json.load(r)
        if not repos:
            break
        for repo in repos:
            if repo.get("fork"):
                continue
            lr = urllib.request.Request(repo["languages_url"], headers=headers)
            try:
                with urllib.request.urlopen(lr, timeout=30) as r2:
                    for lang, bytes_ in json.load(r2).items():
                        totals[lang] = totals.get(lang, 0) + bytes_
            except Exception:
                continue
        page += 1
    grand = sum(totals.values()) or 1
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
    return [(k, v * 100 / grand) for k, v in ranked]


LANG_COLORS = {
    "C#": "#178600", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "Python": "#3572A5", "HTML": "#e34c26", "CSS": "#563d7c",
    "Shell": "#89e051", "ShaderLab": "#222c37", "HLSL": "#aace60",
    "Java": "#b07219", "Kotlin": "#A97BFF", "Dart": "#00B4AB",
    "C++": "#f34b7d", "Liquid": "#67b8de", "Ruby": "#701516",
}


def build_langs(langs, theme_name):
    t = THEMES[theme_name]
    w, pad = 420, 20
    h = pad * 2 + 34 + len(langs) * 22
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}" font-family="\'Segoe UI\',Ubuntu,sans-serif">']
    p.append(f'<text x="{pad}" y="{pad+12}" fill="{t["title"]}" font-size="14" '
             f'font-weight="600">Most Used Languages</text>')

    # stacked bar
    bx, by, bw = pad, pad + 24, w - pad * 2
    off = 0.0
    p.append(f'<clipPath id="rr"><rect x="{bx}" y="{by}" width="{bw}" height="9" rx="4.5"/></clipPath>')
    p.append('<g clip-path="url(#rr)">')
    for name, pct in langs:
        seg = bw * pct / 100
        p.append(f'<rect x="{bx+off:.1f}" y="{by}" width="{seg:.1f}" height="9" '
                 f'fill="{LANG_COLORS.get(name, "#8b949e")}"/>')
        off += seg
    p.append('</g>')

    for i, (name, pct) in enumerate(langs):
        y = by + 28 + i * 22
        p.append(f'<circle cx="{pad+5}" cy="{y-4}" r="5" fill="{LANG_COLORS.get(name, "#8b949e")}"/>')
        p.append(f'<text x="{pad+18}" y="{y}" fill="{t["title"]}" font-size="12">{name}</text>')
        p.append(f'<text x="{w-pad}" y="{y}" fill="{t["text"]}" font-size="12" '
                 f'text-anchor="end">{pct:.1f}%</text>')
    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------------------- main

def main():
    os.makedirs(OUT, exist_ok=True)
    weeks, total = fetch_contributions()
    weeks = weeks[-WEEKS:]
    while len(weeks) < WEEKS:
        weeks.insert(0, {"first": "", "days": [0] * 7})

    for theme in ("dark", "light"):
        suffix = "-dark" if theme == "dark" else ""
        with open(f"{OUT}/platformer{suffix}.svg", "w") as f:
            f.write(build(weeks, total, theme))

    langs = fetch_languages()
    for theme in ("dark", "light"):
        suffix = "-dark" if theme == "dark" else ""
        with open(f"{OUT}/languages{suffix}.svg", "w") as f:
            f.write(build_langs(langs, theme))

    print(f"wrote 4 files to {OUT}/")


if __name__ == "__main__":
    main()
