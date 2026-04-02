"""
NAWA Global General Trading — Product Catalog
Features: Multi-image upload, pagination, admin visit analytics filtering
Public Pages: Home, About, Products & Services, Contact
Run: pip install fastapi uvicorn python-multipart aiofiles pillow && python main.py
"""

import os, json, uuid, hashlib, shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import secrets, math

from fastapi import (
    FastAPI, Request, Form, File, UploadFile, Depends,
    HTTPException, status, Cookie, Response
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from PIL import Image
from io import BytesIO

# ─── Config ───────────────────────────────────────────────────────────────────
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()
SECRET_KEY = secrets.token_hex(32)
CONTACT_WHATSAPP = "+971505464847"
CONTACT_EMAIL = "info@nawaglobalgtd.com"
CONTACT_WEBSITE = "www.nawaglobalgtd.com"
CONTACT_ADDRESS = "Mussafah, Abu Dhabi, United Arab Emirates"
ADMIN_ROUTE = "/admin12"
PRODUCTS_PER_PAGE = 9

DATA_DIR = Path("data")
PRODUCTS_FILE = DATA_DIR / "products.json"
VISITS_FILE   = DATA_DIR / "visits.json"
UPLOAD_DIR    = Path("uploads")
SESSIONS: dict = {}

for d in [DATA_DIR, UPLOAD_DIR]:
    d.mkdir(exist_ok=True)
if not PRODUCTS_FILE.exists(): PRODUCTS_FILE.write_text("[]")
if not VISITS_FILE.exists():   VISITS_FILE.write_text("[]")

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
    VISITS_FILE.write_text(json.dumps(visits[-5000:], indent=2))

def is_admin(request: Request) -> bool:
    token = request.cookies.get("session")
    if not token: return False
    expiry = SESSIONS.get(token)
    if not expiry or datetime.now() > expiry:
        SESSIONS.pop(token, None)
        return False
    return True

def require_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=303, headers={"Location": f"{ADMIN_ROUTE}/login"})

