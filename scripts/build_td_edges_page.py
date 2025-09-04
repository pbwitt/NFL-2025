# scripts/build_td_edges_page.py
#!/usr/bin/env python3
import argparse, pandas as pd, numpy as np

def fmt_odds(o):
    if pd.isna(o): return ""
    o = int(round(o))
    return f"{o:+d}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged_csv", required=True)  # props_with_model_weekX.csv
    ap.add_argument("--out", required=True)         # docs/props/index.html (or td.html)
    ap.add_argument("--min_prob", type=float, default=0.02)  # hide super tiny probs
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    df = pd.read_csv(args.merged_csv)

    # keep only rows with modeled probs
    df = df[~df["model_prob"].isna()].copy()

    # optional: hide ultra-low probs
    df = df[df["model_prob"] >= args.min_prob].copy()

    # rank by edge
    df["edge_bps"] = (df["edge_prob"] * 10000).round(0)  # basis points for readability
    df["model_pct"] = (df["model_prob"] * 100).round(1)
    df["mkt_pct"]   = (df["market_prob"] * 100).round(1)
    if "price" in df.columns:
        df["mkt_odds"] = df["price"].apply(fmt_odds)
    if "model_price" in df.columns:
        df["fair_odds"] = df["model_price"].apply(lambda x: "" if pd.isna(x) else f"{int(round(x)):+d}")

    keep = [c for c in [
        "home_team","away_team","player","bookmaker","mkt_odds","fair_odds","mkt_pct","model_pct","edge_bps",
        "market_std","commence_time"
    ] if c in df.columns]
    table = (df
        .sort_values("edge_prob", ascending=False)
        [keep]
        .head(args.limit))

    # tiny HTML (works with GitHub Pages)
    html = f"""<!doctype html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NFL TD Props — Top Edges</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:24px;}}
h1{{margin:0 0 12px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:8px;font-size:14px}}
th{{background:#f5f5f5;text-align:left}}
td.num{{text-align:right}}
.small{{color:#666;font-size:12px}}
</style>
</head><body>
<h1>Touchdown Props — Top Edges</h1>
<p class="small">Showing best {len(table)} rows. Edge = model_prob − market_prob (in bps).</p>
{table.to_html(index=False, escape=False).replace("<td>","<td>").replace("<td>", "<td>")}
</body></html>"""

    with open(args.out, "w") as f:
        f.write(html)
    print(f"[td_page] wrote {args.out} with {len(table)} rows")

if __name__ == "__main__":
    main()
