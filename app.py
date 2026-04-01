"""
Ketch-All Product Catalog - Single File FastAPI Application
Run: pip install fastapi uvicorn python-multipart aiofiles pillow && python main.py
"""

import os, json, uuid, hashlib, shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import secrets

from fastapi import (
    FastAPI, Request, Form, File, UploadFile, Depends,
    HTTPException, status, Cookie, Response
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# ─── Config ───────────────────────────────────────────────────────────────────
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()  # change me
SECRET_KEY = secrets.token_hex(32)
CONTACT_WHATSAPP = "+918129922989"

DATA_DIR = Path("data")
PRODUCTS_FILE = DATA_DIR / "products.json"
VISITS_FILE = DATA_DIR / "visits.json"
UPLOAD_DIR = Path("uploads")
SESSIONS: dict = {}  # token -> expiry

for d in [DATA_DIR, UPLOAD_DIR]:
    d.mkdir(exist_ok=True)

if not PRODUCTS_FILE.exists():
    PRODUCTS_FILE.write_text("[]")
if not VISITS_FILE.exists():
    VISITS_FILE.write_text("[]")

# ─── Helpers ──────────────────────────────────────────────────────────────────
def load_products() -> list:
    return json.loads(PRODUCTS_FILE.read_text())

def save_products(products: list):
    PRODUCTS_FILE.write_text(json.dumps(products, indent=2))

def load_visits() -> list:
    return json.loads(VISITS_FILE.read_text())

def save_visit(ip: str):
    visits = load_visits()
    visits.append({"ip": ip, "time": datetime.now().isoformat()})
    VISITS_FILE.write_text(json.dumps(visits[-5000:], indent=2))  # keep last 5000

def is_admin(request: Request) -> bool:
    token = request.cookies.get("session")
    if not token:
        return False
    expiry = SESSIONS.get(token)
    if not expiry or datetime.now() > expiry:
        SESSIONS.pop(token, None)
        return False
    return True

def require_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Ketch-All Product Catalog")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ─── HTML Templates ──────────────────────────────────────────────────────────

BASE_STYLE = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;800&family=Barlow:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --red: #D62828;
    --dark: #0A0A0A;
    --mid: #1A1A1A;
    --card: #111111;
    --border: #2A2A2A;
    --gold: #F4A823;
    --text: #E8E8E8;
    --muted: #888;
    --white: #FFFFFF;
  }
  body {
    font-family: 'Barlow', sans-serif;
    background: var(--dark);
    color: var(--text);
    min-height: 100vh;
  }
  a { color: inherit; text-decoration: none; }
  .navbar {
    background: var(--mid);
    border-bottom: 3px solid var(--red);
    padding: 0 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 64px;
    position: sticky; top: 0; z-index: 100;
  }
  .brand {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: 2px;
    color: var(--white);
  }
  .brand span { color: var(--red); }
  .nav-links { display: flex; gap: 1rem; align-items: center; }
  .btn {
    padding: .5rem 1.2rem;
    border: 2px solid var(--red);
    background: transparent;
    color: var(--red);
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 600;
    font-size: 1rem;
    letter-spacing: 1px;
    cursor: pointer;
    transition: all .2s;
    border-radius: 2px;
  }
  .btn:hover, .btn.primary { background: var(--red); color: var(--white); }
  .btn.gold { border-color: var(--gold); color: var(--gold); }
  .btn.gold:hover { background: var(--gold); color: var(--dark); }
  .btn.sm { padding: .3rem .8rem; font-size: .85rem; }
  .btn.danger { border-color: #c00; color: #c00; }
  .btn.danger:hover { background: #c00; color: var(--white); }
  .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
  .hero {
    background: linear-gradient(135deg, var(--mid) 0%, #1a0505 100%);
    border-bottom: 1px solid var(--border);
    padding: 4rem 2rem;
    text-align: center;
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: 'KETCH-ALL';
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 12rem; font-weight: 800;
    color: rgba(214,40,40,.04);
    white-space: nowrap;
    pointer-events: none;
  }
  .hero h1 {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: clamp(2.5rem, 6vw, 5rem);
    font-weight: 800;
    letter-spacing: 4px;
    line-height: 1;
    position: relative;
  }
  .hero h1 span { color: var(--red); }
  .hero p {
    color: var(--muted);
    margin-top: 1rem;
    font-size: 1.1rem;
    font-weight: 300;
    position: relative;
  }
  .badge {
    display: inline-block;
    background: var(--red);
    color: var(--white);
    font-family: 'Barlow Condensed', sans-serif;
    font-size: .75rem;
    letter-spacing: 2px;
    padding: .2rem .6rem;
    margin-bottom: 1rem;
    border-radius: 1px;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
    margin-top: 2rem;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow: hidden;
    transition: border-color .2s, transform .2s;
  }
  .card:hover { border-color: var(--red); transform: translateY(-2px); }
  .card-img {
    width: 100%; height: 200px;
    object-fit: cover;
    background: var(--mid);
    display: flex; align-items: center; justify-content: center;
    color: var(--border);
    font-size: 3rem;
  }
  .card-img img { width: 100%; height: 100%; object-fit: cover; }
  .card-body { padding: 1.2rem; }
  .card-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 1.3rem;
    font-weight: 700;
    letter-spacing: 1px;
    margin-bottom: .3rem;
  }
  .card-cat {
    font-size: .75rem;
    letter-spacing: 2px;
    color: var(--red);
    text-transform: uppercase;
    margin-bottom: .6rem;
    font-weight: 600;
  }
  .card-desc {
    color: var(--muted);
    font-size: .88rem;
    line-height: 1.6;
    margin-bottom: 1rem;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .card-actions { display: flex; gap: .5rem; flex-wrap: wrap; }
  .section-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: 2px;
    border-left: 4px solid var(--red);
    padding-left: 1rem;
    margin: 2rem 0 1rem;
  }
  /* Modal */
  .modal-overlay {
    display: none; position: fixed; inset: 0;
    background: rgba(0,0,0,.85);
    z-index: 1000; align-items: center; justify-content: center;
  }
  .modal-overlay.open { display: flex; }
  .modal {
    background: var(--mid);
    border: 1px solid var(--border);
    border-top: 3px solid var(--red);
    border-radius: 4px;
    width: 90%; max-width: 520px;
    padding: 2rem;
    position: relative;
    animation: slideUp .2s ease;
  }
  @keyframes slideUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
  .modal-close {
    position: absolute; top: 1rem; right: 1rem;
    background: none; border: none; color: var(--muted);
    font-size: 1.4rem; cursor: pointer;
  }
  .modal-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 1.6rem; font-weight: 800; margin-bottom: 1.2rem;
  }
  .form-group { margin-bottom: 1rem; }
  .form-group label { display: block; font-size: .85rem; color: var(--muted); margin-bottom: .4rem; letter-spacing: 1px; text-transform: uppercase; }
  .form-group input, .form-group textarea, .form-group select {
    width: 100%;
    background: var(--dark);
    border: 1px solid var(--border);
    color: var(--text);
    padding: .7rem 1rem;
    border-radius: 2px;
    font-family: 'Barlow', sans-serif;
    font-size: .95rem;
    transition: border-color .2s;
  }
  .form-group input:focus, .form-group textarea:focus {
    outline: none; border-color: var(--red);
  }
  .form-group textarea { resize: vertical; min-height: 100px; }
  .alert {
    padding: .8rem 1rem;
    border-radius: 2px;
    margin-bottom: 1rem;
    font-size: .9rem;
    border-left: 3px solid;
  }
  .alert.success { background: #0a1f0a; border-color: #2d7a2d; color: #6fc96f; }
  .alert.error { background: #1f0a0a; border-color: var(--red); color: #e88; }
  /* Admin */
  .admin-layout { display: grid; grid-template-columns: 220px 1fr; min-height: calc(100vh - 64px); }
  .sidebar {
    background: var(--mid);
    border-right: 1px solid var(--border);
    padding: 1.5rem 0;
  }
  .sidebar-link {
    display: flex; align-items: center; gap: .8rem;
    padding: .8rem 1.5rem;
    color: var(--muted);
    font-weight: 500;
    transition: all .2s;
    border-left: 3px solid transparent;
  }
  .sidebar-link:hover, .sidebar-link.active {
    color: var(--white);
    background: rgba(214,40,40,.1);
    border-left-color: var(--red);
  }
  .main-content { padding: 2rem; }
  .stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .stat-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1.2rem;
  }
  .stat-num {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 2.5rem; font-weight: 800;
    color: var(--red);
  }
  .stat-label { color: var(--muted); font-size: .85rem; letter-spacing: 1px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: .8rem 1rem; border-bottom: 1px solid var(--border); font-size: .9rem; }
  th { color: var(--muted); font-weight: 500; letter-spacing: 1px; text-transform: uppercase; font-size: .78rem; }
  tr:hover td { background: rgba(255,255,255,.02); }
  .tag {
    display: inline-block;
    background: rgba(214,40,40,.15);
    color: var(--red);
    border: 1px solid rgba(214,40,40,.3);
    padding: .1rem .5rem;
    border-radius: 2px;
    font-size: .75rem;
    letter-spacing: 1px;
  }
  .whatsapp-btn {
    display: inline-flex; align-items: center; gap: .5rem;
    background: #25D366; color: #fff;
    padding: .6rem 1.2rem;
    border-radius: 2px;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 600;
    font-size: 1rem;
    letter-spacing: 1px;
    transition: opacity .2s;
  }
  .whatsapp-btn:hover { opacity: .85; }
  .product-detail { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }
  @media (max-width: 640px) {
    .product-detail { grid-template-columns: 1fr; }
    .admin-layout { grid-template-columns: 1fr; }
    .sidebar { display: none; }
  }
  .specs-table td:first-child { color: var(--muted); font-weight: 500; width: 40%; }
  .upload-area {
    border: 2px dashed var(--border);
    border-radius: 4px;
    padding: 1.5rem;
    text-align: center;
    color: var(--muted);
    cursor: pointer;
    transition: border-color .2s;
  }
  .upload-area:hover { border-color: var(--red); }
  input[type=file] { display: none; }
  footer {
    background: var(--mid);
    border-top: 1px solid var(--border);
    text-align: center;
    padding: 1.5rem;
    color: var(--muted);
    font-size: .85rem;
    margin-top: 3rem;
  }
  footer span { color: var(--red); }
</style>
"""

def navbar(admin=False):
    links = ""
    if admin:
        links = '<a href="/admin/dashboard" class="btn sm">Dashboard</a> <a href="/admin/logout" class="btn sm danger">Logout</a>'
    else:
        links = '<a href="/admin/login" class="btn sm">Admin</a>'
    return f"""
    <nav class="navbar">
      <a href="/" class="brand">KETCH<span>-</span>ALL</a>
      <div class="nav-links">{links}</div>
    </nav>"""

# ─── Public Routes ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    save_visit(request.client.host)
    products = load_products()
    # Group by category
    categories = {}
    for p in products:
        cat = p.get("category", "General")
        categories.setdefault(cat, []).append(p)

    cards_html = ""
    for cat, prods in categories.items():
        cards_html += f'<h2 class="section-title">{cat}</h2><div class="grid">'
        for p in prods:
            img_html = f'<img src="/uploads/{p["image"]}" alt="{p["name"]}">' if p.get("image") else "📦"
            wa_msg = f"Hello! I'm interested in: *{p['name']}*. Please send me more details."
            wa_link = f"https://wa.me/{CONTACT_WHATSAPP.replace('+','').replace(' ','')}?text={wa_msg.replace(' ', '%20')}"
            cards_html += f"""
            <div class="card">
              <div class="card-img">{img_html}</div>
              <div class="card-body">
                <div class="card-cat">{cat}</div>
                <div class="card-title">{p['name']}</div>
                <div class="card-desc">{p.get('description','')}</div>
                <div class="card-actions">
                  <a href="/product/{p['id']}" class="btn sm primary">View Details</a>
                  <a href="{wa_link}" target="_blank" class="btn sm gold">Get Quote</a>
                </div>
              </div>
            </div>"""
        cards_html += "</div>"

    empty = "" if products else '<div style="text-align:center;padding:4rem;color:var(--muted);font-size:1.1rem;">No products listed yet. Check back soon.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>{BASE_STYLE}<title>Ketch-All Products</title></head>
<body>
{navbar()}
<div class="hero">
  <div class="badge">INDUSTRIAL SAFETY EQUIPMENT</div>
  <h1>KETCH<span>-ALL</span><br>PRODUCTS</h1>
  <p>Aircraft-grade quality · Made in USA · Trusted by Industry</p>
</div>
<div class="container">
  {cards_html}
  {empty}
</div>
<footer>© 2024 <span>Ketch-All</span> · Contact: {CONTACT_WHATSAPP} · All products made with aircraft-grade aluminium</footer>
</body></html>"""


@app.get("/product/{pid}", response_class=HTMLResponse)
async def product_detail(pid: str, request: Request):
    products = load_products()
    p = next((x for x in products if x["id"] == pid), None)
    if not p:
        return RedirectResponse("/")

    img_html = f'<img src="/uploads/{p["image"]}" style="width:100%;border-radius:4px;" alt="{p["name"]}">' if p.get("image") else '<div class="card-img" style="height:280px;border-radius:4px;background:var(--mid);display:flex;align-items:center;justify-content:center;font-size:5rem;">📦</div>'

    wa_msg = f"Hello! I'm interested in: *{p['name']}*. Please send me more details and a quote."
    wa_link = f"https://wa.me/{CONTACT_WHATSAPP.replace('+','').replace(' ','')}?text={wa_msg.replace(' ', '%20')}"

    specs_rows = ""
    for spec in p.get("specs", []):
        if ":" in spec:
            k, v = spec.split(":", 1)
            specs_rows += f"<tr><td>{k.strip()}</td><td>{v.strip()}</td></tr>"

    specs_section = f"""
    <h3 style="font-family:'Barlow Condensed',sans-serif;font-size:1.2rem;letter-spacing:1px;margin:1.2rem 0 .6rem;">SPECIFICATIONS</h3>
    <table class="specs-table"><tbody>{specs_rows}</tbody></table>
    """ if specs_rows else ""

    tags_html = " ".join(f'<span class="tag">{t.strip()}</span>' for t in p.get("tags","").split(",") if t.strip())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>{BASE_STYLE}<title>{p['name']} – Ketch-All</title></head>
<body>
{navbar()}
<div class="container" style="padding-top:2rem;">
  <a href="/" style="color:var(--muted);font-size:.9rem;">← Back to Products</a>
  <div class="product-detail" style="margin-top:1.5rem;">
    <div>{img_html}</div>
    <div>
      <div class="badge">{p.get('category','General')}</div>
      <h1 style="font-family:'Barlow Condensed',sans-serif;font-size:2.5rem;font-weight:800;letter-spacing:2px;margin:.3rem 0;">{p['name']}</h1>
      <div style="margin-bottom:1rem;">{tags_html}</div>
      <p style="color:var(--muted);line-height:1.8;margin-bottom:1.5rem;">{p.get('description','')}</p>
      {specs_section}
      <div style="margin-top:1.5rem;display:flex;gap:1rem;flex-wrap:wrap;">
        <a href="{wa_link}" target="_blank" class="whatsapp-btn">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.126.554 4.126 1.527 5.865L.057 23.863a.75.75 0 0 0 .92.92l6.01-1.472A11.955 11.955 0 0 0 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75a9.73 9.73 0 0 1-4.964-1.359l-.357-.213-3.7.906.924-3.594-.233-.37A9.731 9.731 0 0 1 2.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>
          GET QUOTE ON WHATSAPP
        </a>
        <a href="/" class="btn">← All Products</a>
      </div>
      <p style="margin-top:1rem;color:var(--muted);font-size:.85rem;">📞 {CONTACT_WHATSAPP}</p>
    </div>
  </div>
</div>
<footer>© 2024 <span>Ketch-All</span> · All products made with aircraft-grade aluminium</footer>
</body></html>"""


# ─── Admin Auth ────────────────────────────────────────────────────────────────

@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if is_admin(request):
        return RedirectResponse("/admin/dashboard")
    err_html = f'<div class="alert error">{error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>{BASE_STYLE}<title>Admin Login – Ketch-All</title>
<style>
  .login-wrap {{ min-height:100vh; display:flex; align-items:center; justify-content:center; }}
  .login-box {{ background:var(--mid); border:1px solid var(--border); border-top:3px solid var(--red); border-radius:4px; padding:2.5rem; width:100%; max-width:380px; }}
</style>
</head>
<body>
{navbar()}
<div class="login-wrap">
  <div class="login-box">
    <div class="badge" style="margin-bottom:1rem;">ADMIN ACCESS</div>
    <h1 style="font-family:'Barlow Condensed',sans-serif;font-size:2rem;font-weight:800;margin-bottom:1.5rem;">SIGN IN</h1>
    {err_html}
    <form method="post" action="/admin/login">
      <div class="form-group">
        <label>Username</label>
        <input type="text" name="username" autocomplete="username" required>
      </div>
      <div class="form-group">
        <label>Password</label>
        <input type="password" name="password" autocomplete="current-password" required>
      </div>
      <button type="submit" class="btn primary" style="width:100%;margin-top:.5rem;">LOGIN</button>
    </form>
    <p style="color:var(--muted);font-size:.8rem;margin-top:1rem;text-align:center;">Default: admin / admin123</p>
  </div>
</div>
</body></html>"""


@app.post("/admin/login")
async def do_login(response: Response, username: str = Form(...), password: str = Form(...)):
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if username != ADMIN_USERNAME or pw_hash != ADMIN_PASSWORD_HASH:
        return RedirectResponse("/admin/login?error=Invalid+credentials", status_code=303)
    token = secrets.token_hex(32)
    SESSIONS[token] = datetime.now() + timedelta(hours=8)
    resp = RedirectResponse("/admin/dashboard", status_code=303)
    resp.set_cookie("session", token, httponly=True, samesite="lax", max_age=28800)
    return resp


@app.get("/admin/logout")
async def logout(response: Response):
    resp = RedirectResponse("/admin/login", status_code=303)
    resp.delete_cookie("session")
    return resp


# ─── Admin Dashboard ──────────────────────────────────────────────────────────

def admin_sidebar(active="dashboard"):
    links = [
        ("dashboard", "/admin/dashboard", "📊 Dashboard"),
        ("products", "/admin/products", "📦 Products"),
        ("visitors", "/admin/visitors", "👥 Visitors"),
    ]
    items = ""
    for key, href, label in links:
        cls = "sidebar-link active" if active == key else "sidebar-link"
        items += f'<a href="{href}" class="{cls}">{label}</a>'
    return f'<aside class="sidebar">{items}</aside>'


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    require_admin(request)
    products = load_products()
    visits = load_visits()
    today = datetime.now().strftime("%Y-%m-%d")
    today_visits = sum(1 for v in visits if v["time"].startswith(today))
    unique_ips = len(set(v["ip"] for v in visits))
    categories = len(set(p.get("category","") for p in products))

    recent_visits = visits[-10:][::-1]
    visit_rows = "".join(
        f"<tr><td>{v['ip']}</td><td>{v['time'][:19].replace('T',' ')}</td></tr>"
        for v in recent_visits
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>{BASE_STYLE}<title>Dashboard – Admin</title></head>
<body>
{navbar(admin=True)}
<div class="admin-layout">
  {admin_sidebar("dashboard")}
  <div class="main-content">
    <h1 class="section-title">DASHBOARD</h1>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-num">{len(products)}</div><div class="stat-label">TOTAL PRODUCTS</div></div>
      <div class="stat-card"><div class="stat-num">{categories}</div><div class="stat-label">CATEGORIES</div></div>
      <div class="stat-card"><div class="stat-num">{len(visits)}</div><div class="stat-label">TOTAL VISITS</div></div>
      <div class="stat-card"><div class="stat-num">{today_visits}</div><div class="stat-label">TODAY'S VISITS</div></div>
      <div class="stat-card"><div class="stat-num">{unique_ips}</div><div class="stat-label">UNIQUE VISITORS</div></div>
    </div>
    <h2 class="section-title" style="font-size:1.3rem;">RECENT VISITORS</h2>
    <div style="background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:auto;">
      <table>
        <thead><tr><th>IP Address</th><th>Time</th></tr></thead>
        <tbody>{visit_rows}</tbody>
      </table>
    </div>
  </div>
</div>
</body></html>"""


@app.get("/admin/products", response_class=HTMLResponse)
async def admin_products(request: Request, msg: str = ""):
    require_admin(request)
    products = load_products()
    msg_html = f'<div class="alert success">{msg}</div>' if msg else ""

    rows = ""
    for p in products:
        img_tag = f'<img src="/uploads/{p["image"]}" style="width:50px;height:40px;object-fit:cover;border-radius:2px;">' if p.get("image") else "—"
        rows += f"""<tr>
          <td>{img_tag}</td>
          <td><strong>{p['name']}</strong></td>
          <td><span class="tag">{p.get('category','—')}</span></td>
          <td style="color:var(--muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{p.get('description','')[:80]}</td>
          <td>
            <a href="/admin/products/edit/{p['id']}" class="btn sm">Edit</a>
            <a href="/admin/products/delete/{p['id']}" class="btn sm danger" onclick="return confirm('Delete this product?')">Del</a>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>{BASE_STYLE}<title>Products – Admin</title></head>
<body>
{navbar(admin=True)}
<div class="admin-layout">
  {admin_sidebar("products")}
  <div class="main-content">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;">
      <h1 class="section-title" style="margin:0;">PRODUCTS</h1>
      <button class="btn primary" onclick="document.getElementById('add-modal').classList.add('open')">+ ADD PRODUCT</button>
    </div>
    {msg_html}
    <div style="background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:auto;">
      <table>
        <thead><tr><th>Image</th><th>Name</th><th>Category</th><th>Description</th><th>Actions</th></tr></thead>
        <tbody>{rows if rows else '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:2rem;">No products yet</td></tr>'}</tbody>
      </table>
    </div>
  </div>
</div>

<!-- Add Product Modal -->
<div class="modal-overlay" id="add-modal">
  <div class="modal" style="max-width:580px;max-height:90vh;overflow-y:auto;">
    <button class="modal-close" onclick="document.getElementById('add-modal').classList.remove('open')">✕</button>
    <div class="modal-title">ADD PRODUCT</div>
    <form method="post" action="/admin/products/add" enctype="multipart/form-data">
      <div class="form-group"><label>Product Name *</label><input type="text" name="name" required></div>
      <div class="form-group"><label>Category *</label><input type="text" name="category" placeholder="e.g. Snare Tool, Safety Glasses" required></div>
      <div class="form-group"><label>Description</label><textarea name="description" rows="4" placeholder="Detailed product description..."></textarea></div>
      <div class="form-group"><label>Specifications (one per line, format: Label: Value)</label><textarea name="specs" rows="4" placeholder="Material: Aircraft-grade Aluminium&#10;Sizes: 3FT, 4FT, 5FT&#10;Release: Dual Release"></textarea></div>
      <div class="form-group"><label>Tags (comma separated)</label><input type="text" name="tags" placeholder="aluminium, safety, drill-pipe"></div>
      <div class="form-group">
        <label>Product Image</label>
        <label class="upload-area" for="add-img-input">
          <div>📷 Click to upload image</div>
          <div style="font-size:.8rem;margin-top:.3rem;" id="add-img-name">PNG, JPG up to 10MB</div>
        </label>
        <input type="file" id="add-img-input" name="image" accept="image/*" onchange="document.getElementById('add-img-name').textContent=this.files[0]?.name||'No file chosen'">
      </div>
      <button type="submit" class="btn primary" style="width:100%;">ADD PRODUCT</button>
    </form>
  </div>
</div>
</body></html>"""


@app.post("/admin/products/add")
async def add_product(
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    specs: str = Form(""),
    tags: str = Form(""),
    image: Optional[UploadFile] = File(None)
):
    require_admin(request)
    products = load_products()
    pid = str(uuid.uuid4())[:8]
    img_filename = None
    if image and image.filename:
        ext = Path(image.filename).suffix.lower()
        img_filename = f"{pid}{ext}"
        contents = await image.read()
        (UPLOAD_DIR / img_filename).write_bytes(contents)

    products.append({
        "id": pid,
        "name": name,
        "category": category,
        "description": description,
        "specs": [s.strip() for s in specs.splitlines() if s.strip()],
        "tags": tags,
        "image": img_filename,
        "created": datetime.now().isoformat()
    })
    save_products(products)
    return RedirectResponse("/admin/products?msg=Product+added+successfully", status_code=303)


@app.get("/admin/products/edit/{pid}", response_class=HTMLResponse)
async def edit_product_page(pid: str, request: Request):
    require_admin(request)
    products = load_products()
    p = next((x for x in products if x["id"] == pid), None)
    if not p:
        return RedirectResponse("/admin/products")

    img_preview = f'<img src="/uploads/{p["image"]}" style="width:100%;max-height:150px;object-fit:cover;border-radius:2px;margin-bottom:.5rem;">' if p.get("image") else ""
    specs_text = "\n".join(p.get("specs", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>{BASE_STYLE}<title>Edit Product – Admin</title></head>
<body>
{navbar(admin=True)}
<div class="admin-layout">
  {admin_sidebar("products")}
  <div class="main-content">
    <h1 class="section-title">EDIT PRODUCT</h1>
    <div style="background:var(--card);border:1px solid var(--border);border-radius:4px;padding:2rem;max-width:620px;">
      <form method="post" action="/admin/products/edit/{pid}" enctype="multipart/form-data">
        <div class="form-group"><label>Product Name *</label><input type="text" name="name" value="{p['name']}" required></div>
        <div class="form-group"><label>Category *</label><input type="text" name="category" value="{p.get('category','')}"></div>
        <div class="form-group"><label>Description</label><textarea name="description">{p.get('description','')}</textarea></div>
        <div class="form-group"><label>Specifications</label><textarea name="specs">{specs_text}</textarea></div>
        <div class="form-group"><label>Tags</label><input type="text" name="tags" value="{p.get('tags','')}"></div>
        <div class="form-group">
          <label>Product Image</label>
          {img_preview}
          <label class="upload-area" for="edit-img-input">
            <div>📷 Click to replace image (optional)</div>
            <div style="font-size:.8rem;margin-top:.3rem;" id="edit-img-name">Leave empty to keep current</div>
          </label>
          <input type="file" id="edit-img-input" name="image" accept="image/*" onchange="document.getElementById('edit-img-name').textContent=this.files[0]?.name||''">
        </div>
        <div style="display:flex;gap:1rem;">
          <button type="submit" class="btn primary">SAVE CHANGES</button>
          <a href="/admin/products" class="btn">Cancel</a>
        </div>
      </form>
    </div>
  </div>
</div>
</body></html>"""


@app.post("/admin/products/edit/{pid}")
async def do_edit_product(
    pid: str, request: Request,
    name: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    specs: str = Form(""),
    tags: str = Form(""),
    image: Optional[UploadFile] = File(None)
):
    require_admin(request)
    products = load_products()
    idx = next((i for i, p in enumerate(products) if p["id"] == pid), None)
    if idx is None:
        return RedirectResponse("/admin/products")

    img_filename = products[idx].get("image")
    if image and image.filename:
        ext = Path(image.filename).suffix.lower()
        img_filename = f"{pid}{ext}"
        contents = await image.read()
        (UPLOAD_DIR / img_filename).write_bytes(contents)

    products[idx].update({
        "name": name,
        "category": category,
        "description": description,
        "specs": [s.strip() for s in specs.splitlines() if s.strip()],
        "tags": tags,
        "image": img_filename,
    })
    save_products(products)
    return RedirectResponse("/admin/products?msg=Product+updated", status_code=303)


@app.get("/admin/products/delete/{pid}")
async def delete_product(pid: str, request: Request):
    require_admin(request)
    products = load_products()
    p = next((x for x in products if x["id"] == pid), None)
    if p and p.get("image"):
        img_path = UPLOAD_DIR / p["image"]
        if img_path.exists():
            img_path.unlink()
    products = [x for x in products if x["id"] != pid]
    save_products(products)
    return RedirectResponse("/admin/products?msg=Product+deleted", status_code=303)


@app.get("/admin/visitors", response_class=HTMLResponse)
async def admin_visitors(request: Request):
    require_admin(request)
    visits = load_visits()
    today = datetime.now().strftime("%Y-%m-%d")
    today_visits = [v for v in visits if v["time"].startswith(today)]

    # Last 7 days stats
    day_counts = {}
    for v in visits:
        day = v["time"][:10]
        day_counts[day] = day_counts.get(day, 0) + 1

    recent = sorted(day_counts.items(), reverse=True)[:7]
    day_rows = "".join(f"<tr><td>{d}</td><td>{c}</td></tr>" for d, c in recent)

    recent_all = visits[-50:][::-1]
    visit_rows = "".join(
        f"<tr><td>{v['ip']}</td><td>{v['time'][:19].replace('T',' ')}</td></tr>"
        for v in recent_all
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>{BASE_STYLE}<title>Visitors – Admin</title></head>
<body>
{navbar(admin=True)}
<div class="admin-layout">
  {admin_sidebar("visitors")}
  <div class="main-content">
    <h1 class="section-title">VISITOR ANALYTICS</h1>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-num">{len(visits)}</div><div class="stat-label">TOTAL VISITS</div></div>
      <div class="stat-card"><div class="stat-num">{len(today_visits)}</div><div class="stat-label">TODAY</div></div>
      <div class="stat-card"><div class="stat-num">{len(set(v['ip'] for v in visits))}</div><div class="stat-label">UNIQUE IPs</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 2fr;gap:1.5rem;margin-top:1rem;">
      <div>
        <h2 class="section-title" style="font-size:1.2rem;">LAST 7 DAYS</h2>
        <div style="background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:auto;">
          <table><thead><tr><th>Date</th><th>Visits</th></tr></thead><tbody>{day_rows}</tbody></table>
        </div>
      </div>
      <div>
        <h2 class="section-title" style="font-size:1.2rem;">RECENT 50 VISITS</h2>
        <div style="background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:auto;max-height:500px;">
          <table><thead><tr><th>IP Address</th><th>Time</th></tr></thead><tbody>{visit_rows}</tbody></table>
        </div>
      </div>
    </div>
  </div>
</div>
</body></html>"""


# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*50)
    print("  Ketch-All Product Catalog")
    print("  http://localhost:8000")
    print("  Admin: http://localhost:8000/admin/login")
    print("  Default login: admin / admin123")
    print("="*50)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
