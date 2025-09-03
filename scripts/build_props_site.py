#!/usr/bin/env python3
import argparse, json
import pandas as pd
import numpy as np
from html import escape

# ---------- helpers ----------
def fmt_odds(o):
    if pd.isna(o): return ""
    try:
        o = int(round(float(o)))
        return f"{o:+d}"
    except Exception:
        return str(o)

def prob_to_american(p):
    if p is None or (isinstance(p,float) and (np.isnan(p) or p<=0 or p>=1)): return ""
    return int(round(-100*p/(1-p))) if p>=0.5 else int(round(100*(1-p)/p))

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged_csv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="NFL-2025 — Player Props")
    ap.add_argument("--min_prob", type=float, default=0.01, help="Drop rows with model_prob < this (unless --show_unmodeled)")
    ap.add_argument("--limit", type=int, default=3000, help="Max rows to render")
    ap.add_argument("--drop_no_scorer", action="store_true", default=True, help="Hide 'No Scorer' rows")
    ap.add_argument("--show_unmodeled", action="store_true", help="Include rows with missing model_prob")
    args = ap.parse_args()

    df0 = pd.read_csv(args.merged_csv)

    # Normalize presence of key cols
    for c in ["market_std","player","home_team","away_team","bookmaker","market_prob","model_prob","model_price","price","commence_time"]:
        if c not in df0.columns: df0[c] = np.nan

    # Drop "No Scorer" if requested
    if args.drop_no_scorer and "player" in df0.columns:
        df0 = df0[df0["player"].astype(str).str.lower() != "no scorer"].copy()

    # Ensure a game display column
    df0["home_team"] = df0["home_team"].fillna("").astype(str).str.strip()
    df0["away_team"] = df0["away_team"].fillna("").astype(str).str.strip()
    df0["game"] = (df0["home_team"] + " vs " + df0["away_team"]).str.strip()

    # Display odds columns
    if "price" in df0.columns:
        df0["mkt_odds"] = df0["price"].apply(fmt_odds)
    else:
        df0["mkt_odds"] = ""

    if "model_price" in df0.columns and df0["model_price"].notna().any():
        df0["fair_odds"] = df0["model_price"].apply(fmt_odds)
    else:
        # fallback from model_prob
        if "model_prob" in df0.columns:
            df0["fair_odds"] = df0["model_prob"].apply(prob_to_american).map(fmt_odds)
        else:
            df0["fair_odds"] = ""

    # Display percentages (x100, 1 decimal)
    df0["mkt_pct"]   = (df0.get("market_prob", np.nan) * 100).round(1)
    df0["model_pct"] = (df0.get("model_prob", np.nan) * 100).round(1)

    # Edge (bps)
    if "edge_prob" in df0.columns:
        edge = df0["edge_prob"]
    else:
        edge = df0.get("model_prob", np.nan) - df0.get("market_prob", np.nan)
    df0["edge_bps"] = (edge * 10000).round(0)

    # If not showing unmodeled, filter to rows with model_prob present
    df = df0.copy()
    if not args.show_unmodeled and "model_prob" in df.columns:
        df = df[~df["model_prob"].isna()].copy()
        if args.min_prob is not None:
            df = df[df["model_prob"] >= args.min_prob].copy()

    # Sort by edge desc (modeled rows will naturally bubble up)
    df = df.sort_values("edge_bps", ascending=False, na_position="last")

    # Trim to limit
    if args.limit:
        df = df.head(args.limit).copy()

    # Select/rename fields for UI (keep only what we render)
    keep = ["game","player","bookmaker","market_std","mkt_odds","fair_odds","mkt_pct","model_pct","edge_bps","commence_time"]
    for c in keep:
        if c not in df.columns:
            df[c] = ""
    df = df[keep].copy()

    # JSON for JS
    # Ensure numbers are json-serializable (NaNs -> None)
    records = json.loads(df.to_json(orient="records"))
    jsdata = json.dumps(records)  # safe literal insertion

    title_html = escape(args.title)

    # -------- HTML (no f-string inside JS/CSS) --------
    html = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>""" + title_html + """</title>
