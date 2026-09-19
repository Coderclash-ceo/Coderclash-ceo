#!/usr/bin/env python3
"""Fetch live GitHub data and write stats + languages SVG cards.

Usage:
    python scripts/generate-stats.py

Set GITHUB_TOKEN (a classic PAT with no scopes is enough) to get contributions and
streaks and to avoid rate limits. Without it, those two show as "-".
The GitHub Action in .github/workflows passes the token automatically.
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)
USERNAME = json.loads((ROOT / "config" / "profile.json").read_text(encoding="utf-8"))["github"]

THEMES = {
    "dark": dict(card="#0D1117", panel="#0D1117", border="#30363D", text="#E6EDF3", muted="#8B949E", accent="#AA9BEF", link="#58A6FF"),
    "light": dict(card="#FFFFFF", panel="#FFFFFF", border="#D0D7DE", text="#24292F", muted="#57606A", accent="#6D5BD0", link="#0969DA"),
}
PALETTE = ["#3178C6", "#F1E05A", "#E34C26", "#AA9BEF", "#3DDC97", "#FF7B72", "#8B949E"]
FONT = "font-family=\"'Segoe UI',Arial,sans-serif\""


def _req(url, data=None):
    headers = {"User-Agent": "profile-stats", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data else None
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=25) as r:
        return json.load(r)


def contributions():
    """Return (total_1y, current_streak, longest_streak) or None without a token."""
    if not os.environ.get("GITHUB_TOKEN"):
        return None
    q = ('query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions '
         'weeks{contributionDays{date contributionCount}}}}}}')
    try:
        res = _req("https://api.github.com/graphql", {"query": q, "variables": {"u": USERNAME}})
        cal = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    except Exception as e:
        print("contributions unavailable:", e)
        return None
    days = sorted((d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"])
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    today = dt.date.today().isoformat()
    cur, seq = 0, [c for d, c in days if d <= today]
    if seq and seq[-1] == 0:
        seq = seq[:-1]  # today not counted yet
    for c in reversed(seq):
        if c > 0:
            cur += 1
        else:
            break
    return cal["totalContributions"], cur, longest


def collect():
    user = _req(f"https://api.github.com/users/{USERNAME}")
    repos = _req(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&type=owner")
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    langs = {}
    for r in repos:
        if r.get("fork"):
            continue
        try:
            for lang, b in _req(r["languages_url"]).items():
                langs[lang] = langs.get(lang, 0) + b
        except Exception as e:
            print("skip", r["name"], e)
    return user, stars, langs, contributions()


def fmt_size(b):
    return f"{b / 1e6:.2f} MB" if b >= 1e6 else f"{b / 1e3:.0f} kB"


def stats_card(theme, user, stars, contrib):
    t = THEMES[theme]
    c = contrib or ("-", "-", "-")
    cells = [
        (stars, "Total stars"), (user.get("public_repos", 0), "Public repos"), (user.get("followers", 0), "Followers"),
        (c[0], "Contributions (1y)"), (c[1], "Current streak"), (c[2], "Longest streak"),
    ]
    out = ""
    for i, (v, label) in enumerate(cells):
        x, y = 40 + (i % 3) * 210, 105 + (i // 3) * 78
        out += (f'<g class="f" style="animation-delay:{0.2 + i * 0.12:.2f}s">'
                f'<text x="{x}" y="{y}" {FONT} font-size="30" font-weight="700" fill="{t["text"]}">{v}</text>'
                f'<text x="{x}" y="{y + 20}" {FONT} font-size="13" fill="{t["muted"]}">{label}</text></g>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="250" viewBox="0 0 700 250">
<style>.f{{opacity:0;animation:a .6s ease forwards}}@keyframes a{{to{{opacity:1}}}}</style>
<rect x=".5" y=".5" width="699" height="249" rx="10" fill="{t['card']}" stroke="{t['border']}"/>
<text x="40" y="48" {FONT} font-size="20" font-weight="700" fill="{t['accent']}">{USERNAME}</text>
<text x="660" y="48" text-anchor="end" {FONT} font-size="13" fill="{t['muted']}">at a glance</text>
<line x1="40" y1="64" x2="660" y2="64" stroke="{t['border']}"/>
{out}</svg>'''


def languages_card(theme, langs):
    t = THEMES[theme]
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    rest = total - sum(v for _, v in top)
    if rest > 0:
        top.append(("Other", rest))
    if not langs:
        top, total = [("No data yet", 1)], 1
    bar, legend, x = "", "", 40.0
    for i, (name, v) in enumerate(top):
        w = 620 * v / total
        col = PALETTE[i % len(PALETTE)]
        bar += f'<rect x="{x:.1f}" y="88" width="{max(w, 2):.1f}" height="8" fill="{col}"/>'
        x += w
        lx, ly = 40 + (i % 2) * 320, 132 + (i // 2) * 26
        legend += (f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{col}"/>'
                   f'<text x="{lx + 18}" y="{ly}" {FONT} font-size="13" fill="{t["text"]}">{name}</text>'
                   f'<text x="{lx + 210}" y="{ly}" text-anchor="end" {FONT} font-size="12" fill="{t["muted"]}">{fmt_size(v)}</text>'
                   f'<text x="{lx + 275}" y="{ly}" text-anchor="end" {FONT} font-size="12" fill="{t["muted"]}">{100 * v / total:.1f}%</text>')
    height = 132 + ((len(top) + 1) // 2) * 26 + 10
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="700" height="{height}" viewBox="0 0 700 {height}">
<defs><clipPath id="r"><rect x="40" y="88" width="620" height="8" rx="4"/></clipPath></defs>
<rect x=".5" y=".5" width="699" height="{height - 1}" rx="10" fill="{t['card']}" stroke="{t['border']}"/>
<text x="40" y="44" {FONT} font-size="16" font-weight="600" fill="{t['link']}">{len(langs)} Languages</text>
<text x="350" y="72" text-anchor="middle" {FONT} font-size="13" fill="{t['link']}">Most used languages</text>
<g clip-path="url(#r)">{bar}</g>{legend}
</svg>'''


def main():
    try:
        user, stars, langs, contrib = collect()
    except Exception as e:
        print("Could not reach GitHub API:", e)
        print("Existing SVG files were left unchanged.")
        sys.exit(1)
    for theme in THEMES:
        (ASSETS / f"stats-{theme}.svg").write_text(stats_card(theme, user, stars, contrib), encoding="utf-8")
        (ASSETS / f"languages-{theme}.svg").write_text(languages_card(theme, langs), encoding="utf-8")
    print("Updated stats + languages cards.")


if __name__ == "__main__":
    main()
