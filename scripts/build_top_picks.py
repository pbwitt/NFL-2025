#!/usr/bin/env python3
import argparse, pandas as pd, numpy as np, re, math
from html import escape
from pathlib import Path

# ---- shared helpers / branding ----

def _is_numeric_total_market(mkt) -> bool:
    """Markets where 'Over/Under <number>' is expected (not Yes/No)."""
    m = pretty_market(mkt or "").lower()
    if not m: return False
    # broad keywords + common exact names
    if "yards" in m:  # passing/receiving/rushing yards, etc.
        return True
    numeric_exact = {
        "receptions", "rush attempts", "pass attempts",
        "completions", "passing touchdowns", "rushing attempts",
    }
    return m in numeric_exact


import re, math  # ensure both imported

NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

def parse_numberish(x):
    """Extract a usable float from messy strings like '7,410 bps', '74.1%', ' +150 '."""
    if x is None or (isinstance(x, float) and math.isnan(x)): return np.nan
    s = str(x).replace(",", " ").strip()
    m = NUM_RE.search(s)
    if not m: return np.nan
    v = float(m.group(0))
    # treat percentages like 74.1% → 0.741
    if "%" in s and v > 1: v = v / 100.0
    return v

def _prob01(x):
    """Normalize probs to [0,1] from decimals or percents."""
    v = parse_numberish(x)
    if not isinstance(v, float) or math.isnan(v): return np.nan
    if 0 <= v <= 1: return v
    if 1 < v <= 100: return v / 100.0
    return np.nan

def american_to_prob(o):
    """Implied probability from American odds (no vig)."""
    v = parse_numberish(o)
    if not isinstance(v, float) or math.isnan(v): return np.nan
    return 100.0/(v+100.0) if v > 0 else (-v)/((-v)+100.0)

def _format_pct(x):
    p = _prob01(x)
    if not isinstance(p, float) or math.isnan(p) or p <= 0 or p >= 1: return ""
    return f"{p*100:.1f}%"

def _ev_per_100(prob, american_odds):
    p = _prob01(prob)
    if not isinstance(p, float) or math.isnan(p) or p <= 0 or p >= 1: return ""
    v = parse_numberish(american_odds)
    if not isinstance(v, float) or math.isnan(v): return ""
    win_profit = (v/100.0)*100.0 if v > 0 else (100.0/abs(v))*100.0
    ev = p*win_profit - (1-p)*100.0
    return f"${ev:.2f}" if ev >= 0 else f"-${abs(ev):.2f}"






try:
    from scripts.site_common import nav_html, pretty_market, fmt_odds_american, kickoff_et, BRAND
except Exception:
    from site_common import nav_html, pretty_market, fmt_odds_american, kickoff_et, BRAND  # fallback

# big render cap; UI defaults to Top N=10 so this won't overwhelm the page
CARD_LIMIT = 25000

# columns we’ll scan for the numeric line if line_disp is missing
LINE_CANDIDATES = [
    "line_disp","point","line","market_line","prop_line","number","threshold","total","line_number",
    "handicap","spread","yards","receptions","receiving_yards","rushing_yards","passing_yards","prop_total"
]
GAME_CANDIDATES = ["game","Game","matchup","matchup_name","matchup_display"]

def _num(x):
    with np.errstate(all="ignore"):
        return pd.to_numeric(x, errors="coerce")

def _norm(s: str) -> str:
    """normalize for filtering: lowercase, collapse spaces, trim"""
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()

def _first_nonnull(row, cols):
    for c in cols:
        if c in row and pd.notna(row[c]) and str(row[c]).strip() != "":
            return row[c]
    return np.nan

def _format_pct(x):
    if x is None or (isinstance(x,float) and (math.isnan(x) or x<0 or x>1)): return ""
    return f"{x*100:.1f}%"

def _ev_per_100(prob, american_odds):
    """Expected profit per $100 stake using prob in [0,1] and American odds."""
    if prob is None or (isinstance(prob,float) and (math.isnan(prob) or prob<=0 or prob>=1)): return ""
    try:
        o = float(american_odds)
    except Exception:
        return ""
    win_profit = (o/100.0)*100.0 if o>0 else (100.0/abs(o))*100.0  # +150→150; -110→90.909...
    ev = prob*win_profit - (1.0-prob)*100.0
    sign = "-" if ev < 0 else ""
    return f"${abs(ev):.2f}"

