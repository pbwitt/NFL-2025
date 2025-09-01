#!/usr/bin/env python3
# scripts/export_props_site.py
import json, pathlib
from datetime import datetime, timezone
import pandas as pd

DATA = pathlib.Path("data/merged/player_props_latest.csv")
SITE = pathlib.Path("site/props"); SITE.mkdir(parents=True, exist_ok=True)

INDEX = """<!doctype html><meta charset="utf-8"><title>NFL Props — All Markets</title>
<link rel="stylesheet" href="styles.css">
<div class=bar>
  <h1>🏈 NFL Props — All Markets</h1>
  <div id=meta></div>
  <label>Market <select id=market></select></label>
  <label>Book <select id=book></select></label>
  <label>Min edge <input id=min type=number step=0.01 value=0.03> <span>%</span></label>
</div>
<table id=tbl><thead><tr>
  <th>Kickoff (ET)</th><th>Matchup</th><th>Market</th><th>Player</th><th>Side</th>
  <th>Line</th><th>Price</th><th>Book</th><th>Model</th><th>Edge</th>
</tr></thead><tbody></tbody></table>
<script src="app.js"></script>
"""

APP = r"""(function(){
const $=(s)=>document.querySelector(s);
function fmtET(iso){ const d=new Date(iso); return d.toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"2-digit",hour:"2-digit",minute:"2-digit"}).replace(",",""); }
function fmtPrice(p){ return (p>0?"+":"")+p; }
function pct(x){ return (100*x).toFixed(1)+"%"; }

fetch("./data.json?_="+Date.now()).then(r=>r.json()).then(data=>{
  $("#meta").textContent = "Updated " + fmtET(data.generated_at);

  const markets=[...new Set(data.rows.map(r=>r.market_label||r.market))].sort();
  const books=[...new Set(data.rows.map(r=>r.bookmaker))].sort();
  $("#market").innerHTML="<option value=''>All</option>"+markets.map(m=>`<option>${m}</option>`).join("");
  $("#book").innerHTML="<option value=''>All</option>"+books.map(b=>`<option>${b}</option>`).join("");

  function render(){
    const mkt=$("#market").value, book=$("#book").value, min=parseFloat($("#min").value||0);
    let rows=data.rows.filter(r=>{
      const label = r.market_label || r.market;
      return (!mkt || label===mkt) && (!book || r.bookmaker===book) && (r.edge_prob>=min);
    });
    const tbody=$("#tbl tbody"); tbody.innerHTML="";
    rows.forEach(r=>{
      const tr=document.createElement("tr");
      const matchup=`${r.away_team} @ ${r.home_team}`;
      const modelDisp = (r.model==="normal" && r.mu!=null? `${Number(r.mu).toFixed(1)} ± ${Number(r.sigma).toFixed(1)}` :
                        r.model==="poisson" && r.lam!=null? `λ=${Number(r.lam).toFixed(2)}` :
                        r.model==="bernoulli" && r.p!=null? `${(100*r.p).toFixed(1)}%` : "—");
      tr.innerHTML = `
        <td>${fmtET(r.commence_time)}</td>
        <td>${matchup}</td>
        <td>${r.market_label || r.market}</td>
        <td>${r.player}</td>
        <td>${r.name}</td>
        <td>${(r.point!=null && r.point!=="" ? Number(r.point).toFixed(1):"")}</td>
        <td>${fmtPrice(r.price)}</td>
        <td>${r.bookmaker}</td>
        <td>${modelDisp}</td>
        <td><b>${pct(r.edge_prob)}</b>${(r.edge_pts!=null && r.edge_pts!==""? ` (${Number(r.edge_pts).toFixed(1)} pts)`: "")}</td>`;
      tbody.appendChild(tr);
    });
  }
  $("#market").addEventListener("change",render);
  $("#book").addEventListener("change",render);
  $("#min").addEventListener("change",render);
  render();
});
})();"""

CSS = """body{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;background:#0b0f17;color:#e8eef9;margin:0}
.bar{position:sticky;top:0;background:#0e1420;border-bottom:1px solid #1c2533;padding:14px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{margin:0;font-size:20px}
label{font-size:12px;background:#111827;border:1px solid #223048;padding:6px 8px;border-radius:10px;display:flex;gap:6px;align-items:center}
input,select{background:#0f172a;color:#e8eef9;border:1px solid #223048;border-radius:8px;padding:6px 8px}
table{width:100%;border-collapse:separate;border-spacing:0 8px;padding:14px 16px}
thead th{font-size:12px;opacity:.9;text-align:left;padding:6px 10px}
tbody td{background:#0f1624;padding:10px;border-top:1px solid #1e293b;border-bottom:1px solid #1e293b}
tbody tr td:first-child{border-left:1px solid #1e293b;border-top-left-radius:10px;border-bottom-left-radius:10px}
tbody tr td:last-child{border-right:1px solid #1e293b;border-top-right-radius:10px;border-bottom-right-radius:10px}
"""

def main():
    if not DATA.exists():
        raise SystemExit("Missing merged props CSV. Run: make props_merge_all")

    df = pd.read_csv(DATA, low_memory=False)
    rows = json.loads(df.to_json(orient="records"))
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "rows": rows}

    (SITE/"index.html").write_text(INDEX)
    (SITE/"app.js").write_text(APP)
    (SITE/"styles.css").write_text(CSS)
    (SITE/"data.json").write_text(json.dumps(payload))
    print("Wrote props site at site/props/ (index.html, app.js, styles.css, data.json)")
    print(f"Rows on page: {len(rows)}")

if __name__ == "__main__":
    main()
