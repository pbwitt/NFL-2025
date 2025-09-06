#!/usr/bin/env python3
import sys, pathlib, datetime as dt
import pandas as pd

PAGE_CSS = """
<style>
:root { font-family: system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; }
main { max-width: 1100px; margin: 48px auto; padding: 0 16px; }
h1 { margin: 0 0 8px; } .subtitle { color:#555;margin:0 0 24px; }
table { border-collapse: collapse; width: 100%; }
th,td { padding:10px 12px; border-bottom:1px solid #e5e5e5; text-align:left; }
th { background:#fafafa; } nav a { margin-right:12px; }
.badge { display:inline-block;border:1px solid #ddd;border-radius:999px;padding:2px 8px;font-size:12px;color:#555; }
</style>
"""

def wrap_html(title: str, body_html: str) -> str:
    now = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html><meta charset="utf-8">
<title>{title}</title>
{PAGE_CSS}
<main>
  <nav>
    <a href="/NFL-2025/">Edges</a>
    <a href="/NFL-2025/props/">Props</a>
  </nav>
  <h1>{title}</h1>
  <p class="subtitle">Generated {now} • <span class="badge">NFL-2025</span></p>
  {body_html}
</main>"""

def sample_edges_dataframe():
    return pd.DataFrame([
        {"Week": 1, "Matchup": "KC @ BAL", "Edge_%": 7.0, "Model": "Elo v0"},
        {"Week": 1, "Matchup": "BUF @ MIA", "Edge_%": -3.0, "Model": "Elo v0"},
        {"Week": 1, "Matchup": "SF  @ LAR", "Edge_%": 5.0, "Model": "Elo v0"},
    ])

def df_to_html(df):
    fmts = {"Edge_%": "{:.1f}%".format}
    return df.to_html(index=False, escape=False, justify="left", formatters=fmts)

def main(out_path: str):
    df = sample_edges_dataframe()
    html = wrap_html("Weekly Team Edges", df_to_html(df))
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"[edges] wrote {out}")

if __name__ == "__main__":
    out = "docs/index.html"
    if len(sys.argv) >= 3 and sys.argv[1] == "--out":
        out = sys.argv[2]
    main(out)
