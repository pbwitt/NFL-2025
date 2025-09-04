#!/usr/bin/env python3
import argparse, pandas as pd, numpy as np, html
from site_common import nav_html, pretty_market, american_to_prob, fmt_pct, fmt_odds, to_kick_et


from site_common import normalize_display


TEMPLATE = """<!doctype html><html><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<style>
body{margin:0;background:#0b0f14;color:#e7edf3;font-family:Inter,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.container{max-width:1100px;margin:0 auto;padding:12px 16px 48px}
h1{font-size:24px;margin:16px 0 10px}
table{width:100%;border-collapse:collapse}
th,td{border-bottom:1px solid #1f2937;padding:8px 10px;text-align:left}
th{position:sticky;top:0;background:#0b0f14;border-bottom:1px solid #243042}
.small{font-size:12px;color:#9aa4af}
</style>
</head><body>
__NAV__
<div class="container">
  <h1>Consensus vs Best Book — Week __WEEK__</h1>
  <div class="small">Consensus = median implied probability across books for the same leg. Best Book = book with highest model edge for that leg.</div>
  <table>
    <thead><tr>
      <th>Kick</th><th>Matchup</th><th>Player</th><th>Market</th><th>Pick</th>
      <th>Model&nbsp;%</th><th>Cons.&nbsp;%</th><th>Best Book</th><th>Best Price</th><th>Edge (bps)</th>
    </tr></thead>
    <tbody>__ROWS__</tbody>
  </table>
</div>
</body></html>
"""

def row_html(r):
    edge_bps = int(round(10000*(r["model_prob"]-r["consensus_prob"])))
    matchup = f'{html.escape(r["home_team"])} vs {html.escape(r["away_team"])}'
    return f"<tr>" \
           f"<td>{html.escape(r['kick_et'])}</td>" \
           f"<td>{matchup}</td>" \
           f"<td>{html.escape(r['player'])}</td>" \
           f"<td>{html.escape(r['market_disp'])}</td>" \
           f"<td>{html.escape(r['name'])}</td>" \
           f"<td>{r['model_prob_pct']}</td>" \
           f"<td>{r['consensus_prob_pct']}</td>" \
           f"<td>{html.escape(r['bookmaker'])}</td>" \
           f"<td>{r['price_disp']}</td>" \
           f"<td>{edge_bps}</td>" \
           f"</tr>"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged_csv", required=True)
    ap.add_argument("--out", default="docs/props/consensus.html")
    ap.add_argument("--week", type=int, default=1)
    args = ap.parse_args()

    df = pd.read_csv(args.merged_csv)
    from site_common import nav_html, normalize_display
    df = normalize_display(df)



    # now you can safely use row['market_disp'], row['kick_et'], etc.






    df = df.dropna(subset=["model_prob","price"])
    df["impl_prob"] = df["price"].astype(float).map(american_to_prob)
    df["market_disp"] = df["market"].map(pretty_market)
    if "kick_et" not in df.columns: df["kick_et"] = df.get("commence_time","").map(to_kick_et)

    key = ["game_id","player","market","name"]
    cons = df.groupby(key)["impl_prob"].median().rename("consensus_prob")
    df["edge"] = df["model_prob"] - df["impl_prob"]
    idx = df.groupby(key)["edge"].idxmax()
    best = df.loc[idx].copy().join(cons, on=key)
    best["consensus_prob"] = best["consensus_prob"].fillna(best["impl_prob"])
    best["model_prob_pct"] = best["model_prob"].map(fmt_pct)
    best["consensus_prob_pct"] = best["consensus_prob"].map(fmt_pct)
    best["price_disp"] = best["price"].map(fmt_odds)
    best = best.sort_values(by="model_prob", ascending=False)

    rows = [row_html(r) for _, r in best.iterrows()]
    html_out = TEMPLATE.replace("__NAV__", nav_html(depth=1, active="consensus")) \
                       .replace("__TITLE__", f"NFL-2025 — Consensus vs Best Book (Week {args.week})") \
                       .replace("__WEEK__", str(args.week)) \
                       .replace("__ROWS__", "\n".join(rows))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[consensus] wrote {args.out} with {len(rows)} rows")

if __name__ == "__main__":
    main()
