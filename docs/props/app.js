(function(){
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
})();