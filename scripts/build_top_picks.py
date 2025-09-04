#!/usr/bin/env python3
import argparse, pandas as pd, numpy as np, html
from site_common import nav_html, pretty_market, american_to_prob, prob_to_american, fmt_pct, fmt_odds, to_kick_et

from site_common import normalize_display




TEMPLATE = """<!doctype html><html><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#0b0f14;--card:#121923;--muted:#9aa4af;--text:#e7edf3;--accent:#3b82f6;--ok:#10b981;--bad:#ef4444;}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
a{color:inherit;text-decoration:none}
.container{max-width:1100px;margin:0 auto;padding:12px 16px 48px}
h1{font-size:24px;margin:18px 0 8px}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 18px}
input,select{background:#0e141b;border:1px solid #1f2a37;color:var(--text);padding:8px 10px;border-radius:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
.card{background:var(--card);border:1px solid #1f2937;border-radius:16px;padding:14px;box-shadow:0 1px 0 rgba(255,255,255,.03) inset}
.badge{background:#0f172a;border:1px solid #1e293b;color:#d1d5db;border-radius:999px;padding:2px 10px;font-size:12px}
.kv{display:flex;justify-content:space-between;margin:6px 0}
.k{color:var(--muted)} .v{font-weight:600}
.copy{cursor:pointer;border:1px solid #253043;padding:6px 10px;border-radius:10px}
hr{border:0;border-top:1px solid #1f2937;margin:14px 0}
.small{font-size:12px;color:var(--muted)}
.positive{color:var(--ok)} .negative{color:var(--bad)}
</style>
</head><body>
__NAV__
<div class="container">
  <h1>Top Picks — Week __WEEK__</h1>
  <div class="small">Sorted by consensus edge (model vs consensus price). Use filters to narrow to bettable edges and EV.</div>
  <div class="toolbar">
    <label>Min Edge (bps) <input id="minbps" type="number" value="__MIN_BPS__" min="0" step="5"/></label>
    <label>Min EV per $100 <input id="minev" type="number" value="0" step="1"/></label>
    <label>Top N <input id="topn" type="number" value="__TOPN__" min="10" step="10"/></label>
    <button id="apply" class="copy">Apply</button>
  </div>
  <div id="grid" class="grid">__CARDS__</div>
</div>
<script>
function applyFilters(){
  const minbps = parseFloat(document.getElementById('minbps').value||0);
  const minev = parseFloat(document.getElementById('minev').value||0);
  const topn = parseInt(document.getElementById('topn').value||200);
  const cards = Array.from(document.querySelectorAll('.card'));
  const ok = [];
  cards.forEach(c=>{
    const bps = parseFloat(c.dataset.bps), ev = parseFloat(c.dataset.ev);
    if(bps>=minbps && ev>=minev) ok.push(c);
    c.style.display = 'none';
  });
  ok.sort((a,b)=>parseFloat(b.dataset.bps)-parseFloat(a.dataset.bps));
  ok.slice(0, topn).forEach(c=>c.style.display='block');
}
document.getElementById('apply').addEventListener('click', applyFilters);
window.addEventListener('load', applyFilters);
function copyTxt(txt){navigator.clipboard.writeText(txt);}
</script>
</body></html>
"""

def card(row):
    edge_bps = int(round(10000*(row["model_prob"]-row["consensus_prob"])))
    ev100 = row["ev_per_100"]
    ev_cls = "positive" if ev100>=0 else "negative"
    leg = f'{row["player"]} — {row["market_disp"]} — {row["name_disp"]}'
    betslip = f'{row["bookmaker"]} {row["price_disp"]} | {leg}'
    return f"""
<div class="card" data-bps="{edge_bps}" data-ev="{ev100:.2f}">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
    <div class="badge">{html.escape(row["kick_et"])}</div>
    <div class="badge">{html.escape(row["home_team"])} vs {html.escape(row["away_team"])}</div>
  </div>
  <h3 style="margin:10px 0 4px">{html.escape(row["player"])} — {html.escape(row["market_disp"])}</h3>
  <div class="small" style="margin-bottom:6px">{html.escape(row["name_disp"])} @ <b>{row["price_disp"]}</b> on <b>{html.escape(row["bookmaker"])}</b></div>
  <div class="kv"><span class="k">Model prob</span><span class="v">{row["model_prob_pct"]}</span></div>
  <div class="kv"><span class="k">Consensus prob</span><span class="v">{row["consensus_prob_pct"]}</span></div>
  <div class="kv"><span class="k">Consensus edge</span><span class="v">{edge_bps} bps</span></div>
  <div class="kv"><span class="k">EV / $100</span><span class="v {ev_cls}">${ev100:.2f}</span></div>
  <hr/>
  <div style="display:flex;gap:8px">
    <button class="copy" onclick='copyTxt({json_str(betslip)})'>Copy bet</button>
    <span class="small">Best book: {html.escape(row["bookmaker"])}</span>
  </div>
</div>"""