<style>
:root {
  --bg: #0b0b10;
  --card: #14141c;
  --muted: #9aa0a6;
  --text: #e8eaed;
  --accent: #6ee7ff;
  --accent2: #a78bfa;
  --border: #23232e;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
  background: var(--bg); color: var(--text);
}
h1 { margin: 0 0 8px; font-size: 22px; font-weight: 700; letter-spacing: .2px; }
.small { color: var(--muted); font-size: 12px; margin-bottom: 16px; }
.card {
  background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.00));
  border: 1px solid var(--border);
  border-radius: 16px; padding: 16px; margin-bottom: 16px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.02), 0 12px 40px rgba(0,0,0,0.35);
}
.controls { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
select, input {
  background: var(--card); color: var(--text); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px 12px; outline: none;
}
select:focus, input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(110,231,255,.15); }
.badge { display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; color:#111; background: var(--accent); }
.table-wrap { overflow:auto; border:1px solid var(--border); border-radius: 14px; }
table { border-collapse: collapse; width: 100%; min-width: 920px; }
th, td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
th { text-align: left; position: sticky; top: 0; background: var(--card); z-index: 1; font-size: 12px; color: var(--muted); letter-spacing: .2px; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
tr:hover td { background: rgba(255,255,255,0.02); }
footer { color: var(--muted); font-size: 12px; margin-top: 16px; }

/* Buttons */
a.button {
  display: inline-block;
  margin: 8px 0;
  padding: 8px 14px;
  border-radius: 10px;
  text-decoration: none;
  font-weight: 600;
  color: #111;
  background: var(--accent2);
  border: 1px solid var(--border);
  transition: background .2s, color .2s;
}
a.button:hover { background: var(--accent); }

/* subtle link for breadcrumbs */
.linklike { color: var(--accent2); text-decoration:none; border-bottom:1px dotted var(--accent2); }
</style>
</head>
<body>

  <div class="card">
    <h1>""" + title_html + """</h1>
    <div class="small">Select <span class="badge">Bet</span> → Game → Player. Optional: Book & search. Sorted by Edge (bps) by default.</div>
    <p><a href="../" class="button">⬅ Back to Home</a></p>

    <div class="controls">
      <select id="market"><option value="">Bet (market)</option></select>
      <select id="game"><option value="">Game</option></select>
      <select id="player"><option value="">Player</option></select>
      <select id="book"><option value="">Book</option></select>
      <input id="q" type="search" placeholder="Search player / team / book…" />
    </div>

    <div class="small" style="margin-top:10px;">
      <span id="count"></span> · Tip: “No Scorer” is hidden.
      <span style="float:right;"><a class="linklike" href="../">Back to site root</a></span>
    </div>
  </div>

  <div class="card table-wrap">
    <table id="tbl">
      <thead>
        <tr>
          <th>Game</th><th>Player</th><th>Book</th><th>Bet</th>
          <th class="num">Mkt Odds</th><th class="num">Fair</th>
          <th class="num">Mkt %</th><th class="num">Model %</th>
          <th class="num">Edge (bps)</th><th>Kick</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <footer>Generated from merged CSV on your machine. Dark theme, zero dependencies.</footer>

<script>
const DATA = """ + jsdata + """;

function uniqueSorted(arr) {
  return [...new Set(arr.filter(Boolean))].sort((a,b)=>a.localeCompare(b));
}

const state = { market: "", game: "", player: "", book: "", q: "" };

const selMarket = document.getElementById("market");
const selGame   = document.getElementById("game");
const selPlayer = document.getElementById("player");
const selBook   = document.getElementById("book");
const inputQ    = document.getElementById("q");
const tbody     = document.querySelector("#tbl tbody");
const countEl   = document.getElementById("count");

function hydrateSelectors() {
  uniqueSorted(DATA.map(r => r.market_std)).forEach(v => {
    const o = document.createElement("option"); o.value=v; o.textContent=v; selMarket.appendChild(o);
  });
  uniqueSorted(DATA.map(r => r.bookmaker)).forEach(v => {
    const o = document.createElement("option"); o.value=v; o.textContent=v; selBook.appendChild(o);
  });
  rebuildDependentSelectors();
}

function rebuildDependentSelectors() {
  const base = DATA.filter(r => (!state.market || r.market_std===state.market) &&
                                (!state.book   || r.bookmaker===state.book));
  const games = uniqueSorted(base.map(r => r.game));
  selGame.innerHTML = '<option value="">Game</option>' + games.map(g=>`<option value="${g}">${g}</option>`).join("");
  if (games.includes(state.game)) selGame.value = state.game; else state.game = "";

  const base2 = base.filter(r => (!state.game || r.game === state.game));
  const players = uniqueSorted(base2.map(r => r.player));
  selPlayer.innerHTML = '<option value="">Player</option>' + players.map(p=>`<option value="${p}">${p}</option>`).join("");
  if (players.includes(state.player)) selPlayer.value = state.player; else state.player = "";
}

function render() {
  const q = state.q.trim().toLowerCase();
  const rows = DATA.filter(r =>
    (!state.market || r.market_std === state.market) &&
    (!state.game   || r.game       === state.game) &&
    (!state.player || r.player     === state.player) &&
    (!state.book   || r.bookmaker  === state.book) &&
    (!q || (r.player+" "+r.bookmaker+" "+r.game).toLowerCase().includes(q))
  ).sort((a,b) => (b.edge_bps ?? -1) - (a.edge_bps ?? -1));

  countEl.textContent = rows.length + " rows";

  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.game || ""}</td>
      <td>${r.player || ""}</td>
      <td>${r.bookmaker || ""}</td>
      <td>${r.market_std || ""}</td>
      <td class="num">${r.mkt_odds ?? ""}</td>
      <td class="num">${r.fair_odds ?? ""}</td>
      <td class="num">${(r.mkt_pct ?? "").toString()}</td>
      <td class="num">${(r.model_pct ?? "").toString()}</td>
      <td class="num" style="color:${
        (r.edge_bps === "" || r.edge_bps === null || r.edge_bps === undefined)
          ? "var(--muted)"
          : (r.edge_bps > 0 ? "#4ade80" : "#f87171")
      }">${(r.edge_bps ?? "").toString()}</td>
      <td>${r.commence_time || ""}</td>
    </tr>
  `).join("");
}

// events
selMarket.addEventListener("change", e => { state.market=e.target.value; rebuildDependentSelectors(); render(); });
selGame  .addEventListener("change", e => { state.game  =e.target.value; rebuildDependentSelectors(); render(); });
selPlayer.addEventListener("change", e => { state.player=e.target.value; render(); });
selBook  .addEventListener("change", e => { state.book  =e.target.value; rebuildDependentSelectors(); render(); });
inputQ   .addEventListener("input",  e => { state.q     =e.target.value; render(); });

// init
hydrateSelectors(); render();
</script>
</body></html>
"""

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[props_site] wrote {args.out} with {len(df)} rows (from {len(df0)} source rows)")

if __name__ == "__main__":
    main()
