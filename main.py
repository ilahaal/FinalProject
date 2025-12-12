from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from azure.cosmos import CosmosClient, exceptions
from jose import jwt, JWTError
import os
import uuid
from datetime import datetime, timedelta

# App branding
app = FastAPI(title="BrewHaven Café API", version="1.0.0")

BUILD_TIME = datetime.utcnow().isoformat()

# -------------------- CORS -------------------- #

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Cosmos DB -------------------- #

COSMOS_ENDPOINT = os.environ.get("COSMOS_ENDPOINT", "")
COSMOS_KEY = os.environ.get("COSMOS_KEY", "")
DATABASE_NAME = "cloudmart"  # same DB name as before

client = None
database = None
products_container = None
cart_container = None
orders_container = None


def init_cosmos():
    """
    Initialize Cosmos DB client and containers.
    If env vars are not set, the app still runs, but DB-dependent endpoints return empty data.
    """
    global client, database, products_container, cart_container, orders_container

    if not COSMOS_ENDPOINT or not COSMOS_KEY:
        # running without DB (local/dev mode)
        return

    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    database = client.get_database_client(DATABASE_NAME)
    products_container = database.get_container_client("products")
    cart_container = database.get_container_client("cart")
    orders_container = database.get_container_client("orders")

    # Seed data if necessary
    try:
        items = list(
            products_container.query_items(
                "SELECT * FROM c", enable_cross_partition_query=True
            )
        )
        if len(items) == 0:
            seed_products()
    except Exception:
        # if Cosmos is misconfigured, just skip seeding
        pass


def seed_products():
    """Seed BrewHaven coffee shop items into Cosmos DB 'products' container."""
    products = [
        {
            "id": "1",
            "name": "Espresso Shot",
            "description": "Rich, concentrated single shot of espresso brewed with freshly ground beans.",
            "category": "Coffee",
            "price": 2.75,
            "stock": 80,
            "image": "☕",
        },
        {
            "id": "2",
            "name": "Cappuccino",
            "description": "Double espresso with silky steamed milk and a cloud of microfoam.",
            "category": "Coffee",
            "price": 4.25,
            "stock": 60,
            "image": "🫖",
        },
        {
            "id": "3",
            "name": "Café Latte",
            "description": "Smooth espresso balanced with plenty of steamed milk and a light foam cap.",
            "category": "Coffee",
            "price": 4.45,
            "stock": 60,
            "image": "🥛",
        },
        {
            "id": "4",
            "name": "Mocha Latte",
            "description": "Espresso, steamed milk, and rich chocolate syrup topped with whipped cream.",
            "category": "Specialty Drinks",
            "price": 4.95,
            "stock": 50,
            "image": "🍫",
        },
        {
            "id": "5",
            "name": "Iced Caramel Latte",
            "description": "Chilled espresso over ice with milk and caramel drizzle.",
            "category": "Specialty Drinks",
            "price": 4.95,
            "stock": 55,
            "image": "🧋",
        },
        {
            "id": "6",
            "name": "Americano",
            "description": "Espresso topped with hot water for a smooth, long coffee.",
            "category": "Coffee",
            "price": 3.25,
            "stock": 70,
            "image": "☕",
        },
        {
            "id": "7",
            "name": "Butter Croissant",
            "description": "Flaky, buttery croissant baked fresh every morning.",
            "category": "Pastry",
            "price": 3.50,
            "stock": 40,
            "image": "🥐",
        },
        {
            "id": "8",
            "name": "Chocolate Croissant",
            "description": "Classic croissant filled with dark chocolate.",
            "category": "Pastry",
            "price": 3.95,
            "stock": 35,
            "image": "🥐",
        },
        {
            "id": "9",
            "name": "Blueberry Muffin",
            "description": "Soft muffin with juicy blueberries and a crumb topping.",
            "category": "Pastry",
            "price": 3.25,
            "stock": 45,
            "image": "🫐",
        },
        {
            "id": "10",
            "name": "Vanilla Bean Ice Cream",
            "description": "Creamy vanilla ice cream served in a cup.",
            "category": "Dessert",
            "price": 3.75,
            "stock": 30,
            "image": "🍨",
        },
        {
            "id": "11",
            "name": "Chocolate Fudge Ice Cream",
            "description": "Chocolate ice cream with fudge swirls.",
            "category": "Dessert",
            "price": 3.95,
            "stock": 30,
            "image": "🍨",
        },
        {
            "id": "12",
            "name": "Matcha Latte",
            "description": "Ceremonial-grade matcha whisked with steamed milk.",
            "category": "Specialty Drinks",
            "price": 4.95,
            "stock": 40,
            "image": "🍵",
        },
        {
            "id": "13",
            "name": "Hot Chocolate",
            "description": "Steamed milk with cocoa and whipped cream on top.",
            "category": "Specialty Drinks",
            "price": 3.95,
            "stock": 50,
            "image": "🍫",
        },
    ]
    for p in products:
        try:
            products_container.create_item(p)
        except exceptions.CosmosResourceExistsError:
            pass


