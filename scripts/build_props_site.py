# scripts/build_props_site.py
#!/usr/bin/env python3
import argparse, pandas as pd, numpy as np
from html import escape

def fmt_odds(o):
    if pd.isna(o): return ""
    try:
        o = int(round(float(o)))
        return f"{o:+d}"
    except Exception:
        return str(o)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged_csv", required=True)  # data/props/props_with_model_weekX.csv
    ap.add_argument("--out", required=True)         # docs/props/index.html
    ap.add_argument("--title", default="NFL Props")
    ap.add_argument("--min_prob", type=float, default=0.01)  # hide super tiny modeled probs
    ap.add_argument("--limit", type=int, default=2000)       # render up to this many rows
    ap.add_argument("--drop_no_scorer", action="store_true", default=True)
    args = ap.parse_args()

    df = pd.read_csv(args.merged_csv)

    # normalize & guard
    for c in ["market_std","player","home_team","away_team","bookmaker"]:
        if c not in df.columns: df[c] = ""
        df[c] = df[c].astype(str)

    # filter: drop "No Scorer"
    if args.drop_no_scorer:
        df = df[df["player"].str.lower() != "no scorer"].copy()

    # keep rows with a model
    if "model_prob" in df.columns:
        df = df[~df["model_prob"].isna()].copy()

    # optional: hide ultra-low model probs
    df = df[df["model_prob"] >= args.min_prob].copy()

    # derived columns
    if "price" in df.columns:
        df["mkt_odds"] = df["price"].apply(fmt_odds)
    else:
        df["mkt_odds"] = ""

    if "model_price" in df.columns:
        df["fair_odds"] = df["model_price"].apply(fmt_odds)
    else:
        # fallback from prob if needed
        def _prob2odds(p):
            if not (0 < p < 1): return ""
            return fmt_odds(-100 * p/(1-p) if p >= 0.5 else 100 * (1-p)/p)
        df["fair_odds"] = df.get("model_prob", pd.Series(dtype=float)).apply(_prob2odds)

    df["mkt_pct"]   = (df.get("market_prob", np.nan) * 100).round(1)
    df["model_pct"] = (df.get("model_prob", np.nan) * 100).round(1)
    df["edge_bps"]  = ((df.get("model_prob", np.nan) - df.get("market_prob", np.nan)) * 10000).round(0)

    # game key
    df["game"] = df["home_team"].str.strip() + " vs " + df["away_team"].str.strip()

    # pick the columns to expose to the UI
    keep = [c for c in [
        "home_team","away_team","game","player","bookmaker","market_std",
        "mkt_odds","fair_odds","mkt_pct","model_pct","edge_bps",
        "commence_time","game_id","player_key"
    ] if c in df.columns] + [c for c in ["mkt_odds","fair_odds","mkt_pct","model_pct","edge_bps"] if c not in df.columns]

    # sort by edge desc by default
    if "edge_bps" in df.columns:
        df = df.sort_values("edge_bps", ascending=False)

    # truncate to keep the page snappy
    df = df[keep].head(args.limit).copy()

    # unique filter values
    markets = sorted([m for m in df["market_std"].dropna().unique() if m])
    games   = sorted([g for g in df["game"].dropna().unique() if g])
    players = sorted([p for p in df["player"].dropna().unique() if p])
    books   = sorted([b for b in df["bookmaker"].dropna().unique() if b])

    # dump data as JSON (safe-ish)
    def _row(rec):
        obj = {k: ("" if pd.isna(v) else v) for k,v in rec.items()}
        # ensure types are plain JSON
        for k in ["mkt_pct","model_pct","edge_bps"]:
            if k in obj and obj[k] != "":
                try: obj[k] = float(obj[k])
                except: pass
        return obj

    data_json = "[" + ",".join(
        [("{"+",".join([f"\"{escape(k)}\": " + (f"\"{escape(str(v))}\"" if isinstance(v,str) else (str(v).lower() if isinstance(v,bool) else (f"{v}" if v != "" else "\"\""))) for k,v in _row(rec).items()])+"}")
         for rec in df.to_dict(orient="records")]
    ) + "]"

    # build HTML
    html = """<!doctype html>

<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(args.title)}</title>
<style>
:root {{
  --bg: #0b0b10;
  --card: #14141c;
  --muted: #9aa0a6;
  --text: #e8eaed;
  --accent: #6ee7ff;
  --accent2: #a78bfa;
  --border: #23232e;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 24px; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
  background: var(--bg); color: var(--text);
}}
h1 {{ margin: 0 0 8px; font-size: 22px; font-weight: 700; letter-spacing: .2px; }}
.small {{ color: var(--muted); font-size: 12px; margin-bottom: 16px; }}
.card {{
  background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.00));
  border: 1px solid var(--border);
  border-radius: 16px; padding: 16px; margin-bottom: 16px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.02), 0 12px 40px rgba(0,0,0,0.35);
}}
.controls {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }}
select, input {{
  background: var(--card); color: var(--text); border: 1px solid var(--border);
  border-radius: 10px; padding: 10px 12px; outline: none;
}}
select:focus, input:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px rgba(110,231,255,.15); }}
.badge {{ display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; color:#111; background: var(--accent); }}
.table-wrap {{ overflow:auto; border:1px solid var(--border); border-radius: 14px; }}
table {{ border-collapse: collapse; width: 100%; min-width: 920px; }}
th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
th {{ text-align: left; position: sticky; top: 0; background: var(--card); z-index: 1; font-size: 12px; color: var(--muted); letter-spacing: .2px; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
tr:hover td {{ background: rgba(255,255,255,0.02); }}
footer {{ color: var(--muted); font-size: 12px; margin-top: 16px; }}
.kv {{ display:flex; gap:8px; align-items:center; flex-wrap: wrap; }}
.kv div {{ background: var(--card); border:1px solid var(--border); border-radius: 8px; padding:6px 8px; }}
.linklike {{ color: var(--accent2); text-decoration:none; border-bottom:1px dotted var(--accent2); }}
</style>
</head>
<body>
  <div class="card">
    <h1>{escape(args.title)}</h1>
    <div class="small">Select <span class="badge">Bet</span> → Game → Player. Optional: Book & search. Sorted by Edge (bps) by default.</div>
    <div class="controls">
      <select id="market">
        <option value="">Bet (market)</option>
      </select>
      <select id="game">
        <option value="">Game</option>
      </select>
      <select id="player">
        <option value="">Player</option>
      </select>
      <select id="book">
        <option value="">Book</option>
      </select>
      <input id="q" type="search" placeholder="Search player / team / book…" />
    </div>
    <div class="kv" style="margin-top:10px;">
      <div id="count"></div>
      <div>Tip: “No Scorer” is hidden.</div>
      <div><a class="linklike" href="../">Back to site root</a></div>
    </div>
  </div>

  <div class="card table-wrap">
    <table id="tbl">
      <thead>
        <tr>
          <th>Game</th>
          <th>Player</th>
          <th>Book</th>
          <th>Bet</th>
          <th class="num">Mkt Odds</th>
          <th class="num">Fair</th>
          <th class="num">Mkt %</th>
          <th class="num">Model %</th>
          <th class="num">Edge (bps)</th>
          <th>Kick</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <footer>Generated from merged CSV on your machine. Dark theme, zero dependencies.</footer>

<script>
const DATA = """ + data_json + """;


function uniqueSorted(arr) {{
  return [...new Set(arr.filter(Boolean))].sort((a,b)=>a.localeCompare(b));
}}

const state = {{
  market: "", game: "", player: "", book: "", q: ""
}};

const selMarket = document.getElementById("market");
const selGame   = document.getElementById("game");
const selPlayer = document.getElementById("player");
const selBook   = document.getElementById("book");
const inputQ    = document.getElementById("q");
const tbody     = document.querySelector("#tbl tbody");
const countEl   = document.getElementById("count");

function hydrateSelectors() {{
  // Markets
  uniqueSorted(DATA.map(r => r.market_std)).forEach(v => {{
    const o = document.createElement("option"); o.value=v; o.textContent=v; selMarket.appendChild(o);
  }});
  // Books
  uniqueSorted(DATA.map(r => r.bookmaker)).forEach(v => {{
    const o = document.createElement("option"); o.value=v; o.textContent=v; selBook.appendChild(o);
  }});
  // Games & players will be dependent; fill initial (all)
  rebuildDependentSelectors();
}}

function rebuildDependentSelectors() {{
  // Compute filtered base for dependent lists
  const base = DATA.filter(r => (!state.market || r.market_std===state.market) &&
                                (!state.book   || r.bookmaker===state.book));
  // Games
  const games = uniqueSorted(base.map(r => r.game));
  selGame.innerHTML = '<option value="">Game</option>' + games.map(g=>`<option value="${g}">${g}</option>`).join("");
  if (games.includes(state.game)) selGame.value = state.game; else state.game = "";

  // Players (depending on market+book+game)
  const base2 = base.filter(r => (!state.game || r.game === state.game));
  const players = uniqueSorted(base2.map(r => r.player));
  selPlayer.innerHTML = '<option value="">Player</option>' + players.map(p=>`<option value="${p}">${p}</option>`).join("");
  if (players.includes(state.player)) selPlayer.value = state.player; else state.player = "";
}

function render() {{
  const q = state.q.trim().toLowerCase();
  const rows = DATA.filter(r =>
    (!state.market || r.market_std === state.market) &&
    (!state.game   || r.game       === state.game) &&
    (!state.player || r.player     === state.player) &&
    (!state.book   || r.bookmaker  === state.book) &&
    (!q || (r.player+" "+r.bookmaker+" "+r.game).toLowerCase().includes(q))
  ).sort((a,b) => (b.edge_bps??-1) - (a.edge_bps??-1));

  countEl.textContent = `${{rows.length}} rows`;

  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${{r.game || ""}}</td>
      <td>${{r.player || ""}}</td>
      <td>${{r.bookmaker || ""}}</td>
      <td>${{r.market_std || ""}}</td>
      <td class="num">${{r.mkt_odds ?? ""}}</td>
      <td class="num">${{r.fair_odds ?? ""}}</td>
      <td class="num">${{(r.mkt_pct ?? "").toString()}}</td>
      <td class="num">${{(r.model_pct ?? "").toString()}}</td>
      <td class="num">${{(r.edge_bps ?? "").toString()}}</td>
      <td>${{r.commence_time || ""}}</td>
    </tr>
  `).join("");
}

// events
selMarket.addEventListener("change", e => {{ state.market=e.target.value; rebuildDependentSelectors(); render(); }});
selGame  .addEventListener("change", e => {{ state.game  =e.target.value; rebuildDependentSelectors(); render(); }});
selPlayer.addEventListener("change", e => {{ state.player=e.target.value; render(); }});
selBook  .addEventListener("change", e => {{ state.book  =e.target.value; rebuildDependentSelectors(); render(); }});
inputQ   .addEventListener("input",  e => {{ state.q     =e.target.value; render(); }});

// init
hydrateSelectors(); render();
</script>
</body></html>
"""
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[props_site] wrote {args.out} with {len(df)} rows shown of {len(pd.read_csv(args.merged_csv))} source rows")

if __name__ == "__main__":
    main()