def read_df(path):
    df = pd.read_csv(path)

    # --- normalize common columns ---
    if "book" not in df.columns and "bookmaker" in df.columns:
        df["book"] = df["bookmaker"]

    # --- edge column (keep existing, parse if stringy) ---
    edge_col = None
    for c in df.columns:
        cl = c.lower().strip()
        if cl in ("edge_bps", "consensus_edge_bps", "edgebps", "edge_bp", "edge_in_bps"):
            edge_col = c
            break
    if edge_col:
        df["edge_bps"] = df[edge_col].apply(parse_numberish)
    elif "edge" in df.columns:
        df["edge_bps"] = df["edge"].apply(parse_numberish)
    else:
        df["edge_bps"] = np.nan

    # --- probabilities (model & consensus) ---
    prob_cols = {c.lower(): c for c in df.columns}
    model_prob_col = None
    for k in ["model_prob", "model_probability", "model_pct", "prob_model", "p_model"]:
        if k in prob_cols:
            model_prob_col = prob_cols[k]
            break
    consensus_prob_col = None
    for k in ["consensus_prob", "market_prob", "mkt_prob", "prob_market", "prob_consensus", "fair_prob"]:
        if k in prob_cols:
            consensus_prob_col = prob_cols[k]
            break

    # === Backfill edge only if missing/all-NaN ===
    edge_label = "Consensus edge"
    if df["edge_bps"].isna().all():
        mp = df[model_prob_col].apply(_prob01) if model_prob_col else None
        if mp is not None and consensus_prob_col:
            cp = df[consensus_prob_col].apply(_prob01)
            df["edge_bps"] = 10000.0 * (mp - cp)
            edge_label = "Consensus edge"
        elif mp is not None and "price" in df.columns:
            bp = df["price"].apply(american_to_prob)
            df["edge_bps"] = 10000.0 * (mp - bp)
            edge_label = "Book edge"

    # stash labels/cols for renderer
    df.attrs["_edge_label"] = edge_label
    df.attrs["model_prob_col"] = model_prob_col
    df.attrs["consensus_prob_col"] = consensus_prob_col

    # --- numerics (safe) ---
    for c in ["price", "model_line", "point", "line"]:
        if c in df.columns:
            df[c] = _num(df[c])

    # --- kickoff fallback ---
    if "kick_et" not in df.columns:
        df["kick_et"] = df["commence_time"] if "commence_time" in df.columns else np.nan
    elif "commence_time" in df.columns:
        df["kick_et"] = df["kick_et"].fillna(df["commence_time"])

    # --- ensure presence ---
    for col in ["player", "market", "book", "home_team", "away_team", "name"]:
        if col not in df.columns:
            df[col] = np.nan
    df["name"] = df["name"].fillna("")

    # ---- line display (bet side + number) ----
    def mk_line_disp(r):
        # If a nice display already exists, keep it
        if "line_disp" in r and str(r["line_disp"]).strip():
            return str(r["line_disp"]).strip()

        # Pull a numeric line from any plausible column
        raw_line = _first_nonnull(r, LINE_CANDIDATES)
        line_txt = ""
        if pd.notna(raw_line):
            try:
                line_txt = f"{float(raw_line):g}"  # avoid trailing .0
            except Exception:
                line_txt = str(raw_line).strip()

        side_raw = str(r.get("name") or r.get("side") or "").strip()  # Over/Under/Yes/No
        side = side_raw

        # If numeric-total market and we have a number, normalize Yes/No → Over/Under
        if line_txt and _is_numeric_total_market(r.get("market")):
            if side_raw.lower() == "yes":
                side = "Over"
            elif side_raw.lower() == "no":
                side = "Under"

        # Assemble
        if side and line_txt:
            return f"{side} {line_txt}"
        return side or line_txt or ""

    df["line_disp"] = df.apply(mk_line_disp, axis=1)

    # ---- game label ----
    def mk_game(row):
        for c in GAME_CANDIDATES:
            if c in df.columns:
                val = row.get(c)
                if pd.notna(val) and str(val).strip():
                    return str(val).strip()
        away = str(row.get("away_team") or "").strip()
        home = str(row.get("home_team") or "").strip()
        if away and home:
            return f"{away} vs {home}"
        return away or home or ""

    df["game_disp"] = df.apply(mk_game, axis=1)

    # ---- normalized helper columns for stable filtering ----
    df["_mkt_norm"] = df["market"].apply(lambda m: _norm(pretty_market(m)))
    df["_game_norm"] = df["game_disp"].apply(_norm)
    df["_book_norm"] = df["book"].apply(_norm)

    # ---- dedupe: keep max edge per (player, market, game, book, line, price) ----
    for c in ["player", "market", "game_disp", "book", "line_disp", "price", "edge_bps"]:
        if c not in df.columns:
            df[c] = np.nan

    df["__key__"] = (
        df["player"].astype(str).str.strip() + "||" +
        df["market"].astype(str).str.strip() + "||" +
        df["game_disp"].astype(str).str.strip() + "||" +
        df["book"].astype(str).str.strip() + "||" +
        df["line_disp"].astype(str).str.strip() + "||" +
        df["price"].astype(str).str.strip()
    )

    _edge_sort = df["edge_bps"].astype(float)
    df["_edge_sort"] = _edge_sort.where(_edge_sort.notna(), -1e15)

    df = (
        df.sort_values(["__key__", "_edge_sort"], ascending=[True, False])
          .drop_duplicates("__key__", keep="first")
          .drop(columns=["_edge_sort"])
          .copy()
    )

    return df

    # ---- line display (bet side + number) ----
    def mk_line_disp(r):
    # If a nice display already exists, keep it
        if "line_disp" in r and str(r["line_disp"]).strip():
            return str(r["line_disp"]).strip()

        # Pull a numeric line from any plausible column
        raw_line = _first_nonnull(r, LINE_CANDIDATES)
        line_txt = ""
        if pd.notna(raw_line):
            try:
                line_txt = f"{float(raw_line):g}"  # avoid trailing .0
            except Exception:
                line_txt = str(raw_line).strip()

        side_raw = str(r.get("name") or r.get("side") or "").strip()  # Over/Under/Yes/No
        side = side_raw

    # If this is a numeric-total market and we have a number,
    # normalize Yes/No → Over/Under.
        if line_txt:
            if _is_numeric_total_market(r.get("market")):
                if side_raw.lower() == "yes": side = "Over"
                elif side_raw.lower() == "no": side = "Under"

        # Assemble
        if side and line_txt:
            return f"{side} {line_txt}"
        return side or line_txt or ""

    # ---- game label ----
    def mk_game(row):
        for c in GAME_CANDIDATES:
            if c in df.columns:
                val = row.get(c)
                if pd.notna(val) and str(val).strip():
                    return str(val).strip()
        away = str(row.get("away_team") or "").strip()
        home = str(row.get("home_team") or "").strip()
        if away and home: return f"{away} vs {home}"
        return away or home or ""
    df["game_disp"] = df.apply(mk_game, axis=1)

    # ---- normalized helper columns for stable filtering ----
    df["_mkt_norm"]  = df["market"].apply(lambda m: _norm(pretty_market(m)))
    df["_game_norm"] = df["game_disp"].apply(_norm)
    df["_book_norm"] = df["book"].apply(_norm)

    # ---- dedupe: keep the row with max edge per (player,market,game,book,line,price) ----
    # ---- dedupe: keep the row with max edge per (player,market,game,book,line,price) ----


    # ---- stash pointers to prob columns for later rendering ----
    df.attrs["model_prob_col"] = model_prob_col
    df.attrs["consensus_prob_col"] = consensus_prob_col
    return df