async def save_image(image: UploadFile, pid: str, suffix: str = "") -> Optional[str]:
    if not image or not image.filename:
        return None
    ext = Path(image.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        return None
    contents = await image.read()
    img = Image.open(BytesIO(contents)).convert("RGB")
    max_size = (800, 800)
    img.thumbnail(max_size)
    fname = f"{pid}{suffix}.jpg"
    save_path = UPLOAD_DIR / fname
    img.save(save_path, format="JPEG", quality=85)
    return fname

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="NAWA Global General Trading")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ═══════════════════════════════════════════════════════════════════════════════
# STYLES — NAWA Global brand: deep green + gold, editorial-industrial
# ═══════════════════════════════════════════════════════════════════════════════
BASE_STYLE = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Barlow:wght@300;400;500;600;700&family=Barlow+Condensed:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  :root{
    --green:#1B5E20;--green2:#2E7D32;--green3:#388E3C;--green-light:#4CAF50;
    --gold:#D4A017;--gold-light:#E8B84B;--gold-dark:#B8860B;
    --danger:#C0392B;--success:#27AE60;--tr:.3s cubic-bezier(.4,0,.2,1)
  }
  [data-theme="dark"]{
    --bg:#0A0F0A;--bg2:#111711;--bg3:#182018;--surface:#141A14;--surface2:#1C241C;
    --border:rgba(255,255,255,.07);--border-accent:rgba(212,160,23,.4);
    --text:#F0EEE8;--text2:#A8A89E;--text3:#6B6B60;
    --nav-bg:rgba(10,15,10,.92);--cshadow:0 4px 24px rgba(0,0,0,.5);--chshadow:0 12px 48px rgba(0,0,0,.7)
  }
  [data-theme="light"]{
    --bg:#F5F7F4;--bg2:#ECEEE8;--bg3:#E0E4DB;--surface:#FFF;--surface2:#F2F4EF;
    --border:rgba(0,0,0,.08);--border-accent:rgba(212,160,23,.5);
    --text:#141A14;--text2:#4A5A4A;--text3:#8A9A8A;
    --nav-bg:rgba(245,247,244,.94);--cshadow:0 2px 16px rgba(0,0,0,.08);--chshadow:0 12px 40px rgba(0,0,0,.15)
  }
  body{font-family:'Barlow',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;transition:background var(--tr),color var(--tr);overflow-x:hidden}
  a{color:inherit;text-decoration:none}
  ::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:var(--bg)}::-webkit-scrollbar-thumb{background:var(--border-accent);border-radius:3px}

  /* Navbar */
  .navbar{position:fixed;top:0;left:0;right:0;z-index:200;background:var(--nav-bg);backdrop-filter:blur(20px) saturate(1.8);border-bottom:1px solid var(--border);height:72px;display:flex;align-items:center;justify-content:space-between;padding:0 2.5rem}
  .brand{display:flex;align-items:center;gap:.75rem}
  .brand-logo{width:44px;height:44px;background:linear-gradient(135deg,var(--green2),var(--green-light));border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.4rem;font-weight:900;color:#fff;font-family:'Barlow Condensed',sans-serif;letter-spacing:-1px}
  .brand-text{display:flex;flex-direction:column}
  .brand-name{font-family:'Barlow Condensed',sans-serif;font-size:1.15rem;font-weight:700;letter-spacing:1px;color:var(--text);line-height:1;text-transform:uppercase}
  .brand-sub{font-size:.58rem;letter-spacing:2.5px;color:var(--gold);text-transform:uppercase;font-weight:600;margin-top:1px}
  .nav-links{display:flex;align-items:center;gap:.25rem}
  .nav-link{padding:.45rem .9rem;border-radius:6px;font-size:.85rem;font-weight:500;color:var(--text2);transition:all var(--tr);letter-spacing:.3px}
  .nav-link:hover{color:var(--text);background:var(--bg3)}
  .nav-link.active{color:var(--green-light);background:rgba(76,175,80,.08)}
  .nav-right{display:flex;align-items:center;gap:.8rem}
  .theme-toggle{width:40px;height:22px;background:var(--bg3);border:1px solid var(--border);border-radius:11px;cursor:pointer;position:relative;display:flex;align-items:center;padding:2px;transition:background var(--tr)}
  .theme-toggle::after{content:'';width:16px;height:16px;background:var(--gold);border-radius:50%;transition:transform var(--tr)}
  [data-theme="light"] .theme-toggle::after{transform:translateX(18px)}

  /* Buttons */
  .btn{font-family:'Barlow',sans-serif;font-weight:600;font-size:.85rem;letter-spacing:.3px;padding:.55rem 1.4rem;border-radius:6px;border:1.5px solid var(--border);background:transparent;color:var(--text2);cursor:pointer;transition:all var(--tr);display:inline-flex;align-items:center;gap:.4rem;white-space:nowrap}
  .btn:hover{border-color:var(--green3);color:var(--green-light)}
  .btn.primary{background:var(--green2);border-color:var(--green2);color:#fff}
  .btn.primary:hover{background:var(--green3);border-color:var(--green3)}
  .btn.gold{background:var(--gold);border-color:var(--gold);color:#000}
  .btn.gold:hover{background:var(--gold-light);border-color:var(--gold-light)}
  .btn.outline-gold{border-color:var(--gold);color:var(--gold)}
  .btn.outline-gold:hover{background:var(--gold);color:#000}
  .btn.outline-green{border-color:var(--green3);color:var(--green-light)}
  .btn.outline-green:hover{background:var(--green2);color:#fff}
  .btn.danger{border-color:var(--danger);color:var(--danger)}
  .btn.danger:hover{background:var(--danger);color:#fff}
  .btn.sm{padding:.32rem .85rem;font-size:.78rem;border-radius:5px}
  .btn.lg{padding:.9rem 2.4rem;font-size:1rem;border-radius:8px}
  .btn:disabled{opacity:.4;cursor:not-allowed}
  .wa-btn{display:inline-flex;align-items:center;gap:.6rem;background:#25D366;color:#fff;font-family:'Barlow',sans-serif;font-weight:700;font-size:.95rem;padding:.75rem 1.6rem;border-radius:8px;transition:all var(--tr);border:none;cursor:pointer;letter-spacing:.3px}
  .wa-btn:hover{background:#1ebe5d;transform:translateY(-1px);box-shadow:0 4px 16px rgba(37,211,102,.35)}

  /* Hero */
  .hero{padding:140px 2.5rem 90px;background:var(--bg);position:relative;overflow:hidden;margin-top:72px}
  .hero-bg-pattern{position:absolute;inset:0;background-image:repeating-linear-gradient(0deg,transparent,transparent 59px,var(--border) 59px,var(--border) 60px),repeating-linear-gradient(90deg,transparent,transparent 59px,var(--border) 59px,var(--border) 60px);opacity:.4}
  .hero-glow-green{position:absolute;top:-80px;left:-80px;width:500px;height:500px;background:radial-gradient(circle,rgba(46,125,50,.15) 0%,transparent 70%);pointer-events:none}
  .hero-glow-gold{position:absolute;bottom:-100px;right:-100px;width:400px;height:400px;background:radial-gradient(circle,rgba(212,160,23,.1) 0%,transparent 70%);pointer-events:none}
  .hero-inner{max-width:1140px;margin:0 auto;position:relative;display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:center}
  .hero-eyebrow{font-family:'Barlow Condensed',sans-serif;font-size:.72rem;letter-spacing:5px;text-transform:uppercase;color:var(--gold);margin-bottom:1.2rem;display:flex;align-items:center;gap:.8rem}
  .hero-eyebrow::before{content:'';width:36px;height:2px;background:var(--gold)}
  .hero-title{font-family:'Playfair Display',serif;font-size:clamp(2.6rem,5vw,4.2rem);line-height:1.08;letter-spacing:-.5px;color:var(--text);margin-bottom:1.2rem}
  .hero-title em{color:var(--green-light);font-style:italic}
  .hero-sub{font-size:1.05rem;color:var(--text2);font-weight:300;line-height:1.75;margin-bottom:2.2rem}
  .hero-cta{display:flex;gap:1rem;flex-wrap:wrap;align-items:center}
  .hero-right{display:flex;flex-direction:column;gap:1.2rem}
  .hero-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:1.4rem 1.6rem;transition:border-color var(--tr)}
  .hero-card:hover{border-color:var(--border-accent)}
  .hero-card-icon{font-size:1.6rem;margin-bottom:.6rem}
  .hero-card-title{font-family:'Barlow Condensed',sans-serif;font-weight:600;font-size:1rem;letter-spacing:.5px;text-transform:uppercase;color:var(--text);margin-bottom:.3rem}
  .hero-card-text{font-size:.83rem;color:var(--text3);line-height:1.5}
  .hero-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1.5rem;margin-top:3.5rem;padding-top:2.5rem;border-top:1px solid var(--border)}
  .hero-stat-num{font-family:'Playfair Display',serif;font-size:2rem;color:var(--green-light);line-height:1}
  .hero-stat-label{font-size:.65rem;letter-spacing:2.5px;text-transform:uppercase;color:var(--text3);margin-top:.3rem;font-family:'Barlow Condensed',sans-serif;font-weight:600}

  /* Trust band */
  .trust-band{background:var(--green2);padding:1.2rem 2.5rem;display:flex;align-items:center;justify-content:center;gap:3rem;flex-wrap:wrap}
  .trust-item{display:flex;align-items:center;gap:.6rem;font-size:.82rem;color:rgba(255,255,255,.9);font-weight:500;letter-spacing:.3px}

  /* Section */
  .section{max-width:1200px;margin:0 auto;padding:4rem 2.5rem}
  .section-header{margin-bottom:3rem;text-align:center}
  .section-label{font-family:'Barlow Condensed',sans-serif;font-size:.68rem;letter-spacing:5px;text-transform:uppercase;color:var(--gold);margin-bottom:.6rem;display:block}
  .section-title{font-family:'Playfair Display',serif;font-size:2.4rem;color:var(--text);margin-bottom:.8rem}
  .section-sub{font-size:1rem;color:var(--text2);font-weight:300;max-width:560px;margin:0 auto;line-height:1.7}
  .section-header-row{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:2rem;border-bottom:1px solid var(--border);padding-bottom:1.2rem;gap:1rem;flex-wrap:wrap}
  .section-count{font-family:'Barlow Condensed',sans-serif;font-size:.7rem;letter-spacing:2px;color:var(--text3);text-transform:uppercase}

  /* Catalog controls */
  .catalog-controls{display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin-bottom:2rem}
  .search-box{flex:1;min-width:200px;max-width:380px;position:relative}
  .search-box input{width:100%;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:.65rem 1rem .65rem 2.6rem;border-radius:8px;font-family:'Barlow',sans-serif;font-size:.9rem;transition:border-color var(--tr),box-shadow var(--tr)}
  .search-box input:focus{outline:none;border-color:var(--green3);box-shadow:0 0 0 3px rgba(56,142,60,.1)}
  .search-box::before{content:'🔍';position:absolute;left:.85rem;top:50%;transform:translateY(-50%);font-size:.85rem;pointer-events:none}
  .filter-select{background:var(--surface);border:1px solid var(--border);color:var(--text2);padding:.65rem 1rem;border-radius:8px;font-family:'Barlow',sans-serif;font-size:.88rem;cursor:pointer;transition:border-color var(--tr)}
  .filter-select:focus{outline:none;border-color:var(--green3)}
  .results-info{font-size:.78rem;color:var(--text3);font-family:'Barlow Condensed',sans-serif;letter-spacing:1px;text-transform:uppercase;white-space:nowrap}

  /* Product grid */
  .product-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1.5rem}
  .product-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;transition:all var(--tr);box-shadow:var(--cshadow);display:flex;flex-direction:column}
  .product-card:hover{box-shadow:var(--chshadow);border-color:var(--border-accent);transform:translateY(-3px)}
  .card-media{position:relative;height:220px;background:var(--bg3);overflow:hidden;cursor:pointer}
  .card-media img{width:100%;height:100%;object-fit:cover;transition:transform .6s cubic-bezier(.4,0,.2,1)}
  .product-card:hover .card-media img{transform:scale(1.04)}
  .card-media-placeholder{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:3.5rem;color:var(--text3)}
  .card-img-count{position:absolute;bottom:8px;right:8px;background:rgba(0,0,0,.65);color:#fff;font-family:'Barlow Condensed',sans-serif;font-size:.62rem;letter-spacing:1px;padding:.15rem .5rem;border-radius:4px;backdrop-filter:blur(4px)}
  .card-category-badge{position:absolute;top:12px;left:12px;background:rgba(46,125,50,.92);color:#fff;font-family:'Barlow Condensed',sans-serif;font-size:.6rem;letter-spacing:2px;text-transform:uppercase;padding:.2rem .6rem;border-radius:4px;font-weight:700}
  .card-body{padding:1.4rem;flex:1;display:flex;flex-direction:column}
  .card-title{font-family:'Playfair Display',serif;font-size:1.18rem;color:var(--text);margin-bottom:.5rem;line-height:1.3}
  .card-desc{font-size:.86rem;color:var(--text2);line-height:1.7;margin-bottom:1.2rem;flex:1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
  .card-footer{display:flex;gap:.6rem}

  /* Pagination */
  .pagination{display:flex;align-items:center;justify-content:center;gap:.4rem;margin-top:3rem;flex-wrap:wrap}
  .page-btn{width:38px;height:38px;display:flex;align-items:center;justify-content:center;border-radius:8px;border:1.5px solid var(--border);background:transparent;color:var(--text2);font-family:'Barlow Condensed',sans-serif;font-size:.88rem;cursor:pointer;transition:all var(--tr)}
  .page-btn:hover{border-color:var(--green3);color:var(--green-light)}
  .page-btn.active{background:var(--green2);border-color:var(--green2);color:#fff;font-weight:700}
  .page-btn.disabled{opacity:.35;cursor:not-allowed;pointer-events:none}
  .page-ellipsis{color:var(--text3);font-size:.8rem;padding:0 .3rem}

  /* Lightbox */
  .lightbox{display:none;position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.93);align-items:center;justify-content:center;flex-direction:column}
  .lightbox.open{display:flex}
  .lightbox-img{max-width:90vw;max-height:76vh;object-fit:contain;border-radius:8px}
  .lightbox-controls{display:flex;gap:1rem;margin-top:1.2rem;align-items:center}
  .lightbox-close{position:absolute;top:1.5rem;right:1.5rem;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);width:36px;height:36px;border-radius:50%;color:#fff;font-size:1.1rem;cursor:pointer;display:flex;align-items:center;justify-content:center}
  .lightbox-nav{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);width:44px;height:44px;border-radius:50%;color:#fff;font-size:1.2rem;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s}
  .lightbox-nav:hover{background:rgba(46,125,50,.5)}
  .lightbox-counter{color:rgba(255,255,255,.6);font-family:'Barlow Condensed',sans-serif;font-size:.85rem;letter-spacing:2px}
  .lightbox-thumbs{display:flex;gap:.5rem;margin-top:.8rem;flex-wrap:wrap;justify-content:center;max-width:520px}
  .lightbox-thumb{width:52px;height:42px;object-fit:cover;border-radius:5px;cursor:pointer;border:2px solid transparent;opacity:.6;transition:all .2s}
  .lightbox-thumb.active{border-color:var(--gold);opacity:1}

  /* Detail */
  .detail-layout{display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:start}
  .detail-gallery{display:flex;flex-direction:column;gap:.8rem}
  .detail-main-img{border-radius:12px;overflow:hidden;background:var(--bg3);aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;border:1px solid var(--border);cursor:pointer}
  .detail-main-img img{width:100%;height:100%;object-fit:cover;transition:transform .5s}
  .detail-main-img:hover img{transform:scale(1.03)}
  .detail-thumbs{display:flex;gap:.6rem;flex-wrap:wrap}
  .detail-thumb{width:72px;height:58px;border-radius:7px;object-fit:cover;border:2px solid var(--border);cursor:pointer;transition:all .2s;opacity:.7}
  .detail-thumb:hover,.detail-thumb.active{border-color:var(--green3);opacity:1}
  .detail-img-placeholder{font-size:6rem;color:var(--text3)}
  .detail-eyebrow{font-family:'Barlow Condensed',sans-serif;font-size:.65rem;letter-spacing:4px;text-transform:uppercase;color:var(--green-light);margin-bottom:.8rem;display:flex;align-items:center;gap:.8rem}
  .detail-eyebrow::before{content:'';width:24px;height:2px;background:var(--green3)}
  .detail-title{font-family:'Playfair Display',serif;font-size:2.4rem;line-height:1.1;color:var(--text);margin-bottom:1rem}
  .detail-desc{font-size:1rem;color:var(--text2);line-height:1.8;margin-bottom:2rem}
  .specs-box{background:var(--bg2);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:2rem}
  .specs-box-title{font-family:'Barlow Condensed',sans-serif;font-size:.65rem;letter-spacing:3px;text-transform:uppercase;color:var(--text3);padding:.85rem 1.2rem;border-bottom:1px solid var(--border);background:var(--bg3);font-weight:600}
  .specs-box table{width:100%}
  .specs-box td{padding:.72rem 1.2rem;font-size:.87rem;border-bottom:1px solid var(--border)}
  .specs-box tr:last-child td{border-bottom:none}
  .specs-box td:first-child{color:var(--text3);font-weight:500;width:44%}
  .detail-actions{display:flex;gap:1rem;flex-wrap:wrap}
  .tag{display:inline-block;background:var(--bg3);color:var(--text2);border:1px solid var(--border);font-size:.7rem;padding:.18rem .55rem;border-radius:100px}
  .tag.green{background:rgba(46,125,50,.1);border-color:rgba(46,125,50,.3);color:var(--green-light)}
  .tag.gold{background:rgba(212,160,23,.1);border-color:rgba(212,160,23,.3);color:var(--gold)}

  /* About / Page Hero */
  .page-hero{padding:120px 2.5rem 70px;background:var(--bg);position:relative;overflow:hidden;margin-top:72px;border-bottom:1px solid var(--border)}
  .page-hero-inner{max-width:800px;margin:0 auto;text-align:center;position:relative}
  .page-hero-eyebrow{font-family:'Barlow Condensed',sans-serif;font-size:.68rem;letter-spacing:5px;text-transform:uppercase;color:var(--gold);margin-bottom:1rem;display:flex;align-items:center;justify-content:center;gap:.8rem}
  .page-hero-eyebrow::before,.page-hero-eyebrow::after{content:'';width:36px;height:1px;background:var(--gold)}
  .page-hero-title{font-family:'Playfair Display',serif;font-size:clamp(2.4rem,5vw,3.6rem);color:var(--text);margin-bottom:1rem;line-height:1.1}
  .page-hero-sub{font-size:1.05rem;color:var(--text2);line-height:1.75;font-weight:300}

  /* Cards for About */
  .card-grid-2{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
  .card-grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem}
  .card-grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem}
  .info-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:2rem;transition:all var(--tr)}
  .info-card:hover{border-color:var(--border-accent);transform:translateY(-2px);box-shadow:var(--chshadow)}
  .info-card-icon{font-size:2.2rem;margin-bottom:1rem}
  .info-card-title{font-family:'Barlow Condensed',sans-serif;font-size:1.05rem;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--text);margin-bottom:.6rem}
  .info-card-text{font-size:.87rem;color:var(--text2);line-height:1.7}
  .highlight-box{background:linear-gradient(135deg,rgba(46,125,50,.08),rgba(212,160,23,.05));border:1px solid rgba(46,125,50,.2);border-radius:16px;padding:3rem;position:relative;overflow:hidden}
  .highlight-box::before{content:'';position:absolute;top:-40px;right:-40px;width:200px;height:200px;background:radial-gradient(circle,rgba(46,125,50,.12),transparent 70%)}

  /* Products page */
  .products-list-item{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.4rem 1.6rem;display:flex;align-items:flex-start;gap:1.2rem;transition:all var(--tr)}
  .products-list-item:hover{border-color:var(--border-accent);transform:translateX(4px)}
  .products-list-icon{width:52px;height:52px;background:rgba(46,125,50,.1);border:1px solid rgba(46,125,50,.2);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;flex-shrink:0}
  .products-list-title{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:1.05rem;letter-spacing:.5px;text-transform:uppercase;color:var(--text);margin-bottom:.3rem}
  .products-list-text{font-size:.84rem;color:var(--text2);line-height:1.6}

  /* Contact */
  .contact-grid{display:grid;grid-template-columns:1fr 1.4fr;gap:3rem;align-items:start}
  .contact-info-item{display:flex;align-items:flex-start;gap:1rem;margin-bottom:1.5rem;padding-bottom:1.5rem;border-bottom:1px solid var(--border)}
  .contact-info-item:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0}
  .contact-info-icon{width:44px;height:44px;background:rgba(46,125,50,.1);border:1px solid rgba(46,125,50,.2);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0}
  .contact-info-label{font-family:'Barlow Condensed',sans-serif;font-size:.62rem;letter-spacing:3px;text-transform:uppercase;color:var(--text3);font-weight:600;margin-bottom:.25rem}
  .contact-info-value{font-size:.95rem;color:var(--text);font-weight:500}
  .contact-form-card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:2.5rem}

  /* Footer */
  footer{background:var(--bg2);border-top:1px solid var(--border);padding:4rem 2.5rem 2rem}
  .footer-inner{max-width:1200px;margin:0 auto;display:grid;grid-template-columns:1.8fr 1fr 1fr 1.5fr;gap:3rem;margin-bottom:3rem;flex-wrap:wrap}
  .footer-brand-name{font-family:'Barlow Condensed',sans-serif;font-size:1.3rem;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--text);margin-bottom:.3rem}
  .footer-brand-sub{font-size:.7rem;letter-spacing:2px;color:var(--gold);text-transform:uppercase;font-weight:600}
  .footer-brand-desc{font-size:.83rem;color:var(--text3);line-height:1.65;margin-top:.8rem}
  .footer-heading{font-family:'Barlow Condensed',sans-serif;font-size:.65rem;letter-spacing:3px;text-transform:uppercase;color:var(--text3);margin-bottom:1rem;font-weight:600}
  .footer-link{display:block;font-size:.84rem;color:var(--text3);margin-bottom:.5rem;transition:color var(--tr)}
  .footer-link:hover{color:var(--green-light)}
  .footer-bottom{max-width:1200px;margin:0 auto;border-top:1px solid var(--border);padding-top:1.5rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem}
  .footer-copy{font-size:.78rem;color:var(--text3)}

  /* Admin */
  .admin-layout{display:grid;grid-template-columns:240px 1fr;min-height:calc(100vh - 72px);margin-top:72px}
  .sidebar{background:var(--surface);border-right:1px solid var(--border);padding:1.5rem 0;position:sticky;top:72px;height:calc(100vh - 72px);overflow-y:auto}
  .sidebar-label{font-family:'Barlow Condensed',sans-serif;font-size:.57rem;letter-spacing:3px;text-transform:uppercase;color:var(--text3);padding:.4rem 1.2rem;margin-bottom:.2rem;font-weight:600}
  .sidebar-link{display:flex;align-items:center;gap:.7rem;padding:.7rem 1.2rem;margin:.1rem .6rem;border-radius:8px;color:var(--text2);font-size:.88rem;font-weight:500;transition:all var(--tr)}
  .sidebar-link:hover{background:var(--bg3);color:var(--text)}
  .sidebar-link.active{background:rgba(46,125,50,.12);color:var(--green-light)}
  .main-content{padding:2.5rem}
  .page-title{font-family:'Playfair Display',serif;font-size:2rem;color:var(--text);margin-bottom:.3rem}
  .page-subtitle{font-size:.84rem;color:var(--text3);margin-bottom:2rem}
  .stat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:1rem;margin-bottom:2rem}
  .stat-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.3rem;transition:border-color var(--tr)}
  .stat-card:hover{border-color:var(--border-accent)}
  .stat-num{font-family:'Playfair Display',serif;font-size:2.6rem;color:var(--green-light);line-height:1;margin-bottom:.3rem}
  .stat-label{font-family:'Barlow Condensed',sans-serif;font-size:.6rem;letter-spacing:2px;text-transform:uppercase;color:var(--text3);font-weight:600}

  /* Filter pills */
  .filter-bar{display:flex;align-items:center;gap:.5rem;margin-bottom:1.5rem;flex-wrap:wrap}
  .filter-pill{padding:.38rem 1.1rem;border-radius:100px;border:1.5px solid var(--border);background:transparent;color:var(--text2);font-family:'Barlow',sans-serif;font-size:.8rem;font-weight:500;cursor:pointer;transition:all var(--tr);text-decoration:none}
  .filter-pill:hover{border-color:var(--green3);color:var(--green-light)}
  .filter-pill.active{background:var(--green2);border-color:var(--green2);color:#fff;font-weight:600}

  /* Bar chart */
  .bar-chart{display:flex;align-items:flex-end;gap:4px;height:160px;padding:.5rem 0}
  .bar-wrap{flex:1;display:flex;flex-direction:column;align-items:center;gap:.3rem;min-width:20px}
  .bar{width:100%;background:rgba(46,125,50,.22);border-radius:4px 4px 0 0;transition:height .6s cubic-bezier(.4,0,.2,1);min-height:2px}
  .bar:hover{background:rgba(46,125,50,.6)}
  .bar-label{font-family:'Barlow Condensed',sans-serif;font-size:.52rem;color:var(--text3);text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
  .bar-val{font-size:.62rem;color:var(--text3)}

  /* Tables */
  .table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden}
  table{width:100%;border-collapse:collapse}
  th{font-family:'Barlow Condensed',sans-serif;font-size:.6rem;letter-spacing:2px;text-transform:uppercase;color:var(--text3);padding:.85rem 1.2rem;background:var(--bg3);font-weight:600;text-align:left;border-bottom:1px solid var(--border)}
  td{padding:.85rem 1.2rem;border-bottom:1px solid var(--border);font-size:.88rem;vertical-align:middle}
  tr:last-child td{border-bottom:none}
  tr:hover td{background:rgba(46,125,50,.03)}

  /* Forms */
  .form-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:2rem}
  .form-group{margin-bottom:1.2rem}
  .form-label{display:block;font-family:'Barlow Condensed',sans-serif;font-size:.62rem;letter-spacing:2px;text-transform:uppercase;color:var(--text3);margin-bottom:.5rem;font-weight:600}
  .form-control{width:100%;background:var(--bg2);border:1px solid var(--border);color:var(--text);padding:.72rem 1rem;border-radius:8px;font-family:'Barlow',sans-serif;font-size:.9rem;transition:border-color var(--tr),box-shadow var(--tr)}
  .form-control:focus{outline:none;border-color:var(--green3);box-shadow:0 0 0 3px rgba(56,142,60,.1)}
  textarea.form-control{resize:vertical;min-height:110px}

  /* Multi-image upload */
  .upload-zone{border:2px dashed var(--border);border-radius:10px;padding:2rem;text-align:center;cursor:pointer;transition:all var(--tr);position:relative}
  .upload-zone:hover,.upload-zone.dragover{border-color:var(--green3);background:rgba(46,125,50,.04)}
  .upload-zone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
  .upload-zone-icon{font-size:2rem;margin-bottom:.5rem}
  .upload-zone-text{font-weight:600;font-size:.9rem;color:var(--text2);margin-bottom:.2rem}
  .upload-zone-sub{font-size:.73rem;color:var(--text3)}
  .image-preview-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:.6rem;margin-top:1rem}
  .img-preview-item{position:relative;aspect-ratio:1;border-radius:8px;overflow:hidden;border:2px solid var(--border)}
  .img-preview-item img{width:100%;height:100%;object-fit:cover}
  .img-preview-item .primary-badge{position:absolute;bottom:3px;left:3px;background:rgba(46,125,50,.9);color:#fff;font-size:.48rem;font-family:'Barlow Condensed',sans-serif;padding:.1rem .3rem;border-radius:3px;font-weight:700;letter-spacing:1px}

  /* Existing images */
  .existing-imgs{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:.6rem;margin-bottom:.8rem}
  .existing-img-item{position:relative;aspect-ratio:1;border-radius:8px;overflow:hidden;border:2px solid var(--border)}
  .existing-img-item img{width:100%;height:100%;object-fit:cover}
  .existing-img-item .del-img-btn{position:absolute;top:3px;right:3px;width:20px;height:20px;background:rgba(192,57,43,.85);border:none;border-radius:50%;color:#fff;font-size:.65rem;cursor:pointer;display:flex;align-items:center;justify-content:center;text-decoration:none;line-height:1}
  .existing-img-item .primary-label{position:absolute;bottom:3px;left:3px;background:rgba(46,125,50,.9);color:#fff;font-size:.46rem;font-family:'Barlow Condensed',sans-serif;padding:.1rem .3rem;border-radius:3px;font-weight:700;letter-spacing:1px}

  /* Alert / Modal */
  .alert{padding:.9rem 1.2rem;border-radius:8px;margin-bottom:1.2rem;font-size:.88rem;border:1px solid;display:flex;align-items:center;gap:.6rem}
  .alert.success{background:rgba(39,174,96,.08);border-color:rgba(39,174,96,.3);color:#2ecc71}
  .alert.error{background:rgba(192,57,43,.08);border-color:rgba(192,57,43,.3);color:#e74c3c}
  .modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.72);backdrop-filter:blur(4px);z-index:500;align-items:center;justify-content:center;padding:1.5rem}
  .modal-overlay.open{display:flex}
  .modal{background:var(--surface);border:1px solid var(--border);border-radius:14px;width:100%;max-width:600px;padding:2rem;position:relative;max-height:90vh;overflow-y:auto;animation:modalIn .25s cubic-bezier(.34,1.56,.64,1)}
  @keyframes modalIn{from{opacity:0;transform:scale(.93) translateY(16px)}to{opacity:1;transform:scale(1) translateY(0)}}
  .modal-close{position:absolute;top:1rem;right:1rem;background:var(--bg3);border:1px solid var(--border);width:30px;height:30px;border-radius:50%;color:var(--text2);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:.9rem;transition:all var(--tr)}
  .modal-close:hover{background:var(--danger);border-color:var(--danger);color:#fff}
  .modal-title{font-family:'Playfair Display',serif;font-size:1.55rem;margin-bottom:1.5rem;color:var(--text)}

  /* Login */
  .login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);padding:2rem}
  .login-box{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:2.5rem;width:100%;max-width:400px;box-shadow:var(--cshadow)}

  /* Misc */
  .breadcrumb{display:flex;align-items:center;gap:.5rem;font-size:.8rem;color:var(--text3);margin-bottom:2rem}
  .breadcrumb a{color:var(--text2);transition:color var(--tr)}
  .breadcrumb a:hover{color:var(--green-light)}
  .empty-state{text-align:center;padding:5rem 2rem;color:var(--text3)}
  .empty-state-icon{font-size:4rem;margin-bottom:1rem;opacity:.5}
  .empty-state h3{font-family:'Playfair Display',serif;font-size:1.5rem;color:var(--text2);margin-bottom:.5rem}
  .divider{border:none;border-top:1px solid var(--border)}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}

  /* Brands strip */
  .brands-strip{background:var(--bg3);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:1.8rem 2.5rem;overflow:hidden}
  .brands-inner{max-width:1200px;margin:0 auto}
  .brands-label{font-family:'Barlow Condensed',sans-serif;font-size:.6rem;letter-spacing:4px;text-transform:uppercase;color:var(--text3);text-align:center;margin-bottom:1.2rem;font-weight:600}
  .brands-list{display:flex;gap:2.5rem;align-items:center;flex-wrap:wrap;justify-content:center}
  .brand-pill{font-family:'Barlow Condensed',sans-serif;font-size:.88rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--text3);padding:.4rem .9rem;border:1px solid var(--border);border-radius:6px;transition:all var(--tr)}
  .brand-pill:hover{border-color:var(--green3);color:var(--green-light)}

  @media(max-width:1024px){
    .footer-inner{grid-template-columns:1fr 1fr}
    .hero-inner{grid-template-columns:1fr}
    .hero-right{display:none}
  }
  @media(max-width:900px){
    .detail-layout,.card-grid-2,.card-grid-3,.card-grid-4,.contact-grid,.grid-2{grid-template-columns:1fr}
    .admin-layout{grid-template-columns:1fr}
    .sidebar{display:none}
    .page-hero{padding:100px 1.5rem 60px}
    .nav-links{display:none}
  }
  @media(max-width:640px){
    .section{padding:2.5rem 1.2rem}
    .navbar{padding:0 1.2rem}
    .trust-band{gap:1.2rem;padding:1rem}
  }