@app.on_event("startup")
async def startup_event():
    init_cosmos()

# -------------------- JWT AUTH -------------------- #

DEMO_USERNAME = "barista"
DEMO_PASSWORD = "coffee123"

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "brewhaven-dev-secret-key")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


class LoginRequest(BaseModel):
    username: str
    password: str


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def get_current_user(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


class CartItem(BaseModel):
    product_id: str
    quantity: int = 1


DEFAULT_USER = "cafe_guest"

# -------------------- HTML FRONTEND -------------------- #

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>BrewHaven Café – Coffee & Treats</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
* { box-sizing:border-box; margin:0; padding:0; }

body {
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  min-height:100vh;
  background:
    radial-gradient(circle at top left, #f97316 0, transparent 55%),
    radial-gradient(circle at bottom right, #a855f7 0, transparent 55%),
    #1c1917;
  color:#111827;
}

/* Top bar */
.header {
  position:sticky;
  top:0;
  z-index:10;
  backdrop-filter: blur(16px);
  background:rgba(28,25,23,0.88);
  border-bottom:1px solid rgba(120,53,15,0.7);
  color:#f5f5f4;
  padding:14px 20px;
}
.header-content {
  max-width:1120px;
  margin:0 auto;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
}
.logo {
  display:flex;
  flex-direction:column;
  gap:2px;
}
.logo-main {
  font-size:22px;
  font-weight:800;
  letter-spacing:0.12em;
  text-transform:uppercase;
}
.logo-main span.cafe-name {
  color:#fed7aa;
}
.logo-main span.dot {
  color:#ea580c;
}
.logo-sub {
  font-size:12px;
  color:#e7e5e4;
}
.bean-badge {
  margin-left:2px;
  padding:3px 9px;
  border-radius:999px;
  font-size:11px;
  background:rgba(68,64,60,0.8);
  border:1px solid rgba(214,211,209,0.7);
}

/* Buttons */
.btn,
.cart-btn,
.btn-outline {
  font-size:13px;
  border-radius:999px;
  border:none;
  cursor:pointer;
  font-weight:500;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  gap:6px;
  transition:transform 0.08s ease, box-shadow 0.08s ease, background 0.12s ease;
}
.btn:active,
.cart-btn:active,
.btn-outline:active {
  transform:translateY(1px);
  box-shadow:none;
}
.btn-outline {
  padding:7px 12px;
  background:transparent;
  border:1px solid rgba(214,211,209,0.8);
  color:#f5f5f4;
}
.btn-outline:hover {
  background:rgba(68,64,60,0.8);
}
.cart-btn {
  background:linear-gradient(135deg,#f97316,#ea580c);
  color:#1c1917;
  padding:7px 14px;
  box-shadow:0 10px 20px rgba(194,65,12,0.6);
}
.cart-btn:hover {
  background:linear-gradient(135deg,#ea580c,#c2410c);
}
.cart-count {
  background:#f5f5f4;
  color:#c2410c;
  border-radius:999px;
  padding:1px 8px;
  font-size:11px;
  font-weight:700;
}

/* Main card */
.main {
  max-width:1120px;
  margin:24px auto 40px;
  padding:20px 18px 22px;
  border-radius:22px;
  background:radial-gradient(circle at top, rgba(250,250,249,0.12), transparent 55%) ,#1c1917;
  box-shadow:
    0 28px 70px rgba(15,23,42,0.85),
    0 0 0 1px rgba(68,64,60,0.85);
  color:#f5f5f4;
}
.main-header {
  display:flex;
  justify-content:space-between;
  align-items:flex-end;
  gap:16px;
}
.main-title h2 {
  font-size:20px;
  font-weight:600;
}
.main-title p {
  margin-top:4px;
  font-size:13px;
  color:#e7e5e4;
}
.status-box {
  font-size:11px;
  color:#d6d3d1;
  text-align:right;
}
small.build {
  display:block;
  margin-top:6px;
  font-size:11px;
  color:#a8a29e;
}

/* Filters */
.chip-row {
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  margin-top:16px;
}
.chip {
  padding:6px 12px;
  font-size:12px;
  border-radius:999px;
  border:1px solid rgba(120,53,15,0.8);
  background:rgba(41,37,36,0.98);
  color:#f5f5f4;
  cursor:pointer;
}
.chip.active {
  background:#fed7aa;
  color:#431407;
  border-color:transparent;
}

/* Search */
.search-row {
  margin-top:12px;
}
.search-input {
  width:100%;
  padding:8px 11px;
  border-radius:11px;
  border:1px solid rgba(87,83,78,0.9);
  background:#0c0a09;
  color:#f5f5f4;
  font-size:13px;
}

/* Product grid */
.product-grid {
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));
  gap:16px;
  margin-top:18px;
}
.card {
  border-radius:18px;
  padding:14px 14px 16px;
  background:
    radial-gradient(circle at top left, rgba(250,204,21,0.18), transparent 55%),
    radial-gradient(circle at bottom right, rgba(248,250,252,0.08), transparent 55%),
    #292524;
  border:1px solid rgba(87,83,78,0.9);
  box-shadow:0 18px 40px rgba(0,0,0,0.85);
}
.card-header {
  display:flex;
  justify-content:space-between;
  align-items:center;
}
.emoji {
  font-size:30px;
}
.badge {
  font-size:11px;
  padding:3px 9px;
  border-radius:999px;
  background:rgba(12,10,9,0.9);
  color:#fed7aa;
}
.card-title {
  margin-top:8px;
  font-weight:600;
  color:#fefce8;
}
.card-desc {
  margin-top:6px;
  font-size:13px;
  color:#e7e5e4;
}
.card-footer {
  margin-top:10px;
  display:flex;
  align-items:center;
  justify-content:space-between;
}
.price {
  font-weight:700;
  color:#facc15;
}
.stock {
  font-size:11px;
  color:#a8a29e;
}
.btn-primary {
  padding:6px 10px;
  border-radius:999px;
  border:none;
  font-size:13px;
  cursor:pointer;
  font-weight:500;
  background:linear-gradient(135deg,#f97316,#ea580c);
  color:#1c1917;
  box-shadow:0 10px 24px rgba(234,88,12,0.7);
}
.btn-primary:hover {
  background:linear-gradient(135deg,#ea580c,#c2410c);
}

/* Modals */
.modal-backdrop {
  position:fixed;
  inset:0;
  background:rgba(12,10,9,0.82);
  display:none;
  align-items:flex-start;
  justify-content:center;
  padding-top:80px;
  z-index:50;
}
.modal {
  background:#0c0a09;
  border-radius:18px;
  padding:18px;
  width:100%;
  max-width:420px;
  border:1px solid rgba(87,83,78,0.9);
  box-shadow:0 24px 60px rgba(0,0,0,0.9);
}
.modal-header {
  display:flex;
  justify-content:space-between;
  align-items:center;
}
.modal-header h3 {
  color:#f5f5f4;
  font-weight:600;
}
.close-btn {
  width:22px;
  height:22px;
  border-radius:999px;
  border:none;
  background:#1c1917;
  color:#f5f5f4;
  cursor:pointer;
}

/* Cart table */
.cart-head-row {
  display:grid;
  grid-template-columns:1fr auto auto auto;
  font-size:12px;
  color:#d6d3d1;
  margin-top:12px;
  padding-bottom:6px;
  border-bottom:1px solid rgba(87,83,78,0.9);
}
.cart-items {
  margin-top:10px;
  max-height:300px;
  overflow-y:auto;
}
.cart-item {
  display:grid;
  grid-template-columns:1fr auto auto auto;
  align-items:center;
  gap:12px;
  padding:10px 0;
  border-bottom:1px solid rgba(63,63,70,0.8);
}
.cart-product {
  display:flex;
  flex-direction:column;
}
.cart-item-price {
  min-width:72px;
  text-align:right;
  color:#f5f5f4;
}
.cart-qty-controls {
  display:flex;
  align-items:center;
  gap:6px;
}
.cart-item-qty {
  min-width:20px;
  text-align:center;
  display:inline-block;
}
.qty-btn {
  width:22px;
  height:22px;
  border-radius:999px;
  border:none;
  background:#1c1917;
  color:#f5f5f4;
  cursor:pointer;
}
.cart-total-row {
  margin-top:10px;
  display:flex;
  justify-content:space-between;
  font-weight:600;
}
.cart-total-row span {
  color:#fef9c3;
}
#cartTotal {
  color:#facc15;
}

/* Toast */
.toast {
  position:fixed;
  bottom:18px;
  right:18px;
  padding:10px 14px;
  border-radius:10px;
  background:#22c55e;
  color:#052e16;
  font-size:13px;
  display:none;
  z-index:60;
}
.toast.error {
  background:#f97373;
  color:#450a0a;
}

/* Login form */
.login-note {
  margin-top:8px;
  font-size:11px;
  color:#a8a29e;
}
.input-field {
  width:100%;
  margin-top:4px;
  padding:6px 8px;
  border-radius:9px;
  border:1px solid rgba(87,83,78,0.9);
  background:#0c0a09;
  color:#f5f5f4;
  font-size:13px;
}
.label {
  font-size:12px;
  color:#d6d3d1;
}
</style>
</head>
<body>
<header class="header">
  <div class="header-content">
    <div class="logo">
      <div class="logo-main">
        <span class="cafe-name">BREWHAVEN</span><span class="dot">·CAFÉ</span>
        <span class="bean-badge">☕ Single-origin & fresh pastry</span>
      </div>
      <div class="logo-sub">Warm drinks, sweet bites, and a cloud-backed checkout.</div>
    </div>
    <div style="display:flex;align-items:center;gap:8px;">
      <button class="btn-outline" id="loginBtn" onclick="openLogin()">Login</button>
      <button class="cart-btn" onclick="openCart()">🧺 Basket <span id="cartCount" class="cart-count">0</span></button>
    </div>
  </div>
</header>

<main class="main">
  <div class="main-header">
    <div class="main-title">
      <h2>Menu</h2>
      <p>Browse handcrafted coffees, pastries, and desserts – add to your basket and confirm your order.</p>
    </div>
    <div class="status-box">
      <div id="healthStatus">Checking café systems…</div>
      <small class="build">Build timestamp: <span id="buildTime"></span></small>
    </div>
  </div>

  <div class="chip-row" id="categoryChips"></div>

  <div class="search-row">
    <input id="searchBox" class="search-input" type="text"
      placeholder="Search by drink, pastry, or category…"
      oninput="searchProducts()" />
  </div>

  <div class="product-grid" id="productGrid"></div>
</main>

<!-- CART MODAL -->
<div class="modal-backdrop" id="cartModal">
  <div class="modal">
    <div class="modal-header">
      <h3>Your Basket</h3>
      <button class="close-btn" onclick="closeCart()">✕</button>
    </div>

    <div class="cart-head-row">
      <span>Item</span>
      <span>Qty</span>
      <span>Total</span>
      <span></span>
    </div>

    <div class="cart-items" id="cartItems"></div>

    <div class="cart-total-row">
      <span>Order total</span>
      <span id="cartTotal">$0.00</span>
    </div>

    <div style="margin-top:12px;display:flex;justify-content:flex-end;gap:8px;">
      <button class="btn" onclick="closeCart()">Close</button>
      <button class="btn btn-primary" onclick="placeOrder()">Place order</button>
    </div>
  </div>
</div>

<!-- LOGIN MODAL -->
<div class="modal-backdrop" id="loginModal">
  <div class="modal">
    <div class="modal-header">
      <h3>Barista Login</h3>
      <button class="close-btn" onclick="closeLogin()">✕</button>
    </div>
    <form onsubmit="performLogin(event)" style="margin-top:12px;display:flex;flex-direction:column;gap:8px;">
      <div>
        <label class="label">Username</label>
        <input id="loginUsername" type="text" value="barista" class="input-field">
      </div>
      <div>
        <label class="label">Password</label>
        <input id="loginPassword" type="password" value="coffee123" class="input-field">
      </div>
      <div style="margin-top:10px;display:flex;justify-content:flex-end;gap:8px;">
        <button type="button" class="btn" onclick="closeLogin()">Cancel</button>
        <button type="submit" class="btn btn-primary">Login</button>
      </div>
    </form>
    <p class="login-note">Demo credentials: barista / coffee123</p>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let products = [];
let categories = [];
let cart = [];
let authToken = null;

async function fetchJSON(url, options) {
  const opts = options || {};
  opts.headers = opts.headers || {};

  if (authToken) {
    opts.headers["Authorization"] = "Bearer " + authToken;
  }

  const res = await fetch(url, opts);
  if (!res.ok) {
    throw new Error("HTTP " + res.status);
  }
  return res.json();
}

async function loadHealth() {
  try {
    const data = await fetchJSON("/health");
    document.getElementById("healthStatus").textContent =
      data.status === "healthy"
        ? "Status: brewing fine (" + data.db_status + ")"
        : "Status: " + data.status;
    document.getElementById("buildTime").textContent = data.build_time || "";
  } catch (e) {
    document.getElementById("healthStatus").textContent = "Status: unreachable";
  }
}

function updateAuthUI() {
  const btn = document.getElementById("loginBtn");
  if (!btn) return;
  if (authToken) {
    btn.textContent = "Logout";
  } else {
    btn.textContent = "Login";
  }
}

async function init() {
  authToken = localStorage.getItem("brewhaven_token") || null;
  updateAuthUI();

  await loadHealth();
  try {
    products = await fetchJSON("/api/v1/products");
    categories = await fetchJSON("/api/v1/categories");
    if (authToken) {
      try {
        cart = await fetchJSON("/api/v1/cart");
      } catch (e) {
        cart = [];
      }
    } else {
      cart = [];
    }
  } catch (e) {
    showToast("Failed to load menu from API", true);
  }
  renderCategories();
  renderProducts();
  updateCartCount();
}

function renderCategories() {
  const container = document.getElementById("categoryChips");
  container.innerHTML = "";
  const allChip = document.createElement("button");
  allChip.className = "chip active";
  allChip.textContent = "All items";
  allChip.onclick = () => filterCategory(null);
  container.appendChild(allChip);

  categories.forEach(cat => {
    const chip = document.createElement("button");
    chip.className = "chip";
    chip.textContent = cat;
    chip.onclick = () => filterCategory(cat);
    container.appendChild(chip);
  });
}

function renderProducts(filtered) {
  const grid = document.getElementById("productGrid");
  grid.innerHTML = "";
  const list = filtered || products;

  list.forEach(p => {
    const card = document.createElement("article");
    card.className = "card";

    card.innerHTML = `
      <div class="card-header">
        <div class="emoji">${p.image || "☕"}</div>
        <span class="badge">${p.category}</span>
      </div>
      <div class="card-title">${p.name}</div>
      <div class="card-desc">${p.description}</div>
      <div class="card-footer">
        <div>
          <div class="price">$${Number(p.price).toFixed(2)}</div>
          <div class="stock">${p.stock} available</div>
        </div>
        <button class="btn-primary" data-id="${p.id}">Add to basket</button>
      </div>
    `;

    const btn = card.querySelector("button");
    btn.onclick = () => addToCart(p.id, 1);

    grid.appendChild(card);
  });
}

function filterCategory(category) {
  const chips = document.querySelectorAll(".chip");
  chips.forEach(c => c.classList.remove("active"));
  if (!category) {
    chips[0].classList.add("active");
    renderProducts();
    return;
  }
  chips.forEach(c => {
    if (c.textContent === category) c.classList.add("active");
  });
  renderProducts(products.filter(p => p.category === category));
}

async function searchProducts() {
  const box = document.getElementById("searchBox");
  if (!box) return;
  const q = box.value.trim();

  if (q.length === 0) {
    const activeChip = document.querySelector(".chip.active");
    if (!activeChip || activeChip.textContent === "All items") {
      renderProducts();
    } else {
      const cat = activeChip.textContent;
      renderProducts(products.filter(p => p.category === cat));
    }
    return;
  }

  try {
    const results = await fetchJSON("/api/v1/search?q=" + encodeURIComponent(q));
    renderProducts(results);
  } catch (e) {
    showToast("Search failed", true);
  }
}

function updateCartCount() {
  document.getElementById("cartCount").textContent = cart.length;
}

function requireLogin() {
  showToast("Login to manage basket and orders", true);
  openLogin();
}

function openCart() {
  if (!authToken) {
    requireLogin();
    return;
  }
  renderCart();
  document.getElementById("cartModal").style.display = "flex";
}

function closeCart() {
  document.getElementById("cartModal").style.display = "none";
}

function renderCart() {
  const container = document.getElementById("cartItems");
  container.innerHTML = "";

  if (!cart || cart.length === 0) {
    container.innerHTML = '<p style="color:#d6d3d1;font-size:13px;">Your basket is empty.</p>';
    document.getElementById("cartTotal").innerText = "$0.00";
    return;
  }

  let total = 0;

  cart.forEach(item => {
    const price = Number(item.price) || 0;
    const qty = Number(item.quantity) || 0;
    const lineTotal = price * qty;
    total += lineTotal;

    const row = document.createElement("div");
    row.className = "cart-item";

    row.innerHTML = `
      <div class="cart-product">
        <div>${item.name}</div>
        <div style="font-size:12px;color:#a8a29e;">$${price.toFixed(2)} each</div>
      </div>

      <div class="cart-qty-controls">
        <button class="qty-btn dec">-</button>
        <span class="cart-item-qty">${qty}</span>
        <button class="qty-btn inc">+</button>
      </div>

      <div class="cart-item-price">$${lineTotal.toFixed(2)}</div>

      <button class="qty-btn remove-btn">✕</button>
    `;

    row.querySelector(".dec").onclick = () => {
      if (qty <= 1) {
        removeFromCart(item.id);
      } else {
        updateCartQuantity(item.id, qty - 1);
      }
    };

    row.querySelector(".inc").onclick = () => {
      updateCartQuantity(item.id, qty + 1);
    };

    row.querySelector(".remove-btn").onclick = () => {
      removeFromCart(item.id);
    };

    container.appendChild(row);
  });

  document.getElementById("cartTotal").innerText = `$${total.toFixed(2)}`;
}

async function addToCart(productId, quantity) {
  if (!authToken) {
    requireLogin();
    return;
  }
  try {
    await fetchJSON("/api/v1/cart/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: productId, quantity }),
    });
    cart = await fetchJSON("/api/v1/cart");
    updateCartCount();
    showToast("Item added to basket");
  } catch (e) {
    showToast("Failed to update basket", true);
  }
}

async function updateCartQuantity(productId, quantity) {
  if (!authToken) {
    requireLogin();
    return;
  }
  await addToCart(productId, quantity);
  renderCart();
}

async function removeFromCart(productId) {
  if (!authToken) {
    requireLogin();
    return;
  }
  try {
    await fetchJSON("/api/v1/cart/items/" + productId, {
      method: "DELETE",
    });
    cart = await fetchJSON("/api/v1/cart");
    updateCartCount();
    renderCart();
    showToast("Item removed");
  } catch (e) {
    showToast("Failed to remove item", true);
  }
}

async function placeOrder() {
  if (!authToken) {
    requireLogin();
    return;
  }
  if (cart.length === 0) {
    showToast("Basket is empty", true);
    return;
  }
  try {
    const order = await fetchJSON("/api/v1/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    cart = [];
    updateCartCount();
    closeCart();
    showToast("Order placed – enjoy your treats!");
    console.log("Order:", order);
  } catch (e) {
    showToast("Failed to place order", true);
  }
}

function openLogin() {
  if (authToken) {
    authToken = null;
    localStorage.removeItem("brewhaven_token");
    cart = [];
    updateCartCount();
    updateAuthUI();
    showToast("Logged out");
    return;
  }
  document.getElementById("loginModal").style.display = "flex";
}

function closeLogin() {
  document.getElementById("loginModal").style.display = "none";
}

async function performLogin(event) {
  event.preventDefault();
  const u = document.getElementById("loginUsername").value.trim();
  const p = document.getElementById("loginPassword").value.trim();

  if (!u || !p) {
    showToast("Enter username and password", true);
    return;
  }

  try {
    const res = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p }),
    });

    if (!res.ok) {
      showToast("Invalid credentials", true);
      return;
    }

    const data = await res.json();
    authToken = data.access_token;
    localStorage.setItem("brewhaven_token", authToken);
    updateAuthUI();
    closeLogin();

    try {
      cart = await fetchJSON("/api/v1/cart");
      updateCartCount();
    } catch (e) {
      cart = [];
    }

    showToast("Logged in");
  } catch (e) {
    showToast("Sign-in failed", true);
  }
}

