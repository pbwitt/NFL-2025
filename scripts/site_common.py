#!/usr/bin/env python3
from datetime import datetime
from zoneinfo import ZoneInfo

# ---- market display ----
PRETTY_MAP = {
    "player_pass_yds": "Passing Yards",
    "player_pass_tds": "Passing TDs",
    "player_pass_attempts": "Pass Attempts",
    "player_pass_completions": "Completions",
    "player_interceptions": "Interceptions Thrown",
    "player_rush_yds": "Rushing Yards",
    "player_rush_tds": "Rushing TDs",
    "player_rec_yds": "Receiving Yards",
    "player_receptions": "Receptions",
    "player_anytime_td": "Anytime TD",
    "player_longest_reception": "Longest Reception",
    "player_longest_rush": "Longest Rush",
}
def pretty_market(m): return PRETTY_MAP.get(str(m).strip(), str(m).replace("_"," ").title())
# Add to scripts/site_common.py
def normalize_display(df):
    """
    Ensure display-friendly columns exist:
      - market_disp  : pretty market name
      - name_disp    : leg label (Over/Under/Yes/No/etc.)
      - kick_et      : kickoff formatted in ET
      - price_disp   : American odds as +/-
    Works in-place and also returns df for chaining.
    """
    import pandas as pd

    # Market → "Rushing Yards", etc.
    if "market_disp" not in df.columns and "market" in df.columns:
        df["market_disp"] = df["market"].map(pretty_market)

    # Leg label (safe string)
    if "name_disp" not in df.columns and "name" in df.columns:
        df["name_disp"] = df["name"].fillna("").astype(str)

    # Kick in ET
    if "kick_et" not in df.columns:
        if "commence_time" in df.columns:
            df["kick_et"] = df["commence_time"].astype(str).map(to_kick_et)
        else:
            df["kick_et"] = ""

    # American odds display
    if "price_disp" not in df.columns and "price" in df.columns:
        df["price_disp"] = df["price"].map(fmt_odds)

    return df
# --- Safe merge that avoids overlapping payload columns ---
def safe_merge(left, right, on, how="left", suffixes=("", "_r"), validate=None):
    """
    Merge while only pulling NEW columns from `right`.
    - `on`: str or list of keys present in both frames.
    - Drops overlapping non-key columns from `right` to avoid pandas overlap error.
    - Optional `validate` (e.g., "many_to_one") to catch key cardinality issues.
    """
    import pandas as pd
    if isinstance(on, str): on = [on]
    for k in on:
        if k not in left.columns:
            raise KeyError(f"left missing join key: {k}")
        if k not in right.columns:
            raise KeyError(f"right missing join key: {k}")

    # Keep keys + only columns from `right` that don't exist on `left` (unless it's a key)
    keep = on + [c for c in right.columns if (c not in left.columns) or (c in on)]
    right_narrow = right[keep].copy()

    return pd.merge(
        left, right_narrow, on=on, how=how, suffixes=suffixes, validate=validate
    )

# ---- odds/prob helpers ----
def american_to_prob(odds):
    if odds is None: return None
    o = float(odds)
    return (100.0/(o+100.0)) if o>0 else (abs(o)/(abs(o)+100.0))

def prob_to_american(p):
    if p is None or p<=0 or p>=1: return None
    return int(round(-100*p/(1-p))) if p>=0.5 else int(round(100*(1-p)/p))

def fmt_pct(x): return "" if x is None else f"{100.0*float(x):.1f}%"
def fmt_odds(o):
    if o is None: return ""
    try: return f"{int(round(float(o))):+d}"
    except: return str(o)

def to_kick_et(s):
    """Accepts ISO string; returns like 'Sun 1 p.m.' Eastern."""
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(ZoneInfo("America/New_York"))
        return dt.strftime("%a %-I p.m.").replace("AM","a.m.").replace("PM","p.m.")
    except: return ""
# ---- nav ----
def nav_html(depth=1, active="home"):
    base = "../"*depth
    items = [
        ("Home", f"{base}index.html", "home"),
        ("Props", f"{base}props/index.html", "props"),
        ("Consensus", f"{base}props/consensus.html", "consensus"),
        ("Top Picks", f"{base}props/top.html", "top"),
    ]
    def cls(slug): return "text-white font-semibold" if slug==active else "text-gray-300 hover:text-white"
    links = "".join([f'<a class="{cls(slug)} px-3 py-2 rounded-xl" href="{href}">{label}</a>' for (label,href,slug) in items])
    return f"""
<nav class="w-full sticky top-0 z-40 bg-gray-900/80 backdrop-blur supports-[backdrop-filter]:bg-gray-900/60 border-b border-gray-800">
  <div class="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
    <div class="text-white font-bold">NFL-2025</div>
    <div class="flex items-center gap-1">{links}</div>
  </div>
</nav>"""