</style>
"""

THEME_SCRIPT = """
<script>
(function(){
  const t=localStorage.getItem('theme')||'dark';
  document.documentElement.setAttribute('data-theme',t);
})();
function toggleTheme(){
  const c=document.documentElement.getAttribute('data-theme');
  const n=c==='dark'?'light':'dark';
  document.documentElement.setAttribute('data-theme',n);
  localStorage.setItem('theme',n);
}
</script>
"""

WA_SVG = '<svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.126.554 4.126 1.527 5.865L.057 23.863a.75.75 0 0 0 .92.92l6.01-1.472A11.955 11.955 0 0 0 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.75a9.73 9.73 0 0 1-4.964-1.359l-.357-.213-3.7.906.924-3.594-.233-.37A9.731 9.731 0 0 1 2.25 12C2.25 6.615 6.615 2.25 12 2.25S21.75 6.615 21.75 12 17.385 21.75 12 21.75z"/></svg>'

def wa_num(): return CONTACT_WHATSAPP.replace('+','').replace(' ','')

NAWA_LOGO = """<div style="width:44px;height:44px;background:linear-gradient(135deg,#2E7D32,#4CAF50);border-radius:8px;display:flex;align-items:center;justify-content:center;overflow:hidden">
  <svg width="30" height="26" viewBox="0 0 30 26" fill="none">
    <path d="M2 20 L10 6 L15 14 L20 6 L28 20" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
    <path d="M10 20 L15 12 L20 20" stroke="rgba(255,255,255,0.6)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  </svg>
</div>"""

def navbar_public(active="home"):
    links = [("home", "/", "Home"), ("about", "/about", "About Us"), ("services", "/services", "Products & Services"), ("contact", "/contact", "Contact")]
    nav_items = "".join(f'<a href="{href}" class="nav-link{"  active" if k==active else ""}">{lbl}</a>' for k, href, lbl in links)
    return f"""<nav class="navbar">
      <a href="/" class="brand">
        {NAWA_LOGO}
        <div class="brand-text">
          <span class="brand-name">NAWA Global</span>
          <span class="brand-sub">General Trading</span>
        </div>
      </a>
      <div class="nav-links">{nav_items}</div>
      <div class="nav-right">
        <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme"></button>
        <a href="https://wa.me/{wa_num()}" target="_blank" class="btn outline-green sm">{WA_SVG} WhatsApp</a>
        <a href="/catalog" class="btn primary sm">View Catalog</a>
      </div>
    </nav>"""

def navbar_admin():
    return f"""<nav class="navbar">
      <a href="/" class="brand">
        {NAWA_LOGO}
        <div class="brand-text">
          <span class="brand-name">NAWA Global</span>
          <span style="display:inline-block;font-size:.5rem;background:rgba(46,125,50,.15);border:1px solid rgba(46,125,50,.3);color:var(--green-light);padding:.1rem .5rem;border-radius:4px;font-family:'Barlow Condensed',sans-serif;letter-spacing:2px;text-transform:uppercase">ADMIN</span>
        </div>
      </a>
      <div class="nav-right">
        <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme"></button>
        <a href="{ADMIN_ROUTE}/dashboard" class="btn sm">Dashboard</a>
        <a href="{ADMIN_ROUTE}/logout" class="btn sm danger">Sign Out</a>
      </div>
    </nav>"""

def admin_sidebar(active="dashboard"):
    links = [
        ("dashboard", f"{ADMIN_ROUTE}/dashboard", "📊", "Dashboard"),
        ("products",  f"{ADMIN_ROUTE}/products",  "📦", "Products"),
        ("visitors",  f"{ADMIN_ROUTE}/visitors",  "👥", "Visitors"),
    ]
    items = "".join(
        f'<a href="{href}" class="sidebar-link{" active" if k==active else ""}">{icon}&nbsp; {lbl}</a>'
        for k, href, icon, lbl in links
    )
    return f"""<aside class="sidebar">
      <div style="padding:0 .6rem">
        <div class="sidebar-label">Navigation</div>
        {items}
      </div>
      <div style="position:absolute;bottom:1.5rem;left:0;right:0;padding:0 .6rem">
        <a href="/" class="sidebar-link" style="font-size:.8rem">🔗&nbsp; View Live Site</a>
      </div>
    </aside>"""

def footer_html():
    return f"""<footer>
      <div class="footer-inner">
        <div>
          <div style="display:flex;align-items:center;gap:.7rem;margin-bottom:.6rem">
            {NAWA_LOGO}
            <div>
              <div class="footer-brand-name">NAWA Global</div>
              <div class="footer-brand-sub">General Trading</div>
            </div>
          </div>
          <div class="footer-brand-desc">Premium oilfield &amp; industrial supply partner based in Abu Dhabi, UAE. Trusted by oil &amp; gas, construction, and facility management sectors.</div>
          <div style="margin-top:1.2rem">
            <a href="https://wa.me/{wa_num()}" target="_blank" class="wa-btn" style="font-size:.8rem;padding:.5rem 1rem">{WA_SVG} Chat on WhatsApp</a>
          </div>
        </div>
        <div>
          <div class="footer-heading">Quick Links</div>
          <a href="/" class="footer-link">Home</a>
          <a href="/about" class="footer-link">About Us</a>
          <a href="/services" class="footer-link">Products &amp; Services</a>
          <a href="/catalog" class="footer-link">Product Catalog</a>
          <a href="/contact" class="footer-link">Contact Us</a>
        </div>
        <div>
          <div class="footer-heading">Services</div>
          <a href="/services" class="footer-link">Oilfield Equipment</a>
          <a href="/services" class="footer-link">Industrial Supplies</a>
          <a href="/services" class="footer-link">Lubricants &amp; Oils</a>
          <a href="/services" class="footer-link">Safety Products</a>
          <a href="/services" class="footer-link">Procurement Services</a>
        </div>
        <div>
          <div class="footer-heading">Contact Info</div>
          <div style="font-size:.84rem;color:var(--text3);margin-bottom:.7rem;display:flex;gap:.6rem;align-items:flex-start">📍 <span>{CONTACT_ADDRESS}</span></div>
          <div style="font-size:.84rem;color:var(--text3);margin-bottom:.7rem">📞 <a href="tel:{CONTACT_WHATSAPP}" style="color:var(--green-light)">{CONTACT_WHATSAPP}</a></div>
          <div style="font-size:.84rem;color:var(--text3);margin-bottom:.7rem">📧 <a href="mailto:{CONTACT_EMAIL}" style="color:var(--green-light)">{CONTACT_EMAIL}</a></div>
          <div style="font-size:.84rem;color:var(--text3)">🌐 <a href="https://{CONTACT_WEBSITE}" target="_blank" style="color:var(--green-light)">{CONTACT_WEBSITE}</a></div>
        </div>
      </div>
      <div class="footer-bottom">
        <div class="footer-copy">© 2026 NAWA Global General Trading. All Rights Reserved.</div>
        <div style="font-size:.76rem;color:var(--text3)">Mussafah, Abu Dhabi, UAE</div>
      </div>
    </footer>"""

BRANDS_STRIP = """<div class="brands-strip">
  <div class="brands-inner">
    <div class="brands-label">Authorized Brands & Partners</div>
    <div class="brands-list">
      <span class="brand-pill">Molyslip</span>
      <span class="brand-pill">Arrow</span>
      <span class="brand-pill">Unispec</span>
      <span class="brand-pill">Lubriplate</span>
      <span class="brand-pill">Jet-Lube</span>
      <span class="brand-pill">Ketch-All</span>
      <span class="brand-pill">Beta</span>
      <span class="brand-pill">JOST</span>
      <span class="brand-pill">3M</span>
      <span class="brand-pill">Ansell</span>
      <span class="brand-pill">Fortwest</span>
      <span class="brand-pill">Deltaplus</span>
      <span class="brand-pill">CAT</span>
      <span class="brand-pill">Mitutoyo</span>
    </div>
  </div>
