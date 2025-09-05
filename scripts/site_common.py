#!/usr/bin/env python3
# Shared helpers for site pages (branding, nav, labels, small formatters)

from datetime import datetime, timezone
import math

BRAND = "Fourth & Value"

NAV_LINKS = [
    ("Home", "/index.html"),
    ("Props", "/props/index.html"),
    ("Consensus", "/props/consensus.html"),
    ("Top Picks", "/props/top.html"),
]

def nav_html(active: str = "") -> str:
    def li(label, href, is_active):
        klass = "font-semibold text-white" if is_active else "text-gray-300 hover:text-white"
        return f'<a class="{klass} px-3 py-2 rounded-lg" href="{href}">{label}</a>'
    items = "".join(li(lbl, href, active.lower()==lbl.lower()) for (lbl, href) in NAV_LINKS)
    return f"""
<header class="w-full sticky top-0 z-20 bg-neutral-900/85 backdrop-blur border-b border-neutral-800">
  <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
    <div class="text-xl font-black tracking-tight text-white">{BRAND}</div>
    <nav class="flex gap-1">{items}</nav>
  </div>
</header>
"""

# Pretty market labels + common synonyms
PRETTY_MAP = {
    "player_rush_yds": "Rushing Yards",
    "player_passing_yds": "Passing Yards",
    "player_pass_yds": "Passing Yards",
    "player_rec_yds": "Receiving Yards",
    "player_receptions": "Receptions",
    "player_anytime_td": "Anytime TD",
    "anytime_td": "Anytime TD",
    # common feed variants
    "player reception yds": "Receiving Yards",
    "player reception yards": "Receiving Yards",
    "player rushing yds": "Rushing Yards",
    "player passing yds": "Passing Yards",
}

def pretty_market(m):
    if not m: return ""
    s = str(m).strip()
    key = s.lower().replace("_"," ")
    return PRETTY_MAP.get(key, s.replace("_"," ").title())

def fmt_odds_american(x):
    if x is None or (isinstance(x, float) and math.isnan(x)): return ""
    try:
        x = int(round(float(x)))
        return f"{x:+d}"
    except Exception:
        return str(x)

def kickoff_et(iso_or_str):
    """Format ISO/UTC-ish kickoff to 'Sun 1:00 PM ET'. Safe if already formatted."""
    if not iso_or_str: return ""
    s = str(iso_or_str)
    # if already pretty like "Sun 1 p.m. ET" or similar, just return it
    if (" ET" in s and any(ch.isalpha() for ch in s[:3])) or ("M ET" in s):
        return s
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)
        return dt.strftime("%a %-I:%M %p ET")
    except Exception:
        return s