let toastTimeout;
function showToast(message, isError) {
  const t = document.getElementById("toast");
  t.textContent = message;
  t.classList.toggle("error", !!isError);
  t.style.display = "block";
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => (t.style.display = "none"), 3000);
}

init();
</script>
</body>
</html>
"""

# -------------------- ROUTES -------------------- #

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_TEMPLATE


@app.get("/health")
def health():
    db_status = "connected" if client else "disconnected"
    return {
        "status": "healthy",
        "service": "brewhaven-cafe-api",
        "version": "1.0.0",
        "build_time": BUILD_TIME,
        "database": "cosmos-db",
        "db_status": db_status,
        "deployed_via": "aci-container",
    }


@app.post("/auth/login")
def auth_login(body: LoginRequest):
    if body.username != DEMO_USERNAME or body.password != DEMO_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": body.username})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/v1/products")
def list_products(category: str | None = None):
    if not products_container:
        # running without DB
        return []
    try:
        if category:
            query = "SELECT * FROM c WHERE c.category = @category"
            items = list(
                products_container.query_items(
                    query,
                    parameters=[{"name": "@category", "value": category}],
                    enable_cross_partition_query=True,
                )
            )
        else:
            items = list(
                products_container.query_items(
                    "SELECT * FROM c", enable_cross_partition_query=True
                )
            )
        return items
    except Exception:
        return []


@app.get("/api/v1/search")
def search_products(q: str):
    """
    Simple search endpoint: searches in product name and category.
    """
    if not products_container:
        return []
    try:
        query = (
            "SELECT * FROM c "
            "WHERE CONTAINS(c.name, @q) "
            "OR CONTAINS(c.category, @q)"
        )
        items = list(
            products_container.query_items(
                query,
                parameters=[{"name": "@q", "value": q}],
                enable_cross_partition_query=True,
            )
        )
        return items
    except Exception:
        return []


@app.get("/api/v1/products/{product_id}")
def get_product(product_id: str):
    if not products_container:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        items = list(
            products_container.query_items(
                "SELECT * FROM c WHERE c.id = @id",
                parameters=[{"name": "@id", "value": product_id}],
                enable_cross_partition_query=True,
            )
        )
        if items:
            return items[0]
        raise HTTPException(status_code=404, detail="Product not found")
    except exceptions.CosmosHttpResponseError:
        raise HTTPException(status_code=404, detail="Product not found")


@app.get("/api/v1/categories")
def get_categories():
    if not products_container:
        return []
    try:
        items = list(
            products_container.query_items(
                "SELECT DISTINCT c.category FROM c",
                enable_cross_partition_query=True,
            )
        )
        return [item["category"] for item in items]
    except Exception:
        return []


@app.get("/api/v1/cart")
def get_cart(current_user: str = Depends(get_current_user)):
    if not cart_container or not products_container:
        return []

    try:
        items = list(
            cart_container.query_items(
                "SELECT * FROM c WHERE c.user_id = @user_id",
                parameters=[{"name": "@user_id", "value": DEFAULT_USER}],
                enable_cross_partition_query=True,
            )
        )

        enriched_cart = []
        for item in items:
            product_items = list(
                products_container.query_items(
                    "SELECT * FROM c WHERE c.id = @pid",
                    parameters=[{"name": "@pid", "value": item["product_id"]}],
                    enable_cross_partition_query=True,
                )
            )
            if not product_items:
                continue

            product = product_items[0]
            enriched_cart.append(
                {
                    "id": product["id"],
                    "name": product["name"],
                    "price": product["price"],
                    "quantity": item["quantity"],
                    "image": product.get("image", "☕"),
                    "category": product.get("category", "Menu"),
                }
            )

        return enriched_cart

    except Exception as e:
        return {"error": str(e)}


@app.post("/api/v1/cart/items")
def add_to_cart(item: CartItem, current_user: str = Depends(get_current_user)):
    if not cart_container:
        return {"error": "Database not available"}
    try:
        existing = list(
            cart_container.query_items(
                "SELECT * FROM c WHERE c.user_id = @user_id AND c.product_id = @product_id",
                parameters=[
                    {"name": "@user_id", "value": DEFAULT_USER},
                    {"name": "@product_id", "value": item.product_id},
                ],
                enable_cross_partition_query=True,
            )
        )
        if existing:
            cart_item = existing[0]
            cart_item["quantity"] = item.quantity
            cart_container.upsert_item(cart_item)
        else:
            cart_item = {
                "id": str(uuid.uuid4()),
                "user_id": DEFAULT_USER,
                "product_id": item.product_id,
                "quantity": item.quantity,
            }
            cart_container.create_item(cart_item)
        return {"message": "Saved successfully"}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/v1/cart/items/{product_id}")
def remove_from_cart(product_id: str, current_user: str = Depends(get_current_user)):
    if not cart_container:
        return {"error": "Database not available"}
    try:
        items = list(
            cart_container.query_items(
                "SELECT * FROM c WHERE c.user_id = @user_id AND c.product_id = @product_id",
                parameters=[
                    {"name": "@user_id", "value": DEFAULT_USER},
                    {"name": "@product_id", "value": product_id},
                ],
                enable_cross_partition_query=True,
            )
        )
        for item in items:
            cart_container.delete_item(item["id"], partition_key=DEFAULT_USER)
        return {"message": "Removed successfully"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/v1/orders")
def create_order(current_user: str = Depends(get_current_user)):
    if not orders_container or not cart_container:
        return {"error": "Database not available"}
    try:
        cart_items = list(
            cart_container.query_items(
                "SELECT * FROM c WHERE c.user_id = @user_id",
                parameters=[{"name": "@user_id", "value": DEFAULT_USER}],
                enable_cross_partition_query=True,
            )
        )
        order = {
            "id": str(uuid.uuid4()),
            "user_id": DEFAULT_USER,
            "items": [
                {"product_id": i["product_id"], "quantity": i["quantity"]}
                for i in cart_items
            ],
            "status": "confirmed",
            "created_at": datetime.utcnow().isoformat(),
        }
        orders_container.create_item(order)
        for item in cart_items:
            cart_container.delete_item(item["id"], partition_key=DEFAULT_USER)
        return order
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/v1/orders")
def get_orders(current_user: str = Depends(get_current_user)):
    if not orders_container:
        return []
    try:
        items = list(
            orders_container.query_items(
                "SELECT * FROM c WHERE c.user_id = @user_id",
                parameters=[{"name": "@user_id", "value": DEFAULT_USER}],
                enable_cross_partition_query=True,
            )
        )
        return items
    except Exception:
        return []

