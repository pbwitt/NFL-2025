#!/usr/bin/env python3
import re, pathlib

ROOT = pathlib.Path("docs")
HTMLS = sorted([p for p in ROOT.rglob("*.html") if p.is_file()])

NAV_CSS = """
/* === NAV (injected) === */
.site-header{position:sticky;top:0;z-index:50;background:rgba(20,20,24,.65);
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  border-bottom:1px solid var(--border,#2a2a2e)}
.navbar{max-width:1100px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:12px}
.brand{font-weight:800;text-decoration:none;color:var(--text,#e9edf6)}
.nav-links{margin-left:auto;display:flex;flex-wrap:wrap;gap:8px}
.nav-link{display:inline-flex;align-items:center;gap:6px;padding:8px 12px;border-radius:10px;
  text-decoration:none;color:var(--text,#e9edf6)}
.nav-link:hover{background:var(--btn-hover,rgba(76,117,255,.14))}
.nav-link.active{border:1px solid var(--accent,#4c74ff);background:rgba(76,117,255,.10)}
@media (max-width:720px){.navbar{padding:8px 12px}.nav-links{gap:6px}}
.nav-link:focus-visible{outline:2px solid var(--accent,#4c74ff);outline-offset:2px;border-radius:10px}
""".strip()

AUTO_ACTIVE_JS = """
<!-- auto-highlight current nav tab -->
<script defer>
(function(){
  const here = location.pathname.replace(/\\/+$/,'');
  document.querySelectorAll('.nav-link').forEach(a=>{
    const href = a.getAttribute('href'); if(!href) return;
    const url = new URL(href, location.href);   // works under /user/repo/
    if (url.pathname.replace(/\\/+$/,'') === here) a.classList.add('active');
  });
})();
</script>
""".strip()

def depth_for(path: pathlib.Path) -> int:
  rel = path.relative_to(ROOT)
  return len(rel.parents) - 1  # index.html => 0; props/x.html => 1

def nav_html(depth: int) -> str:
  pre = "../"*depth
  tabs = [
      (f"{pre}index.html",           "Home"),
      (f"{pre}props/index.html",     "Props"),
      (f"{pre}props/consensus.html", "Consensus"),
      (f"{pre}props/top.html",       "Top Picks"),
      (f"{pre}methods.html",         "Methods"),
  ]
  links = "\n      ".join(f'<a class="nav-link" href="{href}">{label}</a>' for href,label in tabs)
  return f'''<header class="site-header">
  <nav class="navbar">
    <a class="brand" href="{pre}index.html">Fourth &amp; Value 🏈</a>
    <div class="nav-links">
      {links}
    </div>
  </nav>
</header>'''

def inject_css(html: str) -> str:
  if "/* === NAV (injected) === */" in html:
    return html
  if re.search(r"</style>", html, re.I|re.S):
    return re.sub(r"</style>", "\n"+NAV_CSS+"\n</style>", html, count=1, flags=re.I|re.S)
  if re.search(r"</head>", html, re.I|re.S):
    return re.sub(r"</head>", "<style>\n"+NAV_CSS+"\n</style>\n</head>", html, count=1, flags=re.I|re.S)
  return "<style>\n"+NAV_CSS+"\n</style>\n"+html

def inject_nav(html: str, path: pathlib.Path) -> str:
  html = re.sub(r"<header class=\"site-header\"[\\s\\S]*?</header>\\s*", "", html, flags=re.I)
  nav = nav_html(depth_for(path))
  if re.search(r"<body[^>]*>", html, re.I):
    return re.sub(r"(<body[^>]*>)", r"\\1\n"+nav+"\n", html, count=1, flags=re.I)
  else:
    return nav + html

def inject_js(html: str) -> str:
  if "auto-highlight current nav tab" in html:
    return html
  if re.search(r"</body>", html, re.I):
    return re.sub(r"</body>", AUTO_ACTIVE_JS+"\n</body>", html, count=1, flags=re.I)
  return html + "\n" + AUTO_ACTIVE_JS + "\n"

changed = []
for p in HTMLS:
  html = p.read_text(encoding="utf-8", errors="ignore")
  new = inject_css(html)
  new = inject_nav(new, p)
  new = inject_js(new)
  if new != html:
    p.write_text(new, encoding="utf-8")
    changed.append(str(p))

print("Updated files:" if changed else "No changes needed.")
for f in changed: print("-", f)