</div>"""

def make_pagination(page: int, total_pages: int, base_url: str) -> str:
    if total_pages <= 1: return ""
    parts = []
    prev_cls = "page-btn" if page > 1 else "page-btn disabled"
    parts.append(f'<a class="{prev_cls}" href="{base_url}&page={page-1}">&#8249;</a>' if page > 1 else f'<span class="{prev_cls}">&#8249;</span>')
    show = set([1, total_pages] + list(range(max(1,page-2), min(total_pages+1,page+3))))
    prev = None
    for p in sorted(show):
        if prev and p - prev > 1:
            parts.append('<span class="page-ellipsis">…</span>')
        cls = "page-btn active" if p == page else "page-btn"
        parts.append(f'<a class="{cls}" href="{base_url}&page={p}">{p}</a>')
        prev = p
    parts.append(f'<a class="page-btn" href="{base_url}&page={page+1}">&#8250;</a>' if page < total_pages else '<span class="page-btn disabled">&#8250;</span>')
    return f'<div class="pagination">{"".join(parts)}</div>'

def get_product_images(p: dict) -> list:
    images = list(p.get("images") or [])
    legacy = p.get("image")
    if legacy and legacy not in images:
        images = [legacy] + images
    return images

# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    save_visit(request.client.host)
    all_products = load_products()
    all_cats = sorted(set(p.get("category","General") for p in all_products))
    recent = all_products[-6:][::-1]

    cards_html = ""
    for p in recent:
        imgs = get_product_images(p)
        if imgs:
            media = f'<img src="/uploads/{imgs[0]}" alt="{p["name"]}" loading="lazy">'
        else:
            media = '<div class="card-media-placeholder">📦</div>'
        wa_msg = f"Hello! I'm interested in: *{p['name']}*. Please send me details.".replace(' ','%20').replace('*','%2A')
        wa_link = f"https://wa.me/{wa_num()}?text={wa_msg}"
        cards_html += f"""<div class="product-card">
          <div class="card-media" onclick="location.href='/product/{p['id']}'">
            {media}
            <span class="card-category-badge">{p.get('category','General')}</span>
          </div>
          <div class="card-body">
            <div class="card-title">{p['name']}</div>
            <div class="card-desc">{p.get('description','No description available.')}</div>
            <div class="card-footer">
              <a href="/product/{p['id']}" class="btn sm primary" style="flex:1;justify-content:center">View Details</a>
              <a href="{wa_link}" target="_blank" class="btn sm outline-gold">Quote</a>
            </div>
          </div>
        </div>"""

    featured_section = f"""<div class="section" style="padding-top:0">
      <div class="section-header-row">
        <div>
          <span class="section-label">Featured Products</span>
          <div class="section-title" style="font-family:'Playfair Display',serif;font-size:2rem;color:var(--text)">Recently Added</div>
        </div>
        <a href="/catalog" class="btn outline-green">View Full Catalog →</a>
      </div>
      <div class="product-grid">{cards_html if cards_html else '<div class="empty-state"><div class="empty-state-icon">📦</div><h3>No products yet</h3><p>Products will appear here once added.</p></div>'}</div>
    </div>""" if recent else ""

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>NAWA Global General Trading — Premium Oilfield & Industrial Supply Partner</title>
<meta name="description" content="NAWA Global General Trading — reliable supplier of oilfield spare parts, industrial consumables, lubricants, and maintenance solutions based in Abu Dhabi, UAE."></head>
<body>
{navbar_public("home")}

<!-- Hero -->
<div class="hero">
  <div class="hero-bg-pattern"></div>
  <div class="hero-glow-green"></div>
  <div class="hero-glow-gold"></div>
  <div class="hero-inner">
    <div>
      <div class="hero-eyebrow">Abu Dhabi, UAE · Est. 2020</div>
      <h1 class="hero-title">Premium Oilfield &amp;<br><em>Industrial Supply</em><br>Partner</h1>
      <p class="hero-sub">Reliable sourcing of high-quality oilfield spare parts, industrial consumables, lubricants, safety products, and maintenance solutions — delivered with speed and competitive pricing.</p>
      <div class="hero-cta">
        <a href="/catalog" class="btn primary lg">Browse Catalog</a>
        <a href="https://wa.me/{wa_num()}" target="_blank" class="wa-btn">{WA_SVG} Request a Quote</a>
      </div>
      <div class="hero-stats">
        <div><div class="hero-stat-num">{len(all_products)}+</div><div class="hero-stat-label">Products</div></div>
        <div><div class="hero-stat-num">{len(all_cats)}+</div><div class="hero-stat-label">Categories</div></div>
        <div><div class="hero-stat-num">UAE</div><div class="hero-stat-label">Based In</div></div>
        <div><div class="hero-stat-num">14+</div><div class="hero-stat-label">Brands</div></div>
      </div>
    </div>
    <div class="hero-right">
      <div class="hero-card"><div class="hero-card-icon">🛢️</div><div class="hero-card-title">Oilfield Equipment</div><div class="hero-card-text">Spare parts, pipe fittings, valves, and field equipment for oil &amp; gas operations.</div></div>
      <div class="hero-card"><div class="hero-card-icon">🔧</div><div class="hero-card-title">Industrial Supplies</div><div class="hero-card-text">MRO supplies, consumables, hydraulic components, and mechanical parts.</div></div>
      <div class="hero-card"><div class="hero-card-icon">🛡️</div><div class="hero-card-title">Safety Products</div><div class="hero-card-text">PPE, hand protection, head &amp; eye protection, uniforms, and safety equipment.</div></div>
    </div>
  </div>
</div>

<!-- Trust band -->
<div class="trust-band">
  <div class="trust-item">🛢️ Oilfield Specialists</div>
  <div class="trust-item">🇦🇪 Abu Dhabi Based</div>
  <div class="trust-item">🌍 Global Sourcing</div>
  <div class="trust-item">⚡ Fast Delivery</div>
  <div class="trust-item">💰 Competitive Pricing</div>
  <div class="trust-item">💬 WhatsApp Support</div>
</div>

<!-- About snippet -->
<div class="section">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:center">
    <div>
      <span class="section-label">About NAWA Global</span>
      <h2 style="font-family:'Playfair Display',serif;font-size:2.2rem;color:var(--text);margin-bottom:1.2rem;line-height:1.2">A Trusted Partner for Industrial &amp; Oilfield Supply</h2>
      <p style="font-size:.97rem;color:var(--text2);line-height:1.8;margin-bottom:1.5rem">NAWA Global General Trading is a reliable supplier of high-quality oilfield spare parts, industrial consumables, lubricants, grease, degreasers, and maintenance solutions. We serve oil &amp; gas, industrial, construction, and facility management sectors with a commitment to quality, speed, and competitive pricing.</p>
      <div style="display:flex;gap:1rem;flex-wrap:wrap">
        <a href="/about" class="btn primary">Learn More About Us</a>
        <a href="/contact" class="btn outline-green">Get in Touch</a>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
      <div class="info-card"><div class="info-card-icon">🌐</div><div class="info-card-title">Global Network</div><div class="info-card-text">Strong global supplier network enabling competitive pricing.</div></div>
      <div class="info-card"><div class="info-card-icon">⚡</div><div class="info-card-title">Fast Response</div><div class="info-card-text">Quick turnaround and reliable delivery schedules.</div></div>
      <div class="info-card"><div class="info-card-icon">✅</div><div class="info-card-title">Quality Focused</div><div class="info-card-text">Compliance-driven approach with rigorous quality assurance.</div></div>
      <div class="info-card"><div class="info-card-icon">🤝</div><div class="info-card-title">Customer First</div><div class="info-card-text">Solution-oriented, dedicated to your operational success.</div></div>
    </div>
  </div>
</div>

<!-- Industries -->
<div style="background:var(--bg2);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:3rem 2.5rem">
  <div style="max-width:1200px;margin:0 auto">
    <div class="section-header" style="margin-bottom:2rem">
      <span class="section-label">Industries We Serve</span>
      <h2 class="section-title">Powering Multiple Sectors</h2>
    </div>
    <div class="card-grid-4">
      <div style="text-align:center;padding:1.5rem;background:var(--surface);border:1px solid var(--border);border-radius:12px;transition:all var(--tr)" onmouseover="this.style.borderColor='var(--border-accent)'" onmouseout="this.style.borderColor='var(--border)'">
        <div style="font-size:2.5rem;margin-bottom:.8rem">🛢️</div>
        <div style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:.95rem;letter-spacing:.5px;text-transform:uppercase;color:var(--text)">Oil &amp; Gas</div>
      </div>
      <div style="text-align:center;padding:1.5rem;background:var(--surface);border:1px solid var(--border);border-radius:12px;transition:all var(--tr)" onmouseover="this.style.borderColor='var(--border-accent)'" onmouseout="this.style.borderColor='var(--border)'">
        <div style="font-size:2.5rem;margin-bottom:.8rem">🏗️</div>
        <div style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:.95rem;letter-spacing:.5px;text-transform:uppercase;color:var(--text)">Construction</div>
      </div>
      <div style="text-align:center;padding:1.5rem;background:var(--surface);border:1px solid var(--border);border-radius:12px;transition:all var(--tr)" onmouseover="this.style.borderColor='var(--border-accent)'" onmouseout="this.style.borderColor='var(--border)'">
        <div style="font-size:2.5rem;margin-bottom:.8rem">🏭</div>
        <div style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:.95rem;letter-spacing:.5px;text-transform:uppercase;color:var(--text)">Industrial</div>
      </div>
      <div style="text-align:center;padding:1.5rem;background:var(--surface);border:1px solid var(--border);border-radius:12px;transition:all var(--tr)" onmouseover="this.style.borderColor='var(--border-accent)'" onmouseout="this.style.borderColor='var(--border)'">
        <div style="font-size:2.5rem;margin-bottom:.8rem">🏢</div>
        <div style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:.95rem;letter-spacing:.5px;text-transform:uppercase;color:var(--text)">Facility Mgmt</div>
      </div>
    </div>
  </div>
</div>

{featured_section}

{BRANDS_STRIP}

<!-- CTA -->
<div style="background:linear-gradient(135deg,var(--green2),var(--green3));padding:4rem 2.5rem;text-align:center">
  <div style="max-width:640px;margin:0 auto">
    <h2 style="font-family:'Playfair Display',serif;font-size:2.4rem;color:#fff;margin-bottom:1rem">Looking for Reliable Industrial Supply?</h2>
    <p style="font-size:1rem;color:rgba(255,255,255,.82);line-height:1.7;margin-bottom:2rem">Partner with NAWA Global for dependable sourcing, quality products, and timely delivery across the UAE and beyond.</p>
    <div style="display:flex;gap:1rem;justify-content:center;flex-wrap:wrap">
      <a href="https://wa.me/{wa_num()}" target="_blank" class="wa-btn">{WA_SVG} Request a Quote</a>
      <a href="/contact" class="btn" style="background:rgba(255,255,255,.15);border-color:rgba(255,255,255,.3);color:#fff">Contact Us →</a>
    </div>
  </div>
</div>

{footer_html()}
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: ABOUT PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    save_visit(request.client.host)
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>About Us — NAWA Global General Trading</title>
<meta name="description" content="About NAWA Global General Trading — trusted oilfield and industrial supply partner based in Abu Dhabi, UAE."></head>
<body>
{navbar_public("about")}

<div class="page-hero">
  <div class="page-hero-inner">
    <div class="page-hero-eyebrow">About NAWA Global</div>
    <h1 class="page-hero-title">Trusted Partner for<br><em style="color:var(--green-light)">Oilfield & Industrial</em><br>Solutions</h1>
    <p class="page-hero-sub">Based in Abu Dhabi, UAE — serving oil &amp; gas, industrial, construction, and facility management sectors with quality, speed, and competitive pricing.</p>
  </div>
</div>

<!-- About section -->
<div class="section">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:start">
    <div>
      <span class="section-label">Who We Are</span>
      <h2 style="font-family:'Playfair Display',serif;font-size:2rem;color:var(--text);margin-bottom:1.2rem;line-height:1.2">NAWA Global General Trading</h2>
      <p style="font-size:.97rem;color:var(--text2);line-height:1.8;margin-bottom:1rem">NAWA Global General Trading is a trusted supplier of premium oilfield and industrial products based in Abu Dhabi, UAE. We specialize in delivering high-quality spare parts, consumables, lubricants, and maintenance solutions tailored to meet the needs of various industries.</p>
      <p style="font-size:.97rem;color:var(--text2);line-height:1.8;margin-bottom:1.5rem">With a strong global supplier network and a commitment to excellence, we ensure reliable sourcing, competitive pricing, and timely delivery for every client. Our team understands the operational demands of the energy and industrial sectors, and we work closely with our clients to provide solutions that truly support their success.</p>
      <div style="display:flex;gap:1rem;flex-wrap:wrap">
        <a href="/contact" class="btn primary">Get in Touch</a>
        <a href="/services" class="btn outline-green">Our Services →</a>
      </div>
    </div>
    <div>
      <div class="highlight-box" style="margin-bottom:1.2rem">
        <div style="font-size:2rem;margin-bottom:.8rem">🎯</div>
        <div style="font-family:'Playfair Display',serif;font-size:1.3rem;color:var(--text);margin-bottom:.6rem">Our Vision</div>
        <p style="font-size:.92rem;color:var(--text2);line-height:1.75">To be a trusted trading partner delivering reliable industrial and oilfield solutions with excellence — building long-term partnerships based on integrity and performance.</p>
      </div>
      <div class="highlight-box">
        <div style="font-size:2rem;margin-bottom:.8rem">🚀</div>
        <div style="font-family:'Playfair Display',serif;font-size:1.3rem;color:var(--text);margin-bottom:.6rem">Our Mission</div>
        <p style="font-size:.92rem;color:var(--text2);line-height:1.75">To provide high-quality products, timely delivery, and value-driven services that support our clients' operational success across multiple industries.</p>
      </div>
    </div>
  </div>
</div>

<!-- What we do -->
<div style="background:var(--bg2);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:4rem 2.5rem">
  <div style="max-width:1200px;margin:0 auto">
    <div class="section-header">
      <span class="section-label">What We Do</span>
      <h2 class="section-title">Comprehensive Supply Solutions</h2>
      <p class="section-sub">We provide a wide range of products and services to simplify procurement and deliver reliable solutions that meet operational demands.</p>
    </div>
    <div class="card-grid-3">
      <div class="info-card"><div class="info-card-icon">🛢️</div><div class="info-card-title">Oilfield Equipment</div><div class="info-card-text">High-quality oilfield spare parts, pipe fittings, valves, pressure gauges, and specialized field equipment.</div></div>
      <div class="info-card"><div class="info-card-icon">🔧</div><div class="info-card-title">Industrial Supplies</div><div class="info-card-text">MRO supplies, consumables, hydraulic &amp; mechanical components, fasteners, and maintenance products.</div></div>
      <div class="info-card"><div class="info-card-icon">💧</div><div class="info-card-title">Lubricants &amp; Grease</div><div class="info-card-text">Industrial and automotive lubricants, specialty oils, grease, degreasers, and cleaning chemicals.</div></div>
      <div class="info-card"><div class="info-card-icon">🛡️</div><div class="info-card-title">Safety Products</div><div class="info-card-text">Full PPE range — hand, head, eye, ear and face protection, uniforms, workwear, harnesses, and LOTO equipment.</div></div>
      <div class="info-card"><div class="info-card-icon">🌱</div><div class="info-card-title">Environmental</div><div class="info-card-text">Degreasers, cleaning chemicals, underground drainage, sewage products, and environmental compliance solutions.</div></div>
      <div class="info-card"><div class="info-card-icon">🔍</div><div class="info-card-title">Custom Sourcing</div><div class="info-card-text">Customized procurement services leveraging our global supplier network to find specific products you need.</div></div>
    </div>
  </div>
</div>

<!-- Our Strengths -->
<div class="section">
  <div class="section-header">
    <span class="section-label">Our Strengths</span>
    <h2 class="section-title">Why Choose NAWA Global?</h2>
  </div>
  <div class="card-grid-2">
    <div style="display:flex;flex-direction:column;gap:1rem">
      {''.join(f'<div style="display:flex;align-items:flex-start;gap:1rem;padding:1.2rem;background:var(--surface);border:1px solid var(--border);border-radius:10px"><div style="width:36px;height:36px;background:rgba(46,125,50,.1);border:1px solid rgba(46,125,50,.2);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0">{icon}</div><div><div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:700;font-size:.95rem;letter-spacing:.5px;text-transform:uppercase;color:var(--text);margin-bottom:.3rem">{title}</div><div style="font-size:.84rem;color:var(--text2);line-height:1.6">{desc}</div></div></div>'
        for icon, title, desc in [
          ("🌐", "Global Sourcing Capabilities", "Access to a strong international supplier network for competitive pricing and rare items."),
          ("⚡", "Fast Turnaround Time", "Quick response to inquiries and efficient order processing to meet tight deadlines."),
          ("💰", "Competitive Pricing", "Cost optimization strategies that deliver real value without compromising quality."),
          ("🚚", "Reliable Logistics", "Dependable delivery schedules with careful logistics planning and tracking."),
        ])}
    </div>
    <div style="display:flex;flex-direction:column;gap:1rem">
      {''.join(f'<div style="display:flex;align-items:flex-start;gap:1rem;padding:1.2rem;background:var(--surface);border:1px solid var(--border);border-radius:10px"><div style="width:36px;height:36px;background:rgba(46,125,50,.1);border:1px solid rgba(46,125,50,.2);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0">{icon}</div><div><div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:700;font-size:.95rem;letter-spacing:.5px;text-transform:uppercase;color:var(--text);margin-bottom:.3rem">{title}</div><div style="font-size:.84rem;color:var(--text2);line-height:1.6">{desc}</div></div></div>'
        for icon, title, desc in [
          ("✅", "Quality Assurance", "Rigorous quality checks and compliance-driven procurement processes."),
          ("🤝", "Customer-First Approach", "Solution-oriented service with dedicated support for every client."),
          ("📋", "Compliance-Driven", "All products meet industry standards and regulatory requirements."),
          ("📞", "Dedicated Support", "Direct WhatsApp access for fast quotes, updates, and after-sales support."),
        ])}
    </div>
  </div>
</div>

<!-- Industries -->
<div style="background:var(--bg2);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:3.5rem 2.5rem">
  <div style="max-width:1200px;margin:0 auto">
    <div class="section-header">
      <span class="section-label">Industries We Serve</span>
      <h2 class="section-title">Powering Operations Across Sectors</h2>
    </div>
    <div class="card-grid-4">
      {''.join(f'<div style="text-align:center;padding:2rem 1rem;background:var(--surface);border:1px solid var(--border);border-radius:12px"><div style="font-size:3rem;margin-bottom:1rem">{icon}</div><div style="font-family:\'Barlow Condensed\',sans-serif;font-weight:700;font-size:1rem;letter-spacing:.5px;text-transform:uppercase;color:var(--text);margin-bottom:.4rem">{name}</div><div style="font-size:.8rem;color:var(--text3)">{desc}</div></div>'
        for icon, name, desc in [
          ("🛢️","Oil & Gas","Upstream, midstream & downstream operations"),
          ("🏗️","Construction","Infrastructure and civil engineering projects"),
          ("🏭","Industrial","Manufacturing and processing facilities"),
          ("🏢","Facility Mgmt","Building maintenance and operations"),
        ])}
    </div>
  </div>
</div>

{BRANDS_STRIP}
{footer_html()}
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: PRODUCTS & SERVICES PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/services", response_class=HTMLResponse)
async def services(request: Request):
    save_visit(request.client.host)
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>Products & Services — NAWA Global General Trading</title>
<meta name="description" content="Explore NAWA Global's full range of oilfield, industrial, safety, and lubricant products and services."></head>
<body>
{navbar_public("services")}

<div class="page-hero">
  <div class="page-hero-inner">
    <div class="page-hero-eyebrow">Products &amp; Services</div>
    <h1 class="page-hero-title">Full Spectrum of<br><em style="color:var(--green-light)">Industrial Supply</em></h1>
    <p class="page-hero-sub">From oilfield spare parts to safety PPE — we supply everything your operations need, sourced globally and delivered reliably.</p>
  </div>
</div>

<!-- Core services -->
<div class="section">
  <div class="section-header">
    <span class="section-label">Core Offerings</span>
    <h2 class="section-title">What We Supply</h2>
    <p class="section-sub">A comprehensive range covering every industrial supply need.</p>
  </div>
  <div style="display:flex;flex-direction:column;gap:1rem">
    {''.join(f'<div class="products-list-item"><div class="products-list-icon">{icon}</div><div><div class="products-list-title">{title}</div><div class="products-list-text">{desc}</div></div></div>'
      for icon, title, desc in [
        ("🛢️","Oilfield Spare Parts & Equipment","High-quality oilfield components including pipe fittings, press fittings, flowmeters, pressure gauges, instrumentation fluid oil, stud bolts &amp; fasteners, and specialized drilling equipment."),
        ("🔧","Industrial Consumables & MRO Supplies","Comprehensive MRO (maintenance, repair, operations) supplies including grills, diffusers, exhaust fans, instrumentation switches &amp; cables, solar products, and irrigation systems."),
        ("💧","Industrial & Automotive Grease","Premium grease products including COPASLIP, Duck Paste, and specialty greases for industrial machinery, automotive applications, and high-temperature environments."),
        ("🛞","Lubricants & Specialty Oils","Instrumentation fluid oils, specialty lubricants, and performance oils for industrial and automotive equipment — trusted brands like Molyslip, Lubriplate, and Jet-Lube."),
        ("🧪","Degreasers & Cleaning Chemicals","Industrial-strength degreasers, adhesives, sealants, and cleaning chemicals for maintenance and facility management applications."),
        ("⚙️","Hydraulic & Mechanical Components","Metal valves, pumps, mechanical seals, oilfield seals, expansion joints, couplings, flange adaptors, rubber products (O-rings, gaskets, packing, hoses), and power belts."),
        ("🏗️","Pipes, Fittings & Structural","Copper pipes &amp; fittings, PVC/CPVC/PPR/HDPE pipes, ferrous &amp; non-ferrous pipes, flanges &amp; forgings, and underground drainage &amp; sewage products."),
        ("⚡","Electrical & Instrumentation","LED industrial lights, instrumentation switches &amp; cables, pressure gauges, flowmeters, and solar products."),
        ("🛡️","Personal Protective Equipment (PPE)","Complete safety portfolio: hand protection (impact/mechanical/chemical), head protection, eye protection, ear protection, face protection, foot protection, and full-body uniforms (IFR/FR/Cotton/PC)."),
        ("🔍","Custom Sourcing & Procurement","Tailored procurement services utilizing our global supplier network to source specific products, negotiate pricing, and manage the complete supply chain."),
      ])}
  </div>
</div>

<!-- Safety PPE Detail -->
<div style="background:var(--bg2);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:4rem 2.5rem">
  <div style="max-width:1200px;margin:0 auto">
    <div class="section-header">
      <span class="section-label">Safety & PPE</span>
      <h2 class="section-title">Complete Personal Protection Range</h2>
      <p class="section-sub">Protecting your workforce with certified, industry-grade safety equipment.</p>
    </div>
    <div class="card-grid-3">
      {''.join(f'<div class="info-card"><div class="info-card-icon">{icon}</div><div class="info-card-title">{title}</div><div class="info-card-text">{desc}</div></div>'
        for icon, title, desc in [
          ("🧤","Hand Protection","Impact, mechanical, chemical and new generation gloves for all hazard types."),
          ("⛑️","Head Protection","Hard hats and helmets compliant with industrial safety standards."),
          ("🥽","Eye Protection","Safety glasses, goggles, and face shields for various environments."),
          ("👂","Ear Protection","Earplugs and earmuffs for noise-hazard environments."),
          ("😷","Face Protection","Respirators, half-face masks, and full-face respiratory protection."),
          ("👟","Foot Protection","Safety boots for various terrains and hazard conditions."),
          ("👔","Uniforms & Workwear","IFR/FR/Cotton/PC uniforms, hi-vis workwear, and disposable coveralls."),
          ("🔒","LOTO & Fall Protection","Lockout/Tagout kits, harnesses, self-retracting lifelines (SRL), and gas monitors."),
          ("🧰","Other Safety Equipment","Eye wash stations, emergency breathing devices (EEBD/SCBA), and first aid kits."),
        ])}
    </div>
  </div>
</div>

<!-- Product Range Visual -->
<div class="section">
  <div class="section-header">
    <span class="section-label">Product Range</span>
    <h2 class="section-title">Extensive Industrial Product Range</h2>
    <p class="section-sub">Sourced from leading global brands and manufacturers.</p>
  </div>
  <div class="card-grid-4">
    {''.join(f'<div style="padding:1.2rem;background:var(--surface);border:1px solid var(--border);border-radius:10px;text-align:center;transition:all var(--tr)" onmouseover="this.style.borderColor=\'var(--border-accent)\'" onmouseout="this.style.borderColor=\'var(--border)\'"><div style="font-size:1.8rem;margin-bottom:.6rem">{icon}</div><div style="font-family:\'Barlow Condensed\',sans-serif;font-size:.82rem;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--text2)">{name}</div></div>'
      for icon, name in [
        ("🔩","Press Pipe Fittings"), ("📊","Flowmeters"), ("⚙️","Stud Bolts"), ("🔴","Grease Gun & Pump"),
        ("📡","Instrumentation"), ("☀️","Solar Products"), ("🔧","Plastic & Thread Protector"), ("💧","Drainage Systems"),
        ("📈","Pressure Gauges"), ("🌿","Irrigation Products"), ("🚿","Sanitary Products"), ("💡","LED Lighting"),
        ("🛡️","Anti-Slip Products"), ("🔌","Switches & Cables"), ("🔄","Vibration Isolators"), ("🔩","Flange & Forging"),
        ("🪙","Copper Pipes"), ("🔗","Expansion Joints"), ("📦","Power Belt & Bags"), ("🔧","Metal Valves"),
        ("⛓️","Lifting Chains & Hoist"), ("🚿","PVC/PPR Pipes"), ("🔌","Manhole Covers"), ("🪣","Chemicals & Adhesives"),
      ])}
  </div>
</div>

{BRANDS_STRIP}

<!-- CTA -->
<div style="background:linear-gradient(135deg,var(--green2),var(--green3));padding:4rem 2.5rem;text-align:center">
  <div style="max-width:600px;margin:0 auto">
    <h2 style="font-family:'Playfair Display',serif;font-size:2.2rem;color:#fff;margin-bottom:1rem">Need a Specific Product?</h2>
    <p style="font-size:.97rem;color:rgba(255,255,255,.82);line-height:1.75;margin-bottom:2rem">Can't find what you're looking for? Our custom sourcing service can find and procure virtually any industrial product you need.</p>
    <div style="display:flex;gap:1rem;justify-content:center;flex-wrap:wrap">
      <a href="https://wa.me/{wa_num()}" target="_blank" class="wa-btn">{WA_SVG} Request a Quote</a>
      <a href="/catalog" class="btn" style="background:rgba(255,255,255,.15);border-color:rgba(255,255,255,.3);color:#fff">Browse Catalog →</a>
    </div>
  </div>
</div>

{footer_html()}
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: CONTACT PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request, sent: str = ""):
    save_visit(request.client.host)
    success_msg = '<div class="alert success" style="margin-bottom:1.5rem">✅ Message sent! We will get back to you shortly via WhatsApp or email.</div>' if sent == "1" else ""
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>Contact Us — NAWA Global General Trading</title>
<meta name="description" content="Contact NAWA Global General Trading for product inquiries, quotes, and procurement assistance."></head>
<body>
{navbar_public("contact")}

<div class="page-hero">
  <div class="page-hero-inner">
    <div class="page-hero-eyebrow">Get in Touch</div>
    <h1 class="page-hero-title">Contact<br><em style="color:var(--green-light)">NAWA Global</em></h1>
    <p class="page-hero-sub">Reach out for product inquiries, quotes, or procurement support. We respond quickly via WhatsApp and email.</p>
  </div>
</div>

<div class="section">
  <div class="contact-grid">
    <!-- Left: info -->
    <div>
      <span class="section-label" style="display:block;margin-bottom:1.2rem">Contact Information</span>
      <div class="contact-info-item">
        <div class="contact-info-icon">📍</div>
        <div><div class="contact-info-label">Address</div><div class="contact-info-value">{CONTACT_ADDRESS}</div></div>
      </div>
      <div class="contact-info-item">
        <div class="contact-info-icon">📞</div>
        <div><div class="contact-info-label">Phone / WhatsApp</div><div class="contact-info-value"><a href="tel:{CONTACT_WHATSAPP}" style="color:var(--green-light)">{CONTACT_WHATSAPP}</a></div></div>
      </div>
      <div class="contact-info-item">
        <div class="contact-info-icon">📧</div>
        <div><div class="contact-info-label">Email</div><div class="contact-info-value"><a href="mailto:{CONTACT_EMAIL}" style="color:var(--green-light)">{CONTACT_EMAIL}</a></div></div>
      </div>
      <div class="contact-info-item">
        <div class="contact-info-icon">🌐</div>
        <div><div class="contact-info-label">Website</div><div class="contact-info-value"><a href="https://{CONTACT_WEBSITE}" target="_blank" style="color:var(--green-light)">{CONTACT_WEBSITE}</a></div></div>
      </div>

      <div style="margin-top:2rem;padding:1.5rem;background:linear-gradient(135deg,rgba(46,125,50,.08),rgba(212,160,23,.05));border:1px solid rgba(46,125,50,.2);border-radius:12px">
        <div style="font-family:'Playfair Display',serif;font-size:1.15rem;color:var(--text);margin-bottom:.8rem">Chat on WhatsApp</div>
        <p style="font-size:.85rem;color:var(--text2);line-height:1.6;margin-bottom:1rem">For the fastest response, contact us directly on WhatsApp. Our team is available to assist with quotes and product inquiries.</p>
        <a href="https://wa.me/{wa_num()}" target="_blank" class="wa-btn" style="width:100%;justify-content:center">{WA_SVG} Chat Now on WhatsApp</a>
      </div>
    </div>

    <!-- Right: form -->
    <div class="contact-form-card">
      <div style="font-family:'Playfair Display',serif;font-size:1.5rem;color:var(--text);margin-bottom:.4rem">Send an Inquiry</div>
      <div style="font-size:.83rem;color:var(--text3);margin-bottom:1.5rem">Fill out the form and we'll get back to you promptly.</div>
      {success_msg}
      <form method="post" action="/contact">
        <div class="grid-2">
          <div class="form-group"><label class="form-label">Your Name *</label><input type="text" name="name" class="form-control" placeholder="John Smith" required></div>
          <div class="form-group"><label class="form-label">Email Address *</label><input type="email" name="email" class="form-control" placeholder="john@company.com" required></div>
        </div>
        <div class="form-group"><label class="form-label">Company</label><input type="text" name="company" class="form-control" placeholder="Your Company Name"></div>
        <div class="form-group"><label class="form-label">Product / Service Inquiry</label><input type="text" name="product" class="form-control" placeholder="e.g. Oilfield spare parts, Safety PPE, Lubricants..."></div>
        <div class="form-group"><label class="form-label">Message *</label><textarea name="message" class="form-control" rows="5" placeholder="Describe your requirements, quantity, delivery timeline, etc." required></textarea></div>
        <button type="submit" class="btn primary" style="width:100%;justify-content:center;padding:.9rem;font-size:.95rem">Send Inquiry →</button>
        <p style="font-size:.73rem;color:var(--text3);text-align:center;margin-top:.8rem">We typically respond within a few hours during business hours.</p>
      </form>
    </div>
  </div>
</div>

{footer_html()}
</body></html>"""

