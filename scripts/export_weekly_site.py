#!/usr/bin/env python3
# scripts/export_weekly_site.py
import json, pathlib
from datetime import datetime, timezone
import pandas as pd

SITE_DIR = pathlib.Path("site")
SITE_DIR.mkdir(parents=True, exist_ok=True)

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>NFL-2025 — Weekly Edges</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="./styles.css">
</head>
<body>
<header>
  <h1>🏈 NFL-2025 — Weekly Edges</h1>
  <div id="meta"></div>
  <div class="controls">
    <label>Market
      <select id="market">
        <option value="">All</option>
        <option value="h2h">Moneyline</option>
        <option value="spreads">Spread</option>
        <option value="totals">Total</option>
      </select>
    </label>
    <label>Book
      <select id="book"></select>
    </label>
    <label>Min edge
      <input id="minEdge" type="number" step="0.1" value="1.0">
      <select id="edgeUnit">
        <option value="pct">%</option>
        <option value="pts">pts</option>
      </select>
    </label>
    <button id="copyLink">Copy Sharable Link</button>
  </div>
</header>

<main>
  <table id="edges">
    <thead>
      <tr>
        <th>Kickoff (ET)</th>
        <th>Matchup</th>
        <th>Market</th>
        <th>Side</th>
        <th>Line</th>
        <th>Price</th>
        <th>Book</th>
        <th>Model</th>
        <th>Edge</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>
</main>

<footer>
  <p>Manual refresh each week. Edges are model vs market; not betting advice.</p>