def json_str(s):
    return '"' + s.replace('\\','\\\\').replace('"','\\"') + '"'

def american_payout_per_100(odds):
    o = float(odds)
    return (o if o>0 else 10000.0/abs(o))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged_csv", required=True, help="e.g., data/props/props_with_model_week1.csv")
    ap.add_argument("--out", default="docs/props/top.html")
    ap.add_argument("--week", type=int, default=1)
    ap.add_argument("--min_prob", type=float, default=0.01)
    ap.add_argument("--topn_default", type=int, default=200)
    ap.add_argument("--minbps_default", type=int, default=30)
    args = ap.parse_args()

    df = pd.read_csv(args.merged_csv)


    # … any filters or merges you normally do …

    # ---- normalize display columns ----
    df = normalize_display(df)
    # ---- end normalize ----

    # now you can safely use row['market_disp'], row['kick_et'], etc.






    for col in ("model_prob","price","bookmaker","player","market","name","home_team","away_team"):
        if col not in df.columns: df[col] = np.nan

    # drop unmolded/oddsless
    df = df.dropna(subset=["model_prob","price"])
    df["impl_prob"] = df["price"].astype(float).map(american_to_prob)
    df = df.dropna(subset=["impl_prob"])
    df["market_disp"] = df["market"].map(pretty_market)
    df["name_disp"] = df["name"].fillna("").replace({"Over":"Over","Under":"Under"})  # keep as-is if present
    # kickoff (prefer kick_et if present)
    if "kick_et" not in df.columns: df["kick_et"] = df.get("commence_time","").map(to_kick_et)

    # group key at (game, player, market, name)
    key = ["game_id","player","market","name"]
    # consensus prob per key (median across books)
    cons = df.groupby(key)["impl_prob"].median().rename("consensus_prob")
    # best book per key by highest model edge vs book
    df["edge"] = df["model_prob"] - df["impl_prob"]
    idx = df.groupby(key)["edge"].idxmax()
    best = df.loc[idx].copy()
    best = best.join(cons, on=key)
    best["consensus_prob"] = best["consensus_prob"].fillna(best["impl_prob"])
    best["model_prob_pct"] = best["model_prob"].map(fmt_pct)
    best["consensus_prob_pct"] = best["consensus_prob"].map(fmt_pct)
    best["price_disp"] = best["price"].map(fmt_odds)
    # EV per $100 stake
    best["ev_per_100"] = best["model_prob"]*best["price"].astype(float).map(american_payout_per_100) - (1.0 - best["model_prob"])*100.0
    # sort by consensus edge
    best["cons_edge"] = best["model_prob"] - best["consensus_prob"]
    best = best.sort_values("cons_edge", ascending=False)

    cards = []
    for _, r in best.iterrows():
        row = dict(r)
        if pd.isna(row.get("kick_et","")) or not row["kick_et"]:
            row["kick_et"] = to_kick_et(str(row.get("commence_time","")))
        cards.append(card(row))

    html = TEMPLATE.replace("__NAV__", nav_html(depth=1, active="top")) \
                   .replace("__TITLE__", f"NFL-2025 — Top Picks (Week {args.week})") \
                   .replace("__WEEK__", str(args.week)) \
                   .replace("__CARDS__", "\n".join(cards)) \
                   .replace("__TOPN__", str(args.topn_default)) \
                   .replace("__MIN_BPS__", str(args.minbps_default))

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[top] wrote {args.out} with {len(cards)} cards")

if __name__ == "__main__":
    main()