# ---- rendering ----
def card(row, model_prob_col, consensus_prob_col):
    player = escape(str(row.get("player","")))
    mkt_lbl = pretty_market(row.get("market",""))
    book    = str(row.get("book",""))
    odds    = fmt_odds_american(row.get("price"))
    line_d  = str(row.get("line_disp",""))
    edge    = row.get("edge_bps", np.nan)
    game    = str(row.get("game_disp",""))
    kick    = kickoff_et(row.get("kick_et",""))

    # probs (robust to 0–1 or 0–100 inputs)
    model_prob = row.get(model_prob_col) if model_prob_col else np.nan
    cons_prob  = row.get(consensus_prob_col) if consensus_prob_col else np.nan
    model_prob_txt = _format_pct(model_prob)
    cons_prob_txt  = _format_pct(cons_prob)

    # EV per $100 using model prob & american odds
    ev_txt = _ev_per_100(model_prob if isinstance(model_prob,(int,float,str)) else np.nan, row.get("price"))

    # Optional model line (only if sane)
    model_line = row.get("model_line", np.nan)
    show_model_line = isinstance(model_line, (int, float)) and not math.isnan(model_line) and 0 < float(model_line) < 300
    model_line_txt = f"{float(model_line):g}" if show_model_line else ""

    # normalized attrs for robust filtering
    data_attrs = f'data-market="{escape(_norm(mkt_lbl))}" data-game="{escape(_norm(game))}" data-book="{escape(_norm(book))}"'

    # bet text
    bet_parts = []
    if line_d: bet_parts.append(line_d)                      # "Under 73.5" or "Yes"
    if odds:   bet_parts.append(f"@ {odds}")                 # "@ -110"
    if book:   bet_parts.append(f"on {book}")                # "on BetMGM"
    bet_txt = " ".join(bet_parts).strip()

    edge_txt = "" if (edge is None or (isinstance(edge,float) and math.isnan(edge))) else f"{edge:,.0f} bps"

    return f"""
    <div class="card" {data_attrs} data-edge="{'' if (edge is None or (isinstance(edge,float) and math.isnan(edge))) else f'{float(edge):g}'}">
      <div class="meta">
        <span class="time">{escape(str(kick))}</span>
        <span class="dot">•</span>
        <span class="game">{escape(game)}</span>
      </div>

      <div class="headline">
        <span class="player">{escape(player)}</span>
        <span class="dash">—</span>
        <span class="market">{escape(mkt_lbl)}</span>
      </div>

      <div class="betline">Bet: {escape(bet_txt)}</div>

      <div class="kvgrid">
        <div>Model prob</div><div>{escape(model_prob_txt)}</div>
        <div>Consensus prob</div><div>{escape(cons_prob_txt)}</div>
        <div>Consensus edge</div><div>{escape(edge_txt)}</div>
        <div>EV / $100</div><div>{escape(ev_txt)}</div>
      </div>

      <div class="footer">
        <button class="copy" onclick="copyCard(this)">Copy bet</button>
        <div class="right">
          {"<span class='modelline'>Model: " + escape(model_line_txt) + "</span>" if model_line_txt else ""}
          <span class="bestbook">{"Best book: " + escape(book) if book else ""}</span>
        </div>
      </div>
    </div>
    """


