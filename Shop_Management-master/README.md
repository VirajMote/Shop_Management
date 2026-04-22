# 🛍 Smart Mall — Inventory & Sales Management System

A full-stack web application for managing mall/shop inventory and sales in real-time.

---

## 🗂 Folder Structure

```
smart-mall/
├── backend/
│   ├── main.py          # FastAPI app — all API routes
│   ├── database.py      # SQLAlchemy models + DB connection
│   ├── auth.py          # JWT authentication + bcrypt hashing
│   ├── schemas.py       # Pydantic request/response models
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html       # Login page
│   └── dashboard.html   # Main application (all modules)
├── schema.sql           # MySQL schema (triggers, indexes, stored procedures)
├── docker-compose.yml   # Spins up MySQL + FastAPI together
└── README.md
```

---

## ⚡ Quick Start (Docker — Recommended)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### Steps

```bash
# 1. Clone / unzip the project
cd smart-mall

# 2. Start the entire stack (MySQL + FastAPI backend)
docker compose up --build

# Wait ~30 seconds for MySQL to initialize on first run.
# You'll see: "Application startup complete."
```

```bash
# 3. Open the frontend
# Just open frontend/index.html in your browser
# (Double-click the file OR drag into Chrome)
```

### Login
- **Email:** admin@gmail.com
- **Password:** admin123

---

## 🌐 API Base URL

Once running: `http://localhost:8000`

Interactive API docs: `http://localhost:8000/docs`

---

## 🔑 Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login, returns JWT token |
| GET | `/api/dashboard` | Dashboard stats & charts data |
| GET | `/api/products` | List products (search/filter) |
| POST | `/api/products` | Add new product |
| PUT | `/api/products/{id}` | Edit product |
| DELETE | `/api/products/{id}` | Delete product |
| POST | `/api/sales` | Create sale (deducts stock) |
| GET | `/api/sales` | Transaction history |
| GET | `/api/sales/{id}/invoice` | Download PDF invoice |
| GET | `/api/reports/export` | Export Excel report |
| WS | `/ws/alerts` | Real-time stock alerts |

---

## 🧠 SQL Features Used

### Tables
- `users` — Admin authentication
- `products` — Product catalog with stock
- `sales` — Sale transactions
- `sale_items` — Line items per sale (supports multi-product billing)

### Triggers
```sql
-- trg_reduce_stock: auto-deducts stock after a sale item is inserted
-- trg_check_stock_before_sale: prevents overselling (raises error if stock insufficient)
```

### Indexes
```sql
CREATE INDEX idx_product_name ON products(name);
CREATE INDEX idx_product_category ON products(category);
CREATE INDEX idx_sale_items_sale_id ON sale_items(sale_id);
```

### Stored Procedure
```sql
CALL create_sale(total_amount, @sale_id);
-- Creates the sale header atomically, returns new sale ID
```

### Constraints
```sql
stock_quantity INT CHECK (stock_quantity >= 0)  -- prevents negative stock
price DECIMAL CHECK (price >= 0)
FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔐 Auth | JWT-based login, bcrypt hashed passwords |
| 📊 Dashboard | Stats cards + 7-day sales chart + category donut chart |
| 📦 Products | Add/Edit/Delete, search, filter by category/stock |
| 🗃️ Inventory | Stock bar indicators, quick stock addition |
| 🧾 Billing | Multi-product cart, auto total calculation |
| 📄 PDF Invoice | Server-side generated, downloadable |
| 📋 History | Filter by date range |
| 🔔 Alerts | Low/out-of-stock alerts + WebSocket real-time broadcast |
| ⬇ Excel Export | Full products + sales report |
| 🌐 WebSockets | Real-time stock alerts after each sale |

---

## 🛑 Stopping

```bash
docker compose down        # stop containers
docker compose down -v     # stop + delete database
```

---

## 🔧 Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy
- **Database:** MySQL 8.0 (Docker)
- **Auth:** JWT (python-jose), bcrypt (passlib)
- **PDF:** ReportLab
- **Excel:** openpyxl
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Charts:** Chart.js 4
- **Real-time:** WebSockets (FastAPI native)
