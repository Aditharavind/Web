"""
Ketch-All Product Catalog - Premium Edition v2
Features: Multi-image upload, pagination, admin visit analytics filtering
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
CONTACT_WHATSAPP = "+918129922989"
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

    # Open image
    img = Image.open(BytesIO(contents)).convert("RGB")

    # ✅ Resize while keeping aspect ratio
    max_size = (800, 800)  # You can change this
    img.thumbnail(max_size)

    # Optional: center crop to exact size (uncomment if needed)
    # img = img.resize((800, 600))

    fname = f"{pid}{suffix}.jpg"  # save as jpg for consistency
    save_path = UPLOAD_DIR / fname

    img.save(save_path, format="JPEG", quality=85)

    return fname

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="Ketch-All Product Catalog")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ═══════════════════════════════════════════════════════════════════════════════
# STYLES
# ═══════════════════════════════════════════════════════════════════════════════
BASE_STYLE = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Outfit:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  :root{--accent:#C8972A;--accent-light:#E8B84B;--danger:#C0392B;--success:#27AE60;--tr:.3s cubic-bezier(.4,0,.2,1)}
  [data-theme="dark"]{--bg:#0C0C0F;--bg2:#141418;--bg3:#1C1C22;--surface:#1A1A20;--surface2:#222228;--border:rgba(255,255,255,.08);--border-accent:rgba(200,151,42,.4);--text:#F0EDE8;--text2:#A8A49E;--text3:#6B6764;--nav-bg:rgba(12,12,15,.88);--cshadow:0 4px 24px rgba(0,0,0,.5);--chshadow:0 12px 48px rgba(0,0,0,.7)}
  [data-theme="light"]{--bg:#F7F5F0;--bg2:#EFEDE8;--bg3:#E8E4DC;--surface:#FFF;--surface2:#F2F0EB;--border:rgba(0,0,0,.08);--border-accent:rgba(200,151,42,.5);--text:#1A1714;--text2:#5A5550;--text3:#9A9590;--nav-bg:rgba(247,245,240,.92);--cshadow:0 2px 16px rgba(0,0,0,.08);--chshadow:0 12px 40px rgba(0,0,0,.15)}
  body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;transition:background var(--tr),color var(--tr);overflow-x:hidden}
  a{color:inherit;text-decoration:none}
  ::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:var(--bg)}::-webkit-scrollbar-thumb{background:var(--border-accent);border-radius:3px}

  /* Navbar */
  .navbar{position:fixed;top:0;left:0;right:0;z-index:200;background:var(--nav-bg);backdrop-filter:blur(20px) saturate(1.8);border-bottom:1px solid var(--border);height:68px;display:flex;align-items:center;justify-content:space-between;padding:0 2.5rem}
  .brand{font-family:'DM Serif Display',serif;font-size:1.6rem;color:var(--text)}
  .brand-accent{color:var(--accent)}
  .brand-tagline{font-family:'Space Mono',monospace;font-size:.56rem;color:var(--text3);letter-spacing:3px;text-transform:uppercase;display:block;margin-top:-2px}
  .nav-right{display:flex;align-items:center;gap:1rem}
  .theme-toggle{width:42px;height:24px;background:var(--bg3);border:1px solid var(--border);border-radius:12px;cursor:pointer;position:relative;display:flex;align-items:center;padding:2px;transition:background var(--tr)}
  .theme-toggle::after{content:'';width:18px;height:18px;background:var(--accent);border-radius:50%;transition:transform var(--tr)}
  [data-theme="light"] .theme-toggle::after{transform:translateX(18px)}

  /* Buttons */
  .btn{font-family:'Outfit',sans-serif;font-weight:600;font-size:.85rem;letter-spacing:.4px;padding:.55rem 1.4rem;border-radius:6px;border:1.5px solid var(--border);background:transparent;color:var(--text2);cursor:pointer;transition:all var(--tr);display:inline-flex;align-items:center;gap:.4rem;white-space:nowrap}
  .btn:hover{border-color:var(--accent);color:var(--accent)}
  .btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
  .btn.primary:hover{background:var(--accent-light);border-color:var(--accent-light);color:#000}
  .btn.outline-gold{border-color:var(--accent);color:var(--accent)}
  .btn.outline-gold:hover{background:var(--accent);color:#000}
  .btn.danger{border-color:var(--danger);color:var(--danger)}
  .btn.danger:hover{background:var(--danger);color:#fff}
  .btn.sm{padding:.32rem .85rem;font-size:.78rem;border-radius:5px}
  .btn.lg{padding:.85rem 2.2rem;font-size:1rem;border-radius:8px}
  .btn:disabled{opacity:.4;cursor:not-allowed}
  .wa-btn{display:inline-flex;align-items:center;gap:.6rem;background:#25D366;color:#fff;font-family:'Outfit',sans-serif;font-weight:600;font-size:.95rem;padding:.75rem 1.6rem;border-radius:8px;transition:all var(--tr);border:none;cursor:pointer}
  .wa-btn:hover{background:#1ebe5d;transform:translateY(-1px);box-shadow:0 4px 16px rgba(37,211,102,.35)}

  /* Hero */
  .hero{padding:140px 2.5rem 80px;background:var(--bg);position:relative;overflow:hidden;margin-top:68px}
  .hero-grid{position:absolute;inset:0;background-image:linear-gradient(var(--border) 1px,transparent 1px),linear-gradient(90deg,var(--border) 1px,transparent 1px);background-size:60px 60px;opacity:.5}
  .hero-glow{position:absolute;top:-100px;right:-100px;width:600px;height:600px;background:radial-gradient(circle,rgba(200,151,42,.12) 0%,transparent 70%);pointer-events:none}
  .hero-inner{max-width:1100px;margin:0 auto;position:relative}
  .hero-eyebrow{font-family:'Space Mono',monospace;font-size:.68rem;letter-spacing:4px;text-transform:uppercase;color:var(--accent);margin-bottom:1.5rem;display:flex;align-items:center;gap:1rem}
  .hero-eyebrow::before{content:'';width:40px;height:1px;background:var(--accent)}
  .hero-title{font-family:'DM Serif Display',serif;font-size:clamp(3rem,7vw,6.5rem);line-height:1;letter-spacing:-1px;color:var(--text);margin-bottom:1.5rem}
  .hero-title em{color:var(--accent);font-style:italic}
  .hero-sub{font-size:1.1rem;color:var(--text2);font-weight:300;max-width:520px;line-height:1.7;margin-bottom:2.5rem}
  .hero-cta{display:flex;gap:1rem;flex-wrap:wrap;align-items:center}
  .hero-stats{display:flex;gap:3rem;margin-top:4rem;padding-top:2rem;border-top:1px solid var(--border);flex-wrap:wrap}
  .hero-stat-num{font-family:'DM Serif Display',serif;font-size:2.2rem;color:var(--text);line-height:1}
  .hero-stat-label{font-size:.68rem;letter-spacing:2px;text-transform:uppercase;color:var(--text3);margin-top:.3rem;font-family:'Space Mono',monospace}

  /* Trust band */
  .trust-band{background:var(--bg2);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:1.5rem 2.5rem;display:flex;align-items:center;justify-content:center;gap:3rem;flex-wrap:wrap}
  .trust-item{display:flex;align-items:center;gap:.6rem;font-size:.82rem;color:var(--text2);font-weight:500}

  /* Section */
  .section{max-width:1200px;margin:0 auto;padding:3rem 2.5rem}
  .section-header{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:2rem;border-bottom:1px solid var(--border);padding-bottom:1.2rem;gap:1rem;flex-wrap:wrap}
  .section-label{font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:4px;text-transform:uppercase;color:var(--accent);margin-bottom:.4rem}
  .section-title{font-family:'DM Serif Display',serif;font-size:2rem;color:var(--text)}
  .section-count{font-family:'Space Mono',monospace;font-size:.7rem;color:var(--text3);white-space:nowrap}

  /* Catalog controls */
  .catalog-controls{display:flex;align-items:center;gap:1rem;flex-wrap:wrap;margin-bottom:2rem}
  .search-box{flex:1;min-width:200px;max-width:380px;position:relative}
  .search-box input{width:100%;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:.65rem 1rem .65rem 2.6rem;border-radius:8px;font-family:'Outfit',sans-serif;font-size:.9rem;transition:border-color var(--tr),box-shadow var(--tr)}
  .search-box input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(200,151,42,.1)}
  .search-box::before{content:'🔍';position:absolute;left:.85rem;top:50%;transform:translateY(-50%);font-size:.85rem;pointer-events:none}
  .filter-select{background:var(--surface);border:1px solid var(--border);color:var(--text2);padding:.65rem 1rem;border-radius:8px;font-family:'Outfit',sans-serif;font-size:.88rem;cursor:pointer;transition:border-color var(--tr)}
  .filter-select:focus{outline:none;border-color:var(--accent)}
  .results-info{font-size:.78rem;color:var(--text3);font-family:'Space Mono',monospace;white-space:nowrap}

  /* Product grid */
  .product-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1.5rem}
  .product-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;transition:all var(--tr);box-shadow:var(--cshadow);display:flex;flex-direction:column}
  .product-card:hover{box-shadow:var(--chshadow);border-color:var(--border-accent);transform:translateY(-3px)}
  .card-media{position:relative;height:220px;background:var(--bg3);overflow:hidden;cursor:pointer}
  .card-media img{width:100%;height:100%;object-fit:cover;transition:transform .6s cubic-bezier(.4,0,.2,1)}
  .product-card:hover .card-media img{transform:scale(1.04)}
  .card-media-placeholder{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:3.5rem;color:var(--text3)}
  .card-img-count{position:absolute;bottom:8px;right:8px;background:rgba(0,0,0,.65);color:#fff;font-family:'Space Mono',monospace;font-size:.58rem;padding:.15rem .5rem;border-radius:4px;backdrop-filter:blur(4px)}
  .card-category-badge{position:absolute;top:12px;left:12px;background:rgba(200,151,42,.92);color:#000;font-family:'Space Mono',monospace;font-size:.56rem;letter-spacing:2px;text-transform:uppercase;padding:.2rem .55rem;border-radius:4px;font-weight:700}
  .card-body{padding:1.4rem;flex:1;display:flex;flex-direction:column}
  .card-title{font-family:'DM Serif Display',serif;font-size:1.22rem;color:var(--text);margin-bottom:.5rem;line-height:1.3}
  .card-desc{font-size:.86rem;color:var(--text2);line-height:1.7;margin-bottom:1.2rem;flex:1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
  .card-footer{display:flex;gap:.6rem}

  /* Pagination */
  .pagination{display:flex;align-items:center;justify-content:center;gap:.4rem;margin-top:3rem;flex-wrap:wrap}
  .page-btn{width:38px;height:38px;display:flex;align-items:center;justify-content:center;border-radius:8px;border:1.5px solid var(--border);background:transparent;color:var(--text2);font-family:'Space Mono',monospace;font-size:.8rem;cursor:pointer;transition:all var(--tr)}
  .page-btn:hover{border-color:var(--accent);color:var(--accent)}
  .page-btn.active{background:var(--accent);border-color:var(--accent);color:#000;font-weight:700}
  .page-btn.disabled{opacity:.35;cursor:not-allowed;pointer-events:none}
  .page-ellipsis{color:var(--text3);font-size:.8rem;padding:0 .3rem}

  /* Lightbox */
  .lightbox{display:none;position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.93);align-items:center;justify-content:center;flex-direction:column}
  .lightbox.open{display:flex}
  .lightbox-img{max-width:90vw;max-height:76vh;object-fit:contain;border-radius:8px}
  .lightbox-controls{display:flex;gap:1rem;margin-top:1.2rem;align-items:center}
  .lightbox-close{position:absolute;top:1.5rem;right:1.5rem;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);width:36px;height:36px;border-radius:50%;color:#fff;font-size:1.1rem;cursor:pointer;display:flex;align-items:center;justify-content:center}
  .lightbox-nav{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);width:44px;height:44px;border-radius:50%;color:#fff;font-size:1.2rem;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s}
  .lightbox-nav:hover{background:rgba(200,151,42,.4)}
  .lightbox-counter{color:rgba(255,255,255,.6);font-family:'Space Mono',monospace;font-size:.75rem}
  .lightbox-thumbs{display:flex;gap:.5rem;margin-top:.8rem;flex-wrap:wrap;justify-content:center;max-width:520px}
  .lightbox-thumb{width:52px;height:42px;object-fit:cover;border-radius:5px;cursor:pointer;border:2px solid transparent;opacity:.6;transition:all .2s}
  .lightbox-thumb.active{border-color:var(--accent);opacity:1}

  /* Detail */
  .detail-layout{display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:start}
  .detail-gallery{display:flex;flex-direction:column;gap:.8rem}
  .detail-main-img{border-radius:12px;overflow:hidden;background:var(--bg3);aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;border:1px solid var(--border);cursor:pointer}
  .detail-main-img img{width:100%;height:100%;object-fit:cover;transition:transform .5s}
  .detail-main-img:hover img{transform:scale(1.03)}
  .detail-thumbs{display:flex;gap:.6rem;flex-wrap:wrap}
  .detail-thumb{width:72px;height:58px;border-radius:7px;object-fit:cover;border:2px solid var(--border);cursor:pointer;transition:all .2s;opacity:.7}
  .detail-thumb:hover,.detail-thumb.active{border-color:var(--accent);opacity:1}
  .detail-img-placeholder{font-size:6rem;color:var(--text3)}
  .detail-eyebrow{font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:4px;text-transform:uppercase;color:var(--accent);margin-bottom:.8rem;display:flex;align-items:center;gap:.8rem}
  .detail-eyebrow::before{content:'';width:24px;height:1px;background:var(--accent)}
  .detail-title{font-family:'DM Serif Display',serif;font-size:2.6rem;line-height:1.1;color:var(--text);margin-bottom:1rem}
  .detail-desc{font-size:1rem;color:var(--text2);line-height:1.8;margin-bottom:2rem}
  .specs-box{background:var(--bg2);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:2rem}
  .specs-box-title{font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:3px;text-transform:uppercase;color:var(--text3);padding:.85rem 1.2rem;border-bottom:1px solid var(--border);background:var(--bg3)}
  .specs-box table{width:100%}
  .specs-box td{padding:.72rem 1.2rem;font-size:.87rem;border-bottom:1px solid var(--border)}
  .specs-box tr:last-child td{border-bottom:none}
  .specs-box td:first-child{color:var(--text3);font-weight:500;width:44%}
  .detail-actions{display:flex;gap:1rem;flex-wrap:wrap}
  .tag{display:inline-block;background:var(--bg3);color:var(--text2);border:1px solid var(--border);font-size:.7rem;padding:.18rem .55rem;border-radius:100px}
  .tag.gold{background:rgba(200,151,42,.1);border-color:rgba(200,151,42,.3);color:var(--accent)}

  /* Footer */
  footer{background:var(--bg2);border-top:1px solid var(--border);padding:3rem 2.5rem;margin-top:4rem}
  .footer-inner{max-width:1100px;margin:0 auto;display:flex;justify-content:space-between;align-items:flex-start;gap:2rem;flex-wrap:wrap}
  .footer-brand{font-family:'DM Serif Display',serif;font-size:1.8rem;color:var(--text)}
  .footer-brand span{color:var(--accent)}

  /* Admin */
  .admin-layout{display:grid;grid-template-columns:240px 1fr;min-height:calc(100vh - 68px);margin-top:68px}
  .sidebar{background:var(--surface);border-right:1px solid var(--border);padding:1.5rem 0;position:sticky;top:68px;height:calc(100vh - 68px);overflow-y:auto}
  .sidebar-label{font-family:'Space Mono',monospace;font-size:.57rem;letter-spacing:3px;text-transform:uppercase;color:var(--text3);padding:.4rem 1.2rem;margin-bottom:.2rem}
  .sidebar-link{display:flex;align-items:center;gap:.7rem;padding:.7rem 1.2rem;margin:.1rem .6rem;border-radius:8px;color:var(--text2);font-size:.88rem;font-weight:500;transition:all var(--tr)}
  .sidebar-link:hover{background:var(--bg3);color:var(--text)}
  .sidebar-link.active{background:rgba(200,151,42,.12);color:var(--accent)}
  .main-content{padding:2.5rem}
  .page-title{font-family:'DM Serif Display',serif;font-size:2rem;color:var(--text);margin-bottom:.3rem}
  .page-subtitle{font-size:.84rem;color:var(--text3);margin-bottom:2rem}
  .stat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:1rem;margin-bottom:2rem}
  .stat-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.3rem;transition:border-color var(--tr)}
  .stat-card:hover{border-color:var(--border-accent)}
  .stat-num{font-family:'DM Serif Display',serif;font-size:2.6rem;color:var(--accent);line-height:1;margin-bottom:.3rem}
  .stat-label{font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:2px;text-transform:uppercase;color:var(--text3)}

  /* Filter pills */
  .filter-bar{display:flex;align-items:center;gap:.5rem;margin-bottom:1.5rem;flex-wrap:wrap}
  .filter-pill{padding:.38rem 1.1rem;border-radius:100px;border:1.5px solid var(--border);background:transparent;color:var(--text2);font-family:'Outfit',sans-serif;font-size:.8rem;font-weight:500;cursor:pointer;transition:all var(--tr);text-decoration:none}
  .filter-pill:hover{border-color:var(--accent);color:var(--accent)}
  .filter-pill.active{background:var(--accent);border-color:var(--accent);color:#000;font-weight:600}

  /* Bar chart */
  .bar-chart{display:flex;align-items:flex-end;gap:4px;height:160px;padding:.5rem 0}
  .bar-wrap{flex:1;display:flex;flex-direction:column;align-items:center;gap:.3rem;min-width:20px}
  .bar{width:100%;background:rgba(200,151,42,.22);border-radius:4px 4px 0 0;transition:height .6s cubic-bezier(.4,0,.2,1);min-height:2px}
  .bar:hover{background:rgba(200,151,42,.6)}
  .bar-label{font-family:'Space Mono',monospace;font-size:.52rem;color:var(--text3);text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
  .bar-val{font-size:.62rem;color:var(--text3)}

  /* Tables */
  .table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden}
  table{width:100%;border-collapse:collapse}
  th{font-family:'Space Mono',monospace;font-size:.58rem;letter-spacing:2px;text-transform:uppercase;color:var(--text3);padding:.85rem 1.2rem;background:var(--bg3);font-weight:400;text-align:left;border-bottom:1px solid var(--border)}
  td{padding:.85rem 1.2rem;border-bottom:1px solid var(--border);font-size:.88rem;vertical-align:middle}
  tr:last-child td{border-bottom:none}
  tr:hover td{background:rgba(200,151,42,.03)}

  /* Forms */
  .form-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:2rem}
  .form-group{margin-bottom:1.2rem}
  .form-label{display:block;font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:2px;text-transform:uppercase;color:var(--text3);margin-bottom:.5rem}
  .form-control{width:100%;background:var(--bg2);border:1px solid var(--border);color:var(--text);padding:.72rem 1rem;border-radius:8px;font-family:'Outfit',sans-serif;font-size:.9rem;transition:border-color var(--tr),box-shadow var(--tr)}
  .form-control:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(200,151,42,.1)}
  textarea.form-control{resize:vertical;min-height:110px}

  /* Multi-image upload */
  .upload-zone{border:2px dashed var(--border);border-radius:10px;padding:2rem;text-align:center;cursor:pointer;transition:all var(--tr);position:relative}
  .upload-zone:hover,.upload-zone.dragover{border-color:var(--accent);background:rgba(200,151,42,.04)}
  .upload-zone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
  .upload-zone-icon{font-size:2rem;margin-bottom:.5rem}
  .upload-zone-text{font-weight:600;font-size:.9rem;color:var(--text2);margin-bottom:.2rem}
  .upload-zone-sub{font-size:.73rem;color:var(--text3)}
  .image-preview-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:.6rem;margin-top:1rem}
  .img-preview-item{position:relative;aspect-ratio:1;border-radius:8px;overflow:hidden;border:2px solid var(--border)}
  .img-preview-item img{width:100%;height:100%;object-fit:cover}
  .img-preview-item .primary-badge{position:absolute;bottom:3px;left:3px;background:rgba(200,151,42,.9);color:#000;font-size:.48rem;font-family:'Space Mono',monospace;padding:.1rem .3rem;border-radius:3px;font-weight:700}

  /* Existing images */
  .existing-imgs{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:.6rem;margin-bottom:.8rem}
  .existing-img-item{position:relative;aspect-ratio:1;border-radius:8px;overflow:hidden;border:2px solid var(--border)}
  .existing-img-item img{width:100%;height:100%;object-fit:cover}
  .existing-img-item .del-img-btn{position:absolute;top:3px;right:3px;width:20px;height:20px;background:rgba(192,57,43,.85);border:none;border-radius:50%;color:#fff;font-size:.65rem;cursor:pointer;display:flex;align-items:center;justify-content:center;text-decoration:none;line-height:1}
  .existing-img-item .primary-label{position:absolute;bottom:3px;left:3px;background:rgba(200,151,42,.9);color:#000;font-size:.46rem;font-family:'Space Mono',monospace;padding:.1rem .3rem;border-radius:3px;font-weight:700}

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
  .modal-title{font-family:'DM Serif Display',serif;font-size:1.55rem;margin-bottom:1.5rem;color:var(--text)}

  /* Login */
  .login-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);padding:2rem}
  .login-box{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:2.5rem;width:100%;max-width:400px;box-shadow:var(--cshadow)}
  .login-logo{font-family:'DM Serif Display',serif;font-size:2rem;color:var(--text)}
  .login-logo span{color:var(--accent)}

  /* Misc */
  .breadcrumb{display:flex;align-items:center;gap:.5rem;font-size:.8rem;color:var(--text3);margin-bottom:2rem}
  .breadcrumb a{color:var(--text2);transition:color var(--tr)}
  .breadcrumb a:hover{color:var(--accent)}
  .empty-state{text-align:center;padding:5rem 2rem;color:var(--text3)}
  .empty-state-icon{font-size:4rem;margin-bottom:1rem;opacity:.5}
  .empty-state h3{font-family:'DM Serif Display',serif;font-size:1.5rem;color:var(--text2);margin-bottom:.5rem}
  .divider{border:none;border-top:1px solid var(--border)}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}

  @media(max-width:900px){
    .detail-layout,.grid-2{grid-template-columns:1fr}
    .admin-layout{grid-template-columns:1fr}
    .sidebar{display:none}
    .hero{padding:110px 1.5rem 60px}
  }
  @media(max-width:640px){
    .section{padding:2rem 1.2rem}
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

def navbar_public():
    return f"""<nav class="navbar">
      <a href="/" class="brand">Ketch<span class="brand-accent">-All</span><span class="brand-tagline">Industrial Safety Equipment</span></a>
      <div class="nav-right">
        <button class="theme-toggle" onclick="toggleTheme()" title="Toggle theme"></button>
        <a href="https://wa.me/{wa_num()}" target="_blank" class="btn outline-gold sm">{WA_SVG} Contact Us</a>
      </div>
    </nav>"""

def navbar_admin():
    return f"""<nav class="navbar">
      <a href="/" class="brand">Ketch<span class="brand-accent">-All</span>
        <span style="display:inline-block;margin-left:.6rem;font-size:.5rem;background:rgba(200,151,42,.15);border:1px solid rgba(200,151,42,.3);color:var(--accent);padding:.1rem .5rem;border-radius:4px;vertical-align:middle;font-family:'Space Mono',monospace;letter-spacing:2px;">ADMIN</span>
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
          <div class="footer-brand">Ketch<span>-All</span></div>
          <div style="font-size:.74rem;color:var(--text3);letter-spacing:1px;margin-top:.25rem">Industrial Safety Equipment · Aircraft-Grade Quality</div>
          <div style="font-size:.76rem;color:var(--text3);margin-top:.6rem">© 2024 Ketch-All. All rights reserved.</div>
        </div>
        <div>
          <div style="font-family:'Space Mono',monospace;font-size:.58rem;letter-spacing:3px;color:var(--text3);margin-bottom:.5rem">CONTACT US</div>
          <div style="font-size:.88rem;color:var(--text2)">WhatsApp: <strong style="color:var(--accent)">{CONTACT_WHATSAPP}</strong></div>
          <div style="margin-top:.8rem">
            <a href="https://wa.me/{wa_num()}" target="_blank" class="wa-btn" style="font-size:.82rem;padding:.5rem 1.1rem">{WA_SVG} Chat on WhatsApp</a>
          </div>
        </div>
      </div>
    </footer>"""

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
# PUBLIC: HOME with search + pagination
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, page: int = 1, q: str = "", cat: str = ""):
    save_visit(request.client.host)
    all_products = load_products()
    all_cats = sorted(set(p.get("category","General") for p in all_products))

    # Filter
    filtered = all_products
    if q:
        ql = q.lower()
        filtered = [p for p in filtered if ql in p.get("name","").lower() or ql in p.get("description","").lower() or ql in p.get("tags","").lower()]
    if cat:
        filtered = [p for p in filtered if p.get("category","") == cat]

    # Paginate
    total = len(filtered)
    total_pages = max(1, math.ceil(total / PRODUCTS_PER_PAGE))
    page = max(1, min(page, total_pages))
    start = (page-1)*PRODUCTS_PER_PAGE
    page_products = filtered[start:start+PRODUCTS_PER_PAGE]

    # Cards
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
    base_url = f"/?q={q}&cat={cat}"
    pagination = make_pagination(page, total_pages, base_url)
    r_start = start+1 if total else 0
    r_end = min(start+PRODUCTS_PER_PAGE, total)
    results_txt = f"Showing {r_start}–{r_end} of {total} product{'s' if total!=1 else ''}" if total else "No products found"
    empty = '<div class="empty-state"><div class="empty-state-icon">🔍</div><h3>No products found</h3><p>Try a different search or category.</p></div>' if not page_products else ""

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>Ketch-All — Industrial Safety Equipment</title>
<meta name="description" content="Premium aircraft-grade industrial safety equipment."></head>
<body>
{navbar_public()}
<div class="hero">
  <div class="hero-grid"></div>
  <div class="hero-glow"></div>
  <div class="hero-inner">
    <div class="hero-eyebrow">Aircraft-Grade Quality · Made in USA</div>
    <h1 class="hero-title">Industrial Safety<br><em>Engineered</em> to Perform</h1>
    <p class="hero-sub">Precision-built safety and snare equipment crafted from aircraft-grade aluminium — trusted by oil &amp; gas, construction, and industrial sectors globally.</p>
    <div class="hero-cta">
      <a href="#catalog" class="btn primary lg">Browse Catalog</a>
      <a href="https://wa.me/{wa_num()}" target="_blank" class="wa-btn">{WA_SVG} Get a Quote</a>
    </div>
    <div class="hero-stats">
      <div><div class="hero-stat-num">{len(all_products)}+</div><div class="hero-stat-label">Products</div></div>
      <div><div class="hero-stat-num">{len(all_cats)}+</div><div class="hero-stat-label">Categories</div></div>
      <div><div class="hero-stat-num">USA</div><div class="hero-stat-label">Origin</div></div>
      <div><div class="hero-stat-num">A/G</div><div class="hero-stat-label">Aluminium</div></div>
    </div>
  </div>
</div>
<div class="trust-band">
  <div class="trust-item">✈️ Aircraft-Grade Aluminium</div>
  <div class="trust-item">🇺🇸 Made in USA</div>
  <div class="trust-item">🛡️ Industrial Certified</div>
  <div class="trust-item">🌍 Worldwide Shipping</div>
  <div class="trust-item">💬 WhatsApp Support</div>
</div>

<div id="catalog" class="section" style="padding-top:3rem">
  <div class="section-header">
    <div>
      <div class="section-label">Product Catalog</div>
      <div class="section-title">{cat if cat else "All Products"}</div>
    </div>
    <span class="section-count">{total} product{'s' if total!=1 else ''}</span>
  </div>
  <form method="get" action="/" id="catalog-form">
    <div class="catalog-controls">
      <div class="search-box">
        <input type="text" name="q" value="{q}" placeholder="Search products…" oninput="debounce()" autocomplete="off">
      </div>
      <select name="cat" class="filter-select" onchange="this.form.submit()">{cat_opts}</select>
      <input type="hidden" name="page" value="1">
      <span class="results-info">{results_txt}</span>
      {"<a href='/' class='btn sm'>Clear</a>" if q or cat else ""}
    </div>
  </form>
  {f'<div class="product-grid">{cards_html}</div>' if page_products else empty}
  {pagination}
</div>
{footer_html()}
<script>
  document.querySelector('a[href="#catalog"]')?.addEventListener('click',e=>{{e.preventDefault();document.getElementById('catalog').scrollIntoView({{behavior:'smooth'}})}});
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
    if not p: return RedirectResponse("/")

    imgs = get_product_images(p)
    imgs_json = json.dumps([f"/uploads/{i}" for i in imgs])

    if imgs:
        main_img = f'<img src="/uploads/{imgs[0]}" alt="{p["name"]}" id="main-gallery-img">'
        thumbs = "".join(
            f'<img src="/uploads/{img}" class="detail-thumb{"active" if i==0 else ""}" onclick="setMainImg(this,{i})" alt="Image {i+1}">'
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
    tags_html = " ".join(f'<span class="tag gold">{t.strip()}</span>' for t in p.get("tags","").split(",") if t.strip())
    tags_block = f'<div style="display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:1.2rem">{tags_html}</div>' if tags_html else ""

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>{BASE_STYLE}{THEME_SCRIPT}<title>{p['name']} — Ketch-All</title></head>
<body>
{navbar_public()}
<div class="section" style="margin-top:68px;padding-top:2rem">
  <div class="breadcrumb">
    <a href="/">Home</a><span>/</span>
    <a href="/?cat={p.get('category','')}">{p.get('category','Products')}</a><span>/</span>
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
        <a href="/" class="btn">← All Products</a>
      </div>
      <p style="margin-top:1rem;font-size:.76rem;color:var(--text3)">📞 {CONTACT_WHATSAPP}</p>
    </div>
  </div>
</div>

<!-- Lightbox -->
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
<head>{BASE_STYLE}{THEME_SCRIPT}<title>Admin Login — Ketch-All</title></head>
<body>
<div class="login-wrap">
  <div class="login-box">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem">
      <div class="login-logo">Ketch<span>-All</span></div>
      <button class="theme-toggle" onclick="toggleTheme()"></button>
    </div>
    <div style="font-family:'Space Mono',monospace;font-size:.58rem;letter-spacing:3px;color:var(--text3);margin-bottom:1.5rem">ADMIN PORTAL</div>
    {err}
    <form method="post" action="{ADMIN_ROUTE}/login">
      <div class="form-group"><label class="form-label">Username</label><input type="text" name="username" class="form-control" autocomplete="username" required></div>
      <div class="form-group"><label class="form-label">Password</label><input type="password" name="password" class="form-control" autocomplete="current-password" required></div>
      <button type="submit" class="btn primary" style="width:100%;justify-content:center;padding:.8rem;margin-top:.4rem">Sign In</button>
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
        f'<tr><td style="font-family:\'Space Mono\',monospace;font-size:.78rem">{v["ip"]}</td>'
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
    <div style="font-family:'DM Serif Display',serif;font-size:1.15rem;margin-bottom:.8rem">Recent Visitors</div>
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
          <td><span class="tag gold">{p.get('category','—')}</span></td>
          <td style="color:var(--text2);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.81rem">{p.get('description','')[:70]}</td>
          <td style="color:var(--text3);font-family:'Space Mono',monospace;font-size:.7rem">{len(imgs)} img{'s' if len(imgs)!=1 else ''}</td>
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
      <div class="form-group"><label class="form-label">Product Name *</label><input type="text" name="name" class="form-control" required placeholder="e.g. Ketch-All Snare Tool Pro"></div>
      <div class="form-group"><label class="form-label">Category *</label><input type="text" name="category" class="form-control" placeholder="e.g. Snare Tool, Safety Glasses" required></div>
      <div class="form-group"><label class="form-label">Description</label><textarea name="description" class="form-control"></textarea></div>
      <div class="form-group"><label class="form-label">Specifications (Label: Value, one per line)</label><textarea name="specs" class="form-control" rows="4" placeholder="Material: Aircraft-grade Aluminium&#10;Sizes: 3FT, 4FT, 5FT"></textarea></div>
      <div class="form-group"><label class="form-label">Tags (comma separated)</label><input type="text" name="tags" class="form-control" placeholder="aluminium, safety, drill-pipe"></div>
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

    # Group
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

    # Top IPs
    ip_cnt: dict = {}
    for v in filtered: ip_cnt[v["ip"]] = ip_cnt.get(v["ip"],0)+1
    top_ips = sorted(ip_cnt.items(), key=lambda x:x[1], reverse=True)[:10]
    top_rows = "".join(
        f'<tr><td style="font-family:\'Space Mono\',monospace;font-size:.76rem">{ip}</td><td><strong style="color:var(--accent)">{c}</strong></td></tr>'
        for ip,c in top_ips
    )

    recent_rows = "".join(
        f'<tr><td style="font-family:\'Space Mono\',monospace;font-size:.76rem">{v["ip"]}</td><td style="color:var(--text2);font-size:.8rem">{v["time"][:19].replace("T"," ")}</td></tr>'
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
      <span style="font-family:'Space Mono',monospace;font-size:.6rem;color:var(--text3);letter-spacing:2px;margin-right:.3rem">PERIOD:</span>
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

    <!-- Bar Chart -->
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.5rem;margin-bottom:1.5rem">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
        <div style="font-family:'DM Serif Display',serif;font-size:1.1rem">{label} — Visit Trend</div>
        <span style="font-family:'Space Mono',monospace;font-size:.62rem;color:var(--text3)">{len(sorted_keys)} data point{'s' if len(sorted_keys)!=1 else ''}</span>
      </div>
      {f'<div class="bar-chart">{bars_html}</div>' if bars_html else '<div style="text-align:center;color:var(--text3);padding:3rem 0;font-size:.9rem">No data for this period</div>'}
    </div>

    <div class="grid-2">
      <div>
        <div style="font-family:'DM Serif Display',serif;font-size:1.1rem;margin-bottom:.8rem">Top Visitors</div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>IP Address</th><th>Visits</th></tr></thead>
            <tbody>{top_rows or '<tr><td colspan="2" style="text-align:center;color:var(--text3);padding:1.5rem">No data</td></tr>'}</tbody>
          </table>
        </div>
      </div>
      <div>
        <div style="font-family:'DM Serif Display',serif;font-size:1.1rem;margin-bottom:.8rem">Recent 50 Visits</div>
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


# ─── Redirect old /admin paths ─────────────────────────────────────────────────
@app.get("/admin/login")
async def _old1(): return RedirectResponse("/", status_code=302)
@app.get("/admin/dashboard")
async def _old2(): return RedirectResponse("/", status_code=302)
@app.get("/admin")
async def _old3(): return RedirectResponse("/", status_code=302)


# ─── Run ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("="*55)
    print("  Ketch-All Product Catalog — Premium Edition v2")
    print("  http://localhost:8000")
    print(f"  Admin: http://localhost:8000{ADMIN_ROUTE}/login")
    print("  Default login: admin / admin123")
    print("="*55)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
