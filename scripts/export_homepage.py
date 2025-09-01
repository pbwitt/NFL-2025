#!/usr/bin/env python3
# scripts/export_homepage.py
import pathlib, json
from datetime import datetime, timezone

SITE = pathlib.Path("site")
SITE.mkdir(parents=True, exist_ok=True)

# try to read last generated time from main site and props
def last_updated():
    times = []
    for p in [SITE/"data.json", SITE/"props"/"data.json"]:
        if p.exists():
            try:
                j = json.loads(p.read_text())
                times.append(j.get("generated_at"))
            except Exception:
                pass
    if not times:
        return None
    try:
        # pick most recent iso
        ts = max(datetime.fromisoformat(t.replace("Z","+00:00")) for t in times if t)
        return ts.astimezone(timezone.utc).isoformat()
    except Exception:
        return None

UPDATED = last_updated()

HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>NFL-2025 — AI Edges & Player Props</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="./styles.css">
<style>
:root {{ --bg:#0b0f17; --panel:#0f1624; --line:#1e293b; --ink:#e8eef9; --ink2:#9fb3d9; --brand:#60a5fa; }}
body {{ background:var(--bg); color:var(--ink); }}
.container {{ max-width:1100px; margin:0 auto; padding:24px 20px; }}
.hero {{ padding:48px 20px 18px; border-bottom:1px solid #1c2533; background:#0e1420; }}
h1 {{ margin:0 0 10px; font-size:28px }}
.lede {{ color:var(--ink2); font-size:15px; max-width:820px; }}
.cta {{ display:flex; gap:12px; margin-top:16px; flex-wrap:wrap; }}
.btn {{ display:inline-flex; align-items:center; gap:8px; padding:10px 14px; border-radius:10px; border:1px solid #223048; background:#111827; color:var(--ink); text-decoration:none; font-weight:600 }}
.btn.primary {{ background:linear-gradient(180deg,#2563eb,#1d4ed8); border-color:#1d4ed8 }}
.btn span.kbd {{ font:12px/1.2 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; opacity:.9; background:#0b1220; border:1px solid #223048; padding:2px 6px; border-radius:6px }}
.grid {{ display:grid; gap:14px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); margin-top:20px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px; }}
.card h3 {{ margin:0 0 8px; font-size:16px }}
ul.clean {{ padding-left:18px; margin:8px 0 0 }}
small.muted {{ color:var(--ink2); display:block; margin-top:8px }}
.footer {{ padding:18px 20px; color:var(--ink2); border-top:1px solid #1c2533; text-align:center; margin-top:28px }}
.badge {{ display:inline-block; font-size:12px; padding:4px 8px; border-radius:8px; background:#0f172a; border:1px solid #223048; color:#c7d2fe }}
.meta {{ margin-top:10px; font-size:12px; color:var(--ink2) }}
</style>
</head>
<body>

<header class="hero">
  <div class="container">
    <h1>🏈 NFL-2025 — AI-powered Edges & Player Props</h1>
    <p class="lede">
      Weekly market scans meet lightweight predictive models. We ingest live odds, compute fair prices, and surface
      high-signal discrepancies as easy-to-browse edges — both at the game level and across player props.
    </p>
    <div class="cta">
      <a class="btn primary" href="./">📊 View Weekly Edges</a>
      <a class="btn" href="./props/">🎯 Explore Player Props</a>
      <span class="badge">Not betting advice</span>
    </div>
    {"<div class='meta'>Last updated: " + UPDATED + " (UTC)</div>" if UPDATED else ""}
  </div>
</header>

<main class="container">
  <div class="grid">
    <section class="card">
      <h3>How it works</h3>
      <ul class="clean">
        <li><b>Ingest</b> — Pull current moneylines, spreads, totals, and player props across books.</li>
        <li><b>Model</b> — Estimate win probabilities and stat distributions using transparent, data-first baselines.</li>
        <li><b>Compare</b> — Translate models into fair prices/lines and flag value deltas (“edges”).</li>
      </ul>
      <small class="muted">Everything runs from reproducible scripts each week; outputs are static and shareable.</small>
    </section>

    <section class="card">
      <h3>Team model (games)</h3>
      <p>
        A tuned <b>Elo</b> baseline seeded from prior performance powers Week 1. As the season unfolds, results
        flow into the ratings to keep the signal current. We apply a modest <b>home-field</b> term and map Elo deltas
        into win probabilities and a rough point-margin proxy to sanity-check spreads/totals.
      </p>
      <small class="muted">Designed for stability and transparency; simple by choice.</small>
    </section>

    <section class="card">
      <h3>Player model (props)</h3>
      <p>
        For yardage/volume markets we fit <b>Normal</b> distributions (μ, σ). For discrete counts (TDs, INTs,
        tackles) we use <b>Poisson</b>. Binary markets (Anytime TD) use <b>Bernoulli</b>. Week 1 derives priors from last
        season; Week 2+ rolls forward on current-season data.
      </p>
      <small class="muted">Distribution choice matches the market — simple, fast, explainable.</small>
    </section>

    <section class="card">
      <h3>Why this works</h3>
      <ul class="clean">
        <li><b>Market coverage</b> — Scan many books; highlight best available prices.</li>
        <li><b>Consistency</b> — Same method every week; easy audit trail.</li>
        <li><b>Signal over sizzle</b> — Lightweight models beat overfitting early in the year.</li>
      </ul>
    </section>

    <section class="card">
      <h3>What we don’t do</h3>
      <ul class="clean">
        <li>No injury/beat-report scraping; assumptions stay conservative.</li>
        <li>No secret black-box parameters; any uplift is earned on data.</li>
        <li>No guarantees — edges are estimates, not certainties.</li>
      </ul>
    </section>

    <section class="card">
      <h3>Disclaimers</h3>
      <p class="muted">
        Informational and educational use only. Not betting advice. Check local regulations and play responsibly.
      </p>
    </section>
  </div>
</main>

<div class="footer">
  <span class="badge">Odds: multiple US books</span>
  <span class="badge">Data: nfl_data_py (historical)</span>
  <span class="badge">Refresh: weekly</span>
</div>

</body>
</html>
"""

def main():
    out = SITE / "home.html"
    out.write_text(HTML)
    print(f"Wrote {out} — link: http://localhost:8080/home.html (or /home.html on your host)")

if __name__ == "__main__":
    main()