def _opts_from_pairs(pairs):
    out = ['<option value="">All</option>']
    for val, lbl in pairs:
        out.append(f'<option value="{escape(val)}">{escape(lbl)}</option>')
    return "\n".join(out)

def html_page(cards_html, title, market_pairs, game_pairs, book_pairs):
    market_opts = _opts_from_pairs(market_pairs)
    game_opts   = _opts_from_pairs(game_pairs)
    book_opts   = _opts_from_pairs(book_pairs)

    consensus_note = (
        "Note: <b>market consensus</b> is the aggregated market view "
        "(e.g., average/median de-vig price/line across books). "
        "We surface edges vs that consensus and vs each book."
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{escape(title)}</title>
<link rel="icon" href="data:,">
<style>
:root {{ color-scheme: dark }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:#0b0b0c; color:#e7e7ea; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Inter,Roboto,Ubuntu,Helvetica,Arial,sans-serif; }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 18px 16px 32px; }}
.h1 {{ font-size: clamp(22px,3.5vw,28px); font-weight:900; color:#fff; margin: 4px 0 10px; }}

/* Controls */
.controls {{ display:flex; gap:8px; flex-wrap:wrap; margin:10px 0 10px; align-items:end; }}
label {{ display:flex; flex-direction:column; gap:4px; font-size:12px; color:#b7b7bb; }}
input,select {{ background:#111113; border:1px solid #232327; color:#e7e7ea; border-radius:10px; padding:8px 10px; min-width:110px; }}
button.badge {{ font-size:12px; background:#2a63ff; border:none; color:#fff; padding:8px 12px; border-radius:10px; cursor:pointer; }}
button.reset {{ background:#1a1a1d; border:1px solid #2a2a2e; color:#e7e7ea; }}
.note {{ margin:6px 0 16px; color:#b7b7bb; font-size:13px; }}

/* Card grid (responsive: 1-up → 2-up → 3-up) */
#list {{
  display: grid;
  grid-template-columns: 1fr;      /* mobile: 1-up */
  gap: 12px;
}}
@media (min-width: 760px) {{
  #list {{ grid-template-columns: repeat(2, 1fr); }}   /* tablet: 2-up */
}}
@media (min-width: 1100px) {{
  #list {{ grid-template-columns: repeat(3, 1fr); }}   /* desktop: 3-up */
}}

/* Card — compact, mobile-first */
.card {{
  background:#111113; border:1px solid #1f1f22; border-radius:16px;
  padding:12px 12px; display:flex; flex-direction:column; gap:6px;
}}
.meta {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; color:#8a8a90; font-size:12px; }}
.meta .dot {{ opacity:.6; }}
.headline {{ display:flex; flex-wrap:wrap; gap:6px; align-items:baseline; }}
.player {{ color:#fff; font-weight:800; font-size:15px; }}
.market {{ color:#c8c8cd; font-size:14px; }}
.betline {{ color:#e3e3e6; font-size:14px; }}

/* Tight stats grid (no big spacing) */
.kvgrid {{
  display: grid;
  grid-template-columns: max-content max-content;
  column-gap: 10px;
  row-gap: 2px;
  align-items: baseline;
  font-size: 13px; color: #d6d6d9;
}}
.kvgrid > div:nth-child(odd) {{ color:#b7b7bb; }}  /* labels */

.footer {{ display:flex; justify-content:space-between; align-items:center; gap:8px; margin-top:4px; }}
.copy {{ background:#2a63ff; color:#fff; border:none; border-radius:10px; padding:8px 12px; cursor:pointer; }}
.footer .right {{ display:flex; gap:12px; align-items:center; }}
.bestbook {{ color:#b7b7bb; font-size:12px; }}
.modelline {{ color:#b7b7bb; font-size:12px; }}

/* Wider container on large screens (pairs nicely with 3-up grid) */
@media (min-width: 900px) {{
  .container {{ max-width: 1100px; }}
}}
</style>



</head>
<body>
__NAV__
<main class="container">
  <div class="h1">{escape(title)}</div>

  <div class="controls">
    <label>Min edge (bps)
      <input id="minEdge" type="number" value="0" step="10">
    </label>
    <label>Top N
      <input id="topN" type="number" value="10" step="10">
    </label>
    <label>Market
      <select id="marketFilter">{market_opts}</select>
    </label>
    <label>Game
      <select id="gameFilter">{game_opts}</select>
    </label>
    <label>Book
      <select id="bookFilter">{book_opts}</select>
    </label>
    <div style="display:flex; gap:8px;">
      <button class="badge" onclick="applyFilters()">Apply</button>
      <button class="badge reset" onclick="resetFilters()">Reset</button>
    </div>
  </div>

  <div class="note">{consensus_note}</div>

  <div id="list">{cards_html}</div>
  <div id="empty" style="display:none; color:#9b9ba1; margin:12px 0;">No results. Try lowering Min edge or clearing filters.</div>
</main>
<script>
function readInt(id, fallback) {{
  const raw = document.getElementById(id)?.value;
  const v = Number.parseInt(raw, 10);
  return Number.isFinite(v) ? v : fallback;
}}
function readFloat(id, fallback) {{
  const raw = document.getElementById(id)?.value;
  const v = Number.parseFloat(raw);
  return Number.isFinite(v) ? v : fallback;
}}
function getEdge(el) {{
  const raw = el.getAttribute('data-edge');
  if (raw === null || raw === '') return NaN;
  const v = Number.parseFloat(raw);
  return Number.isFinite(v) ? v : NaN;
}}
function showCard(el) {{ el.style.removeProperty('display'); }}  // let CSS decide
function hideCard(el) {{ el.style.display = 'none'; }}


function applyFilters() {{
  const minEdge = readFloat('minEdge', 0);
  const topN    = readInt('topN', 10);
  const mv      = (document.getElementById('marketFilter')?.value || '');
  const gv      = (document.getElementById('gameFilter')?.value || '');
  const bv      = (document.getElementById('bookFilter')?.value || '');

  const list  = document.getElementById('list');
  const empty = document.getElementById('empty');
  const cards = Array.from(list.querySelectorAll('.card'));

  // sort by edge desc; NaN edges sort last
  cards.sort((a,b) => {{
    const ea = getEdge(a), eb = getEdge(b);
    const sa = Number.isFinite(ea) ? ea : -1e9;
    const sb = Number.isFinite(eb) ? eb : -1e9;
    return sb - sa;
  }});

  let shown = 0;
  cards.forEach(c => {{
    const e = getEdge(c);
    const okEdge = Number.isFinite(e) ? (e >= minEdge) : (minEdge <= 0);
    const okMkt  = !mv || c.dataset.market === mv;
    const okGame = !gv || c.dataset.game === gv;
    const okBook = !bv || c.dataset.book === bv;
    const ok = okEdge && okMkt && okGame && okBook;

    if (ok && shown < topN) {{ showCard(c); shown++; }} else {{ hideCard(c); }}
  }});

  empty.style.display = shown ? 'none' : 'block';
}}

function resetFilters() {{
  document.getElementById('minEdge').value = 0;
  document.getElementById('topN').value = 10;
  document.getElementById('marketFilter').selectedIndex = 0;
  document.getElementById('gameFilter').selectedIndex = 0;
  document.getElementById('bookFilter').selectedIndex = 0;
  applyFilters();
}}

function copyCard(btn) {{
  const card = btn.closest('.card');
  const t = (sel) => card.querySelector(sel)?.textContent.trim() || '';
  const text = [t('.row.player'), t('.row.game'), t('.row.time'), t('.row.bet')].filter(Boolean).join(' | ');
  navigator.clipboard.writeText(text);
  btn.textContent = "Copied!"; setTimeout(()=>btn.textContent="Copy bet", 900);
}}

applyFilters();
</script>
</body>
</html>
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged_csv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default=f"{BRAND} — Top Picks")
    ap.add_argument("--limit", type=int, default=25000)  # render cap
    args = ap.parse_args()

    df_all = read_df(args.merged_csv)

    # Build filter options from FULL CSV (pre-limit) so all choices show
    markets_map, games_map, books_map = {}, {}, {}
    if "market" in df_all.columns:
        for m in df_all["market"].dropna():
            lbl = pretty_market(m); markets_map[_norm(lbl)] = lbl
    if "game_disp" in df_all.columns:
        for g in df_all["game_disp"].dropna():
            s = str(g).strip(); games_map[_norm(s)] = s
    if "book" in df_all.columns:
        for b in df_all["book"].dropna():
            s = str(b).strip(); books_map[_norm(s)] = s
    market_pairs = sorted(markets_map.items(), key=lambda x: x[1].lower())
    game_pairs   = sorted(games_map.items(),    key=lambda x: x[1].lower())
    book_pairs   = sorted(books_map.items(),    key=lambda x: x[1].lower())

    # Sort by edge desc & cap rows to render
    df = df_all.sort_values(by="edge_bps", ascending=False).head(min(CARD_LIMIT, args.limit))

    # Render cards
    model_prob_col = df_all.attrs.get("model_prob_col")
    consensus_prob_col = df_all.attrs.get("consensus_prob_col")
    cards = "\n".join(card(r, model_prob_col, consensus_prob_col) for _, r in df.iterrows())

    html = html_page(cards, args.title, market_pairs, game_pairs, book_pairs).replace("__NAV__", nav_html("Top Picks"))
    out_path = Path(args.out); out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    # diagnostics
    nn_edge = int(df_all["edge_bps"].notna().sum()) if "edge_bps" in df_all.columns else 0
    print(f"[top] wrote {args.out}")
    print(f"[top] rows in CSV: {len(df_all)} ; rendered: {len(df)}")
    print(f"[top] non-null edge rows (CSV): {nn_edge}")
    print(f"[top] unique markets: {len(market_pairs)}, games: {len(game_pairs)}, books: {len(book_pairs)}")

if __name__ == "__main__":
    main()