</footer>
<script src="./app.js"></script>
</body>
</html>
"""

APP_JS = """(function(){
  const qs = new URLSearchParams(window.location.search);
  const $ = (sel)=>document.querySelector(sel);

  function fmtET(iso){
    const d = new Date(iso);
    return d.toLocaleString("en-US", { timeZone: "America/New_York", month:"short", day:"2-digit", hour:"2-digit", minute:"2-digit" }).replace(",","");
  }
  function fmtPct(x){ return (100*x).toFixed(1) + "%"; }
  function fmtPrice(p){ return (p>0?"+":"") + p; }
  function fmtLine(market,point){
    if(market==="spreads"){
      const v = Number(point||0);
      return (v>0?"+":"") + v.toFixed(1);
    } else if(market==="totals"){
      return Number(point||0).toFixed(1);
    }
    return "";
  }

  fetch("./data.json?_="+Date.now())
    .then(r=>r.json())
    .then(data=>{
      $("#meta").textContent = "Updated " + fmtET(data.generated_at);

      const bookSel = $("#book");
      const books = Array.from(new Set(data.rows.map(r=>r.bookmaker))).sort();
      const any = document.createElement("option"); any.value=""; any.textContent="All"; bookSel.appendChild(any);
      books.forEach(b=>{ const o=document.createElement("option"); o.value=b; o.textContent=b; bookSel.appendChild(o); });

      if(qs.has("market")) $("#market").value = qs.get("market");
      if(qs.has("book")) $("#book").value = qs.get("book");
      if(qs.has("minEdge")) $("#minEdge").value = qs.get("minEdge");
      if(qs.has("edgeUnit")) $("#edgeUnit").value = qs.get("edgeUnit");

      function render(){
        const mkt = $("#market").value;
        const book = $("#book").value;
        const unit = $("#edgeUnit").value;
        const minEdge = Number($("#minEdge").value || 0);
        const tbody = $("#edges tbody");
        tbody.innerHTML = "";

        let rows = data.rows.slice();
        if(mkt) rows = rows.filter(r=>r.market===mkt);
        if(book) rows = rows.filter(r=>r.bookmaker===book);

        rows.forEach(r=>{
          r.edge_display = (r.market==="h2h" ? (100*r.edge_moneyline).toFixed(1)+"%" :
                           r.market==="spreads" ? (r.spread_edge_pts||0).toFixed(1)+" pts" :
                           r.market==="totals" ? (r.total_edge_pts||0).toFixed(1)+" pts" : "");
          r.edge_for_sort = (r.market==="h2h" ? (100*r.edge_moneyline) :
                            r.market==="spreads" ? r.spread_edge_pts :
                            r.market==="totals" ? r.total_edge_pts : 0);
        });

        rows = rows.filter(r=>{
          const val = (unit==="pct" ? (r.market==="h2h" ? 100*r.edge_moneyline : -Infinity) :
                                   (r.market!=="h2h" ? (r.market==="spreads"?r.spread_edge_pts:r.total_edge_pts) : -Infinity));
          return (val || 0) >= minEdge;
        });

        rows.sort((a,b)=> (b.edge_for_sort||0)-(a.edge_for_sort||0) || new Date(a.commence_time)-new Date(b.commence_time));

        for(const r of rows){
          const tr = document.createElement("tr");
          const matchup = `${r.away_team} @ ${r.home_team}`;
          const line = fmtLine(r.market, r.point);
          const model = (r.market==="h2h" ? fmtPct(r.team_win_prob) :
                        r.market==="spreads" ? (r.pred_margin>0?"+":"")+Number(r.pred_margin||0).toFixed(1)+" pts" :
                        r.market==="totals" ? (r.pred_total!=null? Number(r.pred_total).toFixed(1)+" pts":"—") : "—");

          tr.innerHTML = `
            <td>${fmtET(r.commence_time)}</td>
            <td>${matchup}</td>
            <td>${r.market.toUpperCase()}</td>
            <td>${r.name}</td>
            <td>${line}</td>
            <td>${r.price!=null?fmtPrice(r.price):""}</td>
            <td>${r.bookmaker}${r.is_best_price?" ⭐":""}</td>
            <td>${model}</td>
            <td class="edge">${r.edge_display}</td>`;
          tbody.appendChild(tr);
        }
      }

      ["market","book","minEdge","edgeUnit"].forEach(id=>$("#"+id).addEventListener("change", render));

      $("#copyLink").addEventListener("click", ()=>{
        const u = new URL(window.location.href);
        const p = u.searchParams;
        p.set("market", $("#market").value || "");
        p.set("book", $("#book").value || "");
        p.set("minEdge", $("#minEdge").value || "0");
        p.set("edgeUnit", $("#edgeUnit").value || "pct");
        navigator.clipboard.writeText(u.toString()).then(()=>{ $("#copyLink").textContent="Copied!"; setTimeout(()=>$("#copyLink").textContent="Copy Sharable Link",1200); });
      });

      render();
    });
})();
"""

STYLES_CSS = """*{box-sizing:border-box}body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;margin:0;background:#0b0f17;color:#e8eef9}
header{padding:16px 20px;border-bottom:1px solid #1c2533;background:#0e1420;position:sticky;top:0}
h1{margin:0 0 6px 0;font-size:20px}
#meta{opacity:.8;font-size:12px}
.controls{display:flex;gap:12px;align-items:center;margin-top:10px;flex-wrap:wrap}
label{font-size:12px;display:flex;gap:6px;align-items:center;background:#111827;border:1px solid #223048;padding:6px 8px;border-radius:10px}
input,select,button{font-size:13px;background:#0f172a;color:#e8eef9;border:1px solid #223048;border-radius:8px;padding:6px 8px}
button{cursor:pointer}
main{padding:14px 20px}
table{width:100%;border-collapse:separate;border-spacing:0 8px}
thead th{font-weight:600;text-align:left;font-size:12px;opacity:.9;padding:6px 10px}
tbody td{background:#0f1624;padding:10px;border-top:1px solid #1e293b;border-bottom:1px solid #1e293b}
tbody tr td:first-child{border-left:1px solid #1e293b;border-top-left-radius:10px;border-bottom-left-radius:10px}
tbody tr td:last-child{border-right:1px solid #1e293b;border-top-right-radius:10px;border-bottom-right-radius:10px}
td.edge{font-weight:600}
footer{padding:20px;color:#9fb3d9;opacity:.9}
"""

def build_top_picks(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["game_id","commence_time","home_team","away_team","market","name","bookmaker","price","point",
            "team_win_prob","pred_margin","pred_total","edge_moneyline","spread_edge_pts","total_edge_pts","is_best_price"]
    keep = [c for c in cols if c in df.columns]
    x = df[keep].copy()

    x["edge_sort"] = 0.0
    if "edge_moneyline" in x.columns:
        x.loc[x["market"]=="h2h", "edge_sort"] = x["edge_moneyline"]*100.0
    if "spread_edge_pts" in x.columns:
        x.loc[x["market"]=="spreads", "edge_sort"] = x["spread_edge_pts"]
    if "total_edge_pts" in x.columns:
        x.loc[x["market"]=="totals", "edge_sort"] = x["total_edge_pts"]

    x["rank"] = x.groupby(["game_id","market","name"])["edge_sort"].rank(method="first", ascending=False)
    best = x[x["rank"]==1].copy().drop(columns=["rank"])
    best = best.sort_values(["edge_sort","commence_time"], ascending=[False, True])
    return best

def main():
    merged_path = pathlib.Path("data/merged/latest_with_edges.csv")
    if not merged_path.exists():
        raise SystemExit("Missing data/merged/latest_with_edges.csv. Run: make merge")

    df = pd.read_csv(merged_path, low_memory=False)

    # Ensure expected columns exist (prevents attribute errors)
    for col in ["market", "edge_moneyline", "spread_edge_pts", "total_edge_pts"]:
        if col not in df.columns:
            df[col] = pd.NA

    # Keep kickoff as ISO; browser will format ET
    if "commence_time" in df.columns:
        df["commence_time"] = pd.to_datetime(df["commence_time"], errors="coerce").astype(str)

    # Filters: build null-safe masks
    m = df["market"]

    h2h_mask = (m == "h2h")
    if "edge_moneyline" in df.columns:
        h2h_mask &= df["edge_moneyline"].notna()
    else:
        h2h_mask &= False

    spreads_mask = (m == "spreads")
    if "spread_edge_pts" in df.columns:
        spreads_mask &= df["spread_edge_pts"].notna()
    else:
        spreads_mask &= False

    totals_mask = (m == "totals")
    if "total_edge_pts" in df.columns:
        totals_mask &= df["total_edge_pts"].notna()
    else:
        totals_mask &= False

    cond = h2h_mask | spreads_mask | totals_mask
    rows = df[cond].copy()

    # Fields the page needs
    fields = [
        "game_id","commence_time","home_team","away_team","market","name","bookmaker","price","point",
        "team_win_prob","pred_margin","pred_total","edge_moneyline","spread_edge_pts","total_edge_pts","is_best_price"
    ]
    rows = rows[[c for c in fields if c in rows.columns]].copy()

    # Write assets
    (SITE_DIR/"index.html").write_text(INDEX_HTML)
    (SITE_DIR/"app.js").write_text(APP_JS)
    (SITE_DIR/"styles.css").write_text(STYLES_CSS)

    # JSON-safe rows (converts NaN/NA -> null)
    payload_rows = json.loads(rows.to_json(orient="records"))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rows": payload_rows
    }
    (SITE_DIR/"data.json").write_text(json.dumps(payload))

    # Top picks CSV
    top = build_top_picks(rows)
    top.to_csv(SITE_DIR/"top_picks.csv", index=False)

    print("Wrote site/index.html, site/app.js, site/styles.css, site/data.json, site/top_picks.csv")
    if "game_id" in rows.columns:
        print(f"Rows on page: {len(rows)} | Games: {rows['game_id'].nunique()}")

if __name__ == "__main__":
    main()