@app.post("/contact")
async def contact_submit(request: Request, name: str = Form(...), email: str = Form(...), company: str = Form(""), product: str = Form(""), message: str = Form(...)):
    # In production, integrate with email or WhatsApp API here
    # For now, redirect to success
    return RedirectResponse("/contact?sent=1", status_code=303)


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: CATALOG (full product listing with search + pagination)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/catalog", response_class=HTMLResponse)
async def catalog(request: Request, page: int = 1, q: str = "", cat: str = ""):
    save_visit(request.client.host)
    all_products = load_products()
    all_cats = sorted(set(p.get("category","General") for p in all_products))

    filtered = all_products
    if q:
        ql = q.lower()
        filtered = [p for p in filtered if ql in p.get("name","").lower() or ql in p.get("description","").lower() or ql in p.get("tags","").lower()]
    if cat:
        filtered = [p for p in filtered if p.get("category","") == cat]

    total = len(filtered)
    total_pages = max(1, math.ceil(total / PRODUCTS_PER_PAGE))
    page = max(1, min(page, total_pages))
    start = (page-1)*PRODUCTS_PER_PAGE
    page_products = filtered[start:start+PRODUCTS_PER_PAGE]

    cards_html = ""
    for p in page_products:
        imgs = get_product_images(p)
        if imgs:
            media = f'<img src="/uploads/{imgs[0]}" alt="{p["name"]}" loading="lazy">'
            count_badge = f'<span class="card-img-count">1 / {len(imgs)}</span>' if len(imgs) > 1 else ""
        else:
            media = '<div class="card-media-placeholder">📦</div>'
            count_badge = ""
        wa_msg = f"Hello! I'm interested in: *{p['name']}*. Please send me details.".replace(' ','%20').replace('*','%2A')
        wa_link = f"https://wa.me/{wa_num()}?text={wa_msg}"
        cards_html += f"""<div class="product-card">
          <div class="card-media" onclick="location.href='/product/{p['id']}'">
            {media}
            <span class="card-category-badge">{p.get('category','General')}</span>
            {count_badge}
          </div>
          <div class="card-body">
            <div class="card-title">{p['name']}</div>
            <div class="card-desc">{p.get('description','No description available.')}</div>
            <div class="card-footer">
              <a href="/product/{p['id']}" class="btn sm primary" style="flex:1;justify-content:center">View Details</a>
              <a href="{wa_link}" target="_blank" class="btn sm outline-gold">Quote</a>
            </div>
          </div>
        </div>"""

    cat_opts = '<option value="">All Categories</option>' + "".join(
        f'<option value="{c}"{"selected" if cat==c else ""}>{c}</option>' for c in all_cats
    )
    base_url = f"/catalog?q={q}&cat={cat}"
    pagination = make_pagination(page, total_pages, base_url)
    r_start = start+1 if total else 0
    r_end = min(start+PRODUCTS_PER_PAGE, total)
    results_txt = f"Showing {r_start}–{r_end} of {total} product{'s' if total!=1 else ''}" if total else "No products found"
    empty = '<div class="empty-state"><div class="empty-state-icon">🔍</div><h3>No products found</h3><p>Try a different search or category.</p></div>' if not page_products else ""

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>Product Catalog — NAWA Global General Trading</title></head>
<body>
{navbar_public()}
<div class="page-hero" style="padding:100px 2.5rem 50px">
  <div class="page-hero-inner">
    <div class="page-hero-eyebrow">Product Catalog</div>
    <h1 class="page-hero-title" style="font-size:2.4rem">{cat if cat else "All Products"}</h1>
  </div>
