(function(){
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