</div>
<div id="catalog" class="section" style="padding-top:2rem">
  <div class="section-header-row">
    <div>
      <span class="section-label">Catalog</span>
      <div style="font-family:'Playfair Display',serif;font-size:1.8rem;color:var(--text)">{cat if cat else "All Products"}</div>
    </div>
    <span class="section-count">{total} product{'s' if total!=1 else ''}</span>
  </div>
  <form method="get" action="/catalog" id="catalog-form">
    <div class="catalog-controls">
      <div class="search-box">
        <input type="text" name="q" value="{q}" placeholder="Search products…" oninput="debounce()" autocomplete="off">
      </div>
      <select name="cat" class="filter-select" onchange="this.form.submit()">{cat_opts}</select>
      <input type="hidden" name="page" value="1">
      <span class="results-info">{results_txt}</span>
      {"<a href='/catalog' class='btn sm'>Clear</a>" if q or cat else ""}
    </div>
  </form>
  {f'<div class="product-grid">{cards_html}</div>' if page_products else empty}
  {pagination}
</div>
{footer_html()}
<script>
  let _t;function debounce(){{clearTimeout(_t);_t=setTimeout(()=>document.getElementById('catalog-form').submit(),450)}}
</script>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC: PRODUCT DETAIL with gallery + lightbox
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/product/{pid}", response_class=HTMLResponse)
async def product_detail(pid: str, request: Request):
    products = load_products()
    p = next((x for x in products if x["id"] == pid), None)
    if not p: return RedirectResponse("/catalog")

    imgs = get_product_images(p)
    imgs_json = json.dumps([f"/uploads/{i}" for i in imgs])

    if imgs:
        main_img = f'<img src="/uploads/{imgs[0]}" alt="{p["name"]}" id="main-gallery-img">'
        thumbs = "".join(
            f'<img src="/uploads/{img}" class="detail-thumb{"  active" if i==0 else ""}" onclick="setMainImg(this,{i})" alt="Image {i+1}">'
            for i, img in enumerate(imgs)
        )
        thumbs_block = f'<div class="detail-thumbs">{thumbs}</div>' if len(imgs)>1 else ""
    else:
        main_img = '<div class="detail-img-placeholder">📦</div>'
        thumbs_block = ""

    wa_msg = f"Hello! I'm interested in: *{p['name']}*. Please send details and a quote.".replace(' ','%20').replace('*','%2A')
    wa_link = f"https://wa.me/{wa_num()}?text={wa_msg}"

    specs_rows = "".join(
        f"<tr><td>{k.strip()}</td><td>{v.strip()}</td></tr>"
        for spec in p.get("specs",[]) if ":" in spec
        for k, v in [spec.split(":",1)]
    )
    specs_section = f'<div class="specs-box"><div class="specs-box-title">Specifications</div><table><tbody>{specs_rows}</tbody></table></div>' if specs_rows else ""
    tags_html = " ".join(f'<span class="tag green">{t.strip()}</span>' for t in p.get("tags","").split(",") if t.strip())
    tags_block = f'<div style="display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:1.2rem">{tags_html}</div>' if tags_html else ""

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>{p['name']} — NAWA Global</title></head>
<body>
{navbar_public()}
<div class="section" style="margin-top:72px;padding-top:2rem">
  <div class="breadcrumb">
    <a href="/">Home</a><span>/</span>
    <a href="/catalog">Catalog</a><span>/</span>
    <a href="/catalog?cat={p.get('category','')}">{p.get('category','Products')}</a><span>/</span>
    <span>{p['name']}</span>
  </div>
  <div class="detail-layout">
    <div class="detail-gallery">
      <div class="detail-main-img" onclick="openLightbox(0)">{main_img}</div>
      {thumbs_block}
    </div>
    <div>
      <div class="detail-eyebrow">{p.get('category','Product')}</div>
      <h1 class="detail-title">{p['name']}</h1>
      {tags_block}
      <p class="detail-desc">{p.get('description','')}</p>
      {specs_section}
      <div class="detail-actions">
        <a href="{wa_link}" target="_blank" class="wa-btn">{WA_SVG} Get Quote on WhatsApp</a>
        <a href="/catalog" class="btn">← All Products</a>
      </div>
      <p style="margin-top:1rem;font-size:.76rem;color:var(--text3)">📞 {CONTACT_WHATSAPP} &nbsp;|&nbsp; 📧 {CONTACT_EMAIL}</p>
    </div>
  </div>
</div>

<div class="lightbox" id="lightbox">
  <button class="lightbox-close" onclick="closeLb()">✕</button>
  <img class="lightbox-img" id="lb-img" src="" alt="">
  <div class="lightbox-controls">
    <button class="lightbox-nav" onclick="lbStep(-1)">&#8249;</button>
    <span class="lightbox-counter" id="lb-ctr"></span>
    <button class="lightbox-nav" onclick="lbStep(1)">&#8250;</button>
  </div>
  <div class="lightbox-thumbs" id="lb-thumbs"></div>
</div>

{footer_html()}
<script>
const IMGS={imgs_json};
let LBI=0;
function openLightbox(i){{if(!IMGS.length)return;LBI=i;document.getElementById('lightbox').classList.add('open');renderLb();document.body.style.overflow='hidden'}}
function closeLb(){{document.getElementById('lightbox').classList.remove('open');document.body.style.overflow=''}}
function renderLb(){{
  document.getElementById('lb-img').src=IMGS[LBI];
  document.getElementById('lb-ctr').textContent=(LBI+1)+' / '+IMGS.length;
  document.getElementById('lb-thumbs').innerHTML=IMGS.map((s,i)=>`<img src="${{s}}" class="lightbox-thumb${{i===LBI?' active':''}}" onclick="lbGo(${{i}})">`).join('');
}}
function lbStep(d){{LBI=(LBI+d+IMGS.length)%IMGS.length;renderLb()}}
function lbGo(i){{LBI=i;renderLb()}}
function setMainImg(el,i){{document.getElementById('main-gallery-img').src=el.src;document.querySelectorAll('.detail-thumb').forEach(t=>t.classList.remove('active'));el.classList.add('active');LBI=i}}
document.getElementById('lightbox').addEventListener('click',e=>{{if(e.target===document.getElementById('lightbox'))closeLb()}});
document.addEventListener('keydown',e=>{{
  if(!document.getElementById('lightbox').classList.contains('open'))return;
  if(e.key==='ArrowRight')lbStep(1);if(e.key==='ArrowLeft')lbStep(-1);if(e.key==='Escape')closeLb();
}});
</script>
</body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN AUTH
# ═══════════════════════════════════════════════════════════════════════════════

@app.get(f"{ADMIN_ROUTE}/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if is_admin(request): return RedirectResponse(f"{ADMIN_ROUTE}/dashboard")
    err = f'<div class="alert error">⚠️ {error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>Admin Login — NAWA Global</title></head>
<body>
<div class="login-wrap">
  <div class="login-box">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem">
      <div style="display:flex;align-items:center;gap:.7rem">
        {NAWA_LOGO}
        <div>
          <div style="font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:1.1rem;letter-spacing:.5px;text-transform:uppercase;color:var(--text)">NAWA Global</div>
          <div style="font-family:'Barlow Condensed',sans-serif;font-size:.58rem;letter-spacing:3px;color:var(--text3);text-transform:uppercase">Admin Portal</div>
        </div>
      </div>
      <button class="theme-toggle" onclick="toggleTheme()"></button>
    </div>
    {err}
    <form method="post" action="{ADMIN_ROUTE}/login">
      <div class="form-group"><label class="form-label">Username</label><input type="text" name="username" class="form-control" autocomplete="username" required></div>
      <div class="form-group"><label class="form-label">Password</label><input type="password" name="password" class="form-control" autocomplete="current-password" required></div>
      <button type="submit" class="btn primary" style="width:100%;justify-content:center;padding:.8rem;margin-top:.4rem">Sign In →</button>
    </form>
    <p style="font-size:.7rem;color:var(--text3);text-align:center;margin-top:1.2rem">Default: admin / admin123</p>
  </div>
</div>
</body></html>"""

@app.post(f"{ADMIN_ROUTE}/login")
async def do_login(response: Response, username: str = Form(...), password: str = Form(...)):
    ph = hashlib.sha256(password.encode()).hexdigest()
    if username != ADMIN_USERNAME or ph != ADMIN_PASSWORD_HASH:
        return RedirectResponse(f"{ADMIN_ROUTE}/login?error=Invalid+credentials", status_code=303)
    token = secrets.token_hex(32)
    SESSIONS[token] = datetime.now() + timedelta(hours=8)
    resp = RedirectResponse(f"{ADMIN_ROUTE}/dashboard", status_code=303)
    resp.set_cookie("session", token, httponly=True, samesite="lax", max_age=28800)
    return resp

@app.get(f"{ADMIN_ROUTE}/logout")
async def logout():
    resp = RedirectResponse(f"{ADMIN_ROUTE}/login", status_code=303)
    resp.delete_cookie("session")
    return resp

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.get(f"{ADMIN_ROUTE}/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    require_admin(request)
    products = load_products()
    visits = load_visits()
    today = datetime.now().strftime("%Y-%m-%d")
    today_v = sum(1 for v in visits if v["time"].startswith(today))
    uniq = len(set(v["ip"] for v in visits))
    cats = len(set(p.get("category","") for p in products))
    rows = "".join(
        f'<tr><td style="font-family:\'Barlow Condensed\',monospace;font-size:.78rem">{v["ip"]}</td>'
        f'<td style="color:var(--text2);font-size:.82rem">{v["time"][:19].replace("T"," ")}</td></tr>'
        for v in visits[-8:][::-1]
    )
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>Dashboard — Admin</title></head>
<body>
{navbar_admin()}
<div class="admin-layout">
  {admin_sidebar("dashboard")}
  <div class="main-content">
    <div class="page-title">Dashboard</div>
    <div class="page-subtitle">Overview of catalog and visitor activity</div>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-num">{len(products)}</div><div class="stat-label">Products</div></div>
      <div class="stat-card"><div class="stat-num">{cats}</div><div class="stat-label">Categories</div></div>
      <div class="stat-card"><div class="stat-num">{len(visits)}</div><div class="stat-label">Total Visits</div></div>
      <div class="stat-card"><div class="stat-num">{today_v}</div><div class="stat-label">Today</div></div>
      <div class="stat-card"><div class="stat-num">{uniq}</div><div class="stat-label">Unique IPs</div></div>
    </div>
    <div style="font-family:'Playfair Display',serif;font-size:1.15rem;margin-bottom:.8rem">Recent Visitors</div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>IP Address</th><th>Timestamp</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="2" style="text-align:center;color:var(--text3);padding:2rem">No visits yet</td></tr>'}</tbody>
      </table>
    </div>
  </div>
</div>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get(f"{ADMIN_ROUTE}/products", response_class=HTMLResponse)
async def admin_products(request: Request, msg: str = ""):
    require_admin(request)
    products = load_products()
    msg_html = f'<div class="alert success">✅ {msg}</div>' if msg else ""

    rows = ""
    for p in products:
        imgs = get_product_images(p)
        if imgs:
            thumbs_row = '<div style="display:flex;gap:3px">' + "".join(
                f'<img src="/uploads/{img}" style="width:36px;height:30px;object-fit:cover;border-radius:4px;border:1px solid var(--border)">'
                for img in imgs[:3]
            )
            if len(imgs)>3: thumbs_row += f'<span style="width:30px;height:30px;background:var(--bg3);border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:.6rem;color:var(--text3)">+{len(imgs)-3}</span>'
            thumbs_row += '</div>'
        else:
            thumbs_row = '<div style="width:36px;height:30px;background:var(--bg3);border-radius:4px;display:flex;align-items:center;justify-content:center">📦</div>'

        rows += f"""<tr>
          <td>{thumbs_row}</td>
          <td><strong style="font-weight:600">{p['name']}</strong></td>
          <td><span class="tag green">{p.get('category','—')}</span></td>
          <td style="color:var(--text2);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.81rem">{p.get('description','')[:70]}</td>
          <td style="color:var(--text3);font-family:'Barlow Condensed',sans-serif;font-size:.78rem;letter-spacing:1px">{len(imgs)} img{'s' if len(imgs)!=1 else ''}</td>
          <td><div style="display:flex;gap:.4rem">
            <a href="{ADMIN_ROUTE}/products/edit/{p['id']}" class="btn sm">Edit</a>
            <a href="{ADMIN_ROUTE}/products/delete/{p['id']}" class="btn sm danger" onclick="return confirm('Delete this product?')">Delete</a>
          </div></td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>Products — Admin</title></head>
<body>
{navbar_admin()}
<div class="admin-layout">
  {admin_sidebar("products")}
  <div class="main-content">
    <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:1.5rem">
      <div><div class="page-title">Products</div><div class="page-subtitle">Manage your product catalog</div></div>
      <button class="btn primary" onclick="document.getElementById('add-modal').classList.add('open')">+ Add Product</button>
    </div>
    {msg_html}
    <div class="table-wrap">
      <table>
        <thead><tr><th>Images</th><th>Name</th><th>Category</th><th>Description</th><th>Media</th><th>Actions</th></tr></thead>
        <tbody>{rows or '<tr><td colspan="6"><div class="empty-state" style="padding:3rem"><div class="empty-state-icon">📦</div><h3>No products yet</h3><p>Add your first product above.</p></div></td></tr>'}</tbody>
      </table>
    </div>
  </div>
</div>

<div class="modal-overlay" id="add-modal">
  <div class="modal">
    <button class="modal-close" onclick="document.getElementById('add-modal').classList.remove('open')">✕</button>
    <div class="modal-title">Add New Product</div>
    <form method="post" action="{ADMIN_ROUTE}/products/add" enctype="multipart/form-data">
      <div class="form-group"><label class="form-label">Product Name *</label><input type="text" name="name" class="form-control" required placeholder="e.g. Industrial Safety Gloves"></div>
      <div class="form-group"><label class="form-label">Category *</label><input type="text" name="category" class="form-control" placeholder="e.g. Safety PPE, Oilfield Equipment" required></div>
      <div class="form-group"><label class="form-label">Description</label><textarea name="description" class="form-control"></textarea></div>
      <div class="form-group"><label class="form-label">Specifications (Label: Value, one per line)</label><textarea name="specs" class="form-control" rows="4" placeholder="Material: Nitrile&#10;Sizes: S, M, L, XL"></textarea></div>
      <div class="form-group"><label class="form-label">Tags (comma separated)</label><input type="text" name="tags" class="form-control" placeholder="safety, gloves, industrial"></div>
      <div class="form-group">
        <label class="form-label">Product Images — up to 10, first = primary</label>
        <div class="upload-zone" id="add-zone">
          <input type="file" name="images" id="add-imgs" accept="image/*" multiple onchange="previewImgs(this,'add-prev')">
          <div class="upload-zone-icon">📷</div>
          <div class="upload-zone-text">Click or drag &amp; drop images here</div>
          <div class="upload-zone-sub">PNG, JPG, WEBP · up to 10 images</div>
        </div>
        <div class="image-preview-grid" id="add-prev"></div>
      </div>
      <button type="submit" class="btn primary" style="width:100%;justify-content:center;padding:.8rem">Add Product</button>
    </form>
  </div>
</div>

<script>
function previewImgs(input,prevId){{
  const g=document.getElementById(prevId);g.innerHTML='';
  Array.from(input.files).slice(0,10).forEach((f,i)=>{{
    const r=new FileReader();
    r.onload=e=>{{
      const d=document.createElement('div');d.className='img-preview-item';
      d.innerHTML=`<img src="${{e.target.result}}">${{i===0?'<span class="primary-badge">PRIMARY</span>':''}}`;
      g.appendChild(d);
    }};r.readAsDataURL(f);
  }});
}}
function setupDrop(zoneId){{
  const z=document.getElementById(zoneId);if(!z)return;
  z.addEventListener('dragover',e=>{{e.preventDefault();z.classList.add('dragover')}});
  z.addEventListener('dragleave',()=>z.classList.remove('dragover'));
  z.addEventListener('drop',e=>{{e.preventDefault();z.classList.remove('dragover');const inp=z.querySelector('input[type=file]');inp.files=e.dataTransfer.files;inp.dispatchEvent(new Event('change'))}});
}}
setupDrop('add-zone');
</script>
</body></html>"""


@app.post(f"{ADMIN_ROUTE}/products/add")
async def add_product(
    request: Request,
    name: str = Form(...), category: str = Form(...),
    description: str = Form(""), specs: str = Form(""), tags: str = Form(""),
    images: List[UploadFile] = File(default=[])
):
    require_admin(request)
    products = load_products()
    pid = str(uuid.uuid4())[:8]
    saved = []
    for i, img in enumerate(images[:10]):
        f = await save_image(img, pid, f"_{i}")
        if f: saved.append(f)
    products.append({
        "id": pid, "name": name, "category": category, "description": description,
        "specs": [s.strip() for s in specs.splitlines() if s.strip()],
        "tags": tags, "image": saved[0] if saved else None, "images": saved,
        "created": datetime.now().isoformat()
    })
    save_products(products)
    return RedirectResponse(f"{ADMIN_ROUTE}/products?msg=Product+added+successfully", status_code=303)


@app.get(f"{ADMIN_ROUTE}/products/edit/{{pid}}", response_class=HTMLResponse)
async def edit_product_page(pid: str, request: Request):
    require_admin(request)
    products = load_products()
    p = next((x for x in products if x["id"] == pid), None)
    if not p: return RedirectResponse(f"{ADMIN_ROUTE}/products")

    imgs = get_product_images(p)
    existing_html = "".join(
        f"""<div class="existing-img-item">
          <img src="/uploads/{img}" alt="">
          <a href="{ADMIN_ROUTE}/products/delete-image/{pid}/{img}" class="del-img-btn" onclick="return confirm('Remove image?')" title="Remove">✕</a>
          {"<span class='primary-label'>PRIMARY</span>" if i==0 else ""}
        </div>"""
        for i, img in enumerate(imgs)
    )
    specs_text = "\n".join(p.get("specs",[]))

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>Edit — Admin</title></head>
<body>
{navbar_admin()}
<div class="admin-layout">
  {admin_sidebar("products")}
  <div class="main-content">
    <div class="breadcrumb">
      <a href="{ADMIN_ROUTE}/products">Products</a><span>/</span><span>Edit</span>
    </div>
    <div class="page-title">Edit Product</div>
    <div class="page-subtitle">{p['name']}</div>
    <div class="form-card" style="max-width:660px">
      <form method="post" action="{ADMIN_ROUTE}/products/edit/{pid}" enctype="multipart/form-data">
        <div class="form-group"><label class="form-label">Product Name *</label><input type="text" name="name" class="form-control" value="{p['name']}" required></div>
        <div class="form-group"><label class="form-label">Category *</label><input type="text" name="category" class="form-control" value="{p.get('category','')}"></div>
        <div class="form-group"><label class="form-label">Description</label><textarea name="description" class="form-control">{p.get('description','')}</textarea></div>
        <div class="form-group"><label class="form-label">Specifications</label><textarea name="specs" class="form-control">{specs_text}</textarea></div>
        <div class="form-group"><label class="form-label">Tags</label><input type="text" name="tags" class="form-control" value="{p.get('tags','')}"></div>
        <div class="form-group">
          <label class="form-label">Current Images ({len(imgs)}) — click ✕ to remove</label>
          {f'<div class="existing-imgs">{existing_html}</div>' if existing_html else '<p style="color:var(--text3);font-size:.82rem;margin-bottom:.5rem">No images yet.</p>'}
          <label class="form-label" style="margin-top:.8rem">Add More Images</label>
          <div class="upload-zone" id="edit-zone">
            <input type="file" name="images" id="edit-imgs" accept="image/*" multiple onchange="previewImgs(this,'edit-prev')">
            <div class="upload-zone-icon">📷</div>
            <div class="upload-zone-text">Click or drag &amp; drop to add images</div>
            <div class="upload-zone-sub">Existing images are kept unless removed above</div>
          </div>
          <div class="image-preview-grid" id="edit-prev"></div>
        </div>
        <div style="display:flex;gap:.8rem;margin-top:.5rem">
          <button type="submit" class="btn primary">Save Changes</button>
          <a href="{ADMIN_ROUTE}/products" class="btn">Cancel</a>
        </div>
      </form>
    </div>
  </div>
</div>
<script>
function previewImgs(input,prevId){{
  const g=document.getElementById(prevId);g.innerHTML='';
  Array.from(input.files).slice(0,10).forEach((f,i)=>{{
    const r=new FileReader();r.onload=e=>{{const d=document.createElement('div');d.className='img-preview-item';d.innerHTML=`<img src="${{e.target.result}}">`;g.appendChild(d)}};r.readAsDataURL(f);
  }});
}}
const ez=document.getElementById('edit-zone');
ez.addEventListener('dragover',e=>{{e.preventDefault();ez.classList.add('dragover')}});
ez.addEventListener('dragleave',()=>ez.classList.remove('dragover'));
ez.addEventListener('drop',e=>{{e.preventDefault();ez.classList.remove('dragover');const inp=ez.querySelector('input[type=file]');inp.files=e.dataTransfer.files;inp.dispatchEvent(new Event('change'))}});
</script>
</body></html>"""


@app.post(f"{ADMIN_ROUTE}/products/edit/{{pid}}")
async def do_edit_product(
    pid: str, request: Request,
    name: str = Form(...), category: str = Form(...),
    description: str = Form(""), specs: str = Form(""), tags: str = Form(""),
    images: List[UploadFile] = File(default=[])
):
    require_admin(request)
    products = load_products()
    idx = next((i for i,p in enumerate(products) if p["id"]==pid), None)
    if idx is None: return RedirectResponse(f"{ADMIN_ROUTE}/products")

    existing = get_product_images(products[idx])
    new_imgs = []
    ts = int(datetime.now().timestamp())
    for i, img in enumerate(images[:10]):
        f = await save_image(img, pid, f"_n{ts}_{i}")
        if f: new_imgs.append(f)

    all_imgs = existing + new_imgs
    products[idx].update({
        "name": name, "category": category, "description": description,
        "specs": [s.strip() for s in specs.splitlines() if s.strip()],
        "tags": tags, "image": all_imgs[0] if all_imgs else None, "images": all_imgs,
    })
    save_products(products)
    return RedirectResponse(f"{ADMIN_ROUTE}/products?msg=Product+updated+successfully", status_code=303)


@app.get(f"{ADMIN_ROUTE}/products/delete-image/{{pid}}/{{filename}}")
async def delete_product_image(pid: str, filename: str, request: Request):
    require_admin(request)
    products = load_products()
    idx = next((i for i,p in enumerate(products) if p["id"]==pid), None)
    if idx is None: return RedirectResponse(f"{ADMIN_ROUTE}/products")
    fp = UPLOAD_DIR / filename
    if fp.exists(): fp.unlink()
    imgs = get_product_images(products[idx])
    imgs = [img for img in imgs if img != filename]
    products[idx]["images"] = imgs
    products[idx]["image"] = imgs[0] if imgs else None
    save_products(products)
    return RedirectResponse(f"{ADMIN_ROUTE}/products/edit/{pid}", status_code=303)


@app.get(f"{ADMIN_ROUTE}/products/delete/{{pid}}")
async def delete_product(pid: str, request: Request):
    require_admin(request)
    products = load_products()
    p = next((x for x in products if x["id"]==pid), None)
    if p:
        for img in get_product_images(p):
            fp = UPLOAD_DIR / img
            if fp.exists(): fp.unlink()
    save_products([x for x in products if x["id"]!=pid])
    return RedirectResponse(f"{ADMIN_ROUTE}/products?msg=Product+deleted", status_code=303)

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN VISITORS — Week / Month / Year / All with bar chart
# ═══════════════════════════════════════════════════════════════════════════════

@app.get(f"{ADMIN_ROUTE}/visitors", response_class=HTMLResponse)
async def admin_visitors(request: Request, period: str = "week"):
    require_admin(request)
    all_visits = load_visits()
    now = datetime.now()

    cfg = {
        "week":  (now-timedelta(days=7),   "Last 7 Days",     "%Y-%m-%d", "%a %d"),
        "month": (now-timedelta(days=30),  "Last 30 Days",    "%Y-%m-%d", "%b %d"),
        "year":  (now-timedelta(days=365), "Last 12 Months",  "%Y-%m",    "%b %Y"),
        "all":   (datetime(2000,1,1),      "All Time",        "%Y-%m",    "%b %Y"),
    }
    cutoff, label, gkey, gfmt = cfg.get(period, cfg["week"])

    filtered = [v for v in all_visits if datetime.fromisoformat(v["time"]) >= cutoff]
    today_str = now.strftime("%Y-%m-%d")
    today_count = sum(1 for v in filtered if v["time"].startswith(today_str))
    uniq = len(set(v["ip"] for v in filtered))

    day_counts: dict = {}
    for v in filtered:
        k = datetime.fromisoformat(v["time"]).strftime(gkey)
        day_counts[k] = day_counts.get(k, 0) + 1

    sorted_keys = sorted(day_counts.keys())
    max_val = max(day_counts.values(), default=1)

    bars_html = ""
    for k in sorted_keys:
        c = day_counts[k]
        h = max(4, round((c/max_val)*100))
        try: disp = datetime.strptime(k, gkey).strftime(gfmt)
        except: disp = k
        bars_html += f'<div class="bar-wrap"><span class="bar-val">{c}</span><div class="bar" style="height:{h}%" title="{disp}: {c} visits"></div><span class="bar-label">{disp}</span></div>'

    ip_cnt: dict = {}
    for v in filtered: ip_cnt[v["ip"]] = ip_cnt.get(v["ip"],0)+1
    top_ips = sorted(ip_cnt.items(), key=lambda x:x[1], reverse=True)[:10]
    top_rows = "".join(
        f'<tr><td style="font-family:\'Barlow Condensed\',monospace;font-size:.76rem">{ip}</td><td><strong style="color:var(--green-light)">{c}</strong></td></tr>'
        for ip,c in top_ips
    )

    recent_rows = "".join(
        f'<tr><td style="font-family:\'Barlow Condensed\',monospace;font-size:.76rem">{v["ip"]}</td><td style="color:var(--text2);font-size:.8rem">{v["time"][:19].replace("T"," ")}</td></tr>'
        for v in filtered[-50:][::-1]
    )

    def pill(p, lbl):
        cls = "filter-pill active" if period==p else "filter-pill"
        return f'<a href="{ADMIN_ROUTE}/visitors?period={p}" class="{cls}">{lbl}</a>'

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>Visitors — Admin</title></head>
<body>
{navbar_admin()}
<div class="admin-layout">
  {admin_sidebar("visitors")}
  <div class="main-content">
    <div class="page-title">Visitor Analytics</div>
    <div class="page-subtitle">Track who's viewing your product catalog</div>

    <div class="filter-bar">
      <span style="font-family:'Barlow Condensed',sans-serif;font-size:.6rem;color:var(--text3);letter-spacing:2px;margin-right:.3rem;font-weight:600;text-transform:uppercase">Period:</span>
      {pill("week","This Week")}
      {pill("month","This Month")}
      {pill("year","This Year")}
      {pill("all","All Time")}
    </div>

    <div class="stat-grid">
      <div class="stat-card"><div class="stat-num">{len(filtered)}</div><div class="stat-label">Visits ({label})</div></div>
      <div class="stat-card"><div class="stat-num">{today_count}</div><div class="stat-label">Today</div></div>
      <div class="stat-card"><div class="stat-num">{uniq}</div><div class="stat-label">Unique IPs</div></div>
      <div class="stat-card"><div class="stat-num">{len(all_visits)}</div><div class="stat-label">All-Time Total</div></div>
    </div>

    <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.5rem;margin-bottom:1.5rem">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
        <div style="font-family:'Playfair Display',serif;font-size:1.1rem">{label} — Visit Trend</div>
        <span style="font-family:'Barlow Condensed',sans-serif;font-size:.65rem;color:var(--text3);letter-spacing:1px">{len(sorted_keys)} DATA POINT{'S' if len(sorted_keys)!=1 else ''}</span>
      </div>
      {f'<div class="bar-chart">{bars_html}</div>' if bars_html else '<div style="text-align:center;color:var(--text3);padding:3rem 0;font-size:.9rem">No data for this period</div>'}
    </div>

    <div class="grid-2">
      <div>
        <div style="font-family:'Playfair Display',serif;font-size:1.1rem;margin-bottom:.8rem">Top Visitors</div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>IP Address</th><th>Visits</th></tr></thead>
            <tbody>{top_rows or '<tr><td colspan="2" style="text-align:center;color:var(--text3);padding:1.5rem">No data</td></tr>'}</tbody>
          </table>
        </div>
      </div>
      <div>
        <div style="font-family:'Playfair Display',serif;font-size:1.1rem;margin-bottom:.8rem">Recent 50 Visits</div>
        <div class="table-wrap" style="max-height:430px;overflow-y:auto">
          <table>
            <thead><tr><th>IP Address</th><th>Timestamp</th></tr></thead>
            <tbody>{recent_rows or '<tr><td colspan="2" style="text-align:center;color:var(--text3);padding:1.5rem">No visits in this period</td></tr>'}</tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>
</body></html>"""


# ─── Redirect old paths ────────────────────────────────────────────────────────
@app.get("/admin/login")
async def _old1(): return RedirectResponse("/", status_code=302)
@app.get("/admin/dashboard")
async def _old2(): return RedirectResponse("/", status_code=302)
@app.get("/admin")
async def _old3(): return RedirectResponse("/", status_code=302)


# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*60)
    print("  NAWA Global General Trading — Catalog")
    print("  http://localhost:8000")
    print(f"  Admin: http://localhost:8000{ADMIN_ROUTE}/login")
    print("  Default login: admin / admin123")
    print("="*60)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
