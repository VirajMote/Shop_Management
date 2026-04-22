"""
main.py — FastAPI application
All routes: auth, products, sales, dashboard, reports
"""

import os, io, json
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import (
    FastAPI, Depends, HTTPException, status,
    UploadFile, File, Form, WebSocket, WebSocketDisconnect
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text

import openpyxl
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from database import engine, Base, get_db, Product, Sale, SaleItem, User
from auth import (
    hash_password, verify_password,
    create_access_token, get_current_user
)
from schemas import (
    LoginRequest, TokenResponse,
    ProductCreate, ProductUpdate, ProductOut,
    SaleCreate, SaleOut, SaleItemOut,
    DashboardStats
)

# ── App Setup ─────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Mall API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

LOW_STOCK_THRESHOLD = 10

# ── WebSocket manager for real-time alerts ────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, msg: dict):
        for ws in self.active:
            try:
                await ws.send_json(msg)
            except:
                pass

manager = ConnectionManager()


# ── WebSocket endpoint ────────────────────────────────────────
@app.websocket("/ws/alerts")
async def alerts_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ══════════════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token({"sub": user.email, "role": user.role, "id": user.id})
    return {"access_token": token, "token_type": "bearer", "role": user.role}


# ══════════════════════════════════════════════════════════════
# DASHBOARD ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/dashboard", response_model=DashboardStats)
def get_dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    total_products = db.query(Product).count()
    total_stock    = db.query(func.sum(Product.stock_quantity)).scalar() or 0
    low_stock_count = db.query(Product).filter(
        Product.stock_quantity > 0,
        Product.stock_quantity <= LOW_STOCK_THRESHOLD
    ).count()

    today = date.today()
    sales_today = db.query(func.sum(Sale.total_amount)).filter(
        func.date(Sale.created_at) == today
    ).scalar() or Decimal("0")

    # Sales for last 7 days
    sales_7 = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        amt = db.query(func.sum(Sale.total_amount)).filter(
            func.date(Sale.created_at) == d
        ).scalar() or 0
        sales_7.append({"date": d.strftime("%b %d"), "amount": float(amt)})

    # Top categories by revenue
    top_cats = db.execute(text("""
        SELECT p.category, SUM(si.quantity * si.price) as revenue
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        GROUP BY p.category
        ORDER BY revenue DESC
        LIMIT 5
    """)).fetchall()
    top_categories = [{"category": r[0], "revenue": float(r[1])} for r in top_cats]

    return DashboardStats(
        total_products=total_products,
        total_stock=int(total_stock),
        sales_today=sales_today,
        low_stock_count=low_stock_count,
        sales_last_7_days=sales_7,
        top_categories=top_categories,
    )


# ══════════════════════════════════════════════════════════════
# PRODUCT ROUTES
# ══════════════════════════════════════════════════════════════

@app.get("/api/products", response_model=List[ProductOut])
def list_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    stock_status: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    q = db.query(Product)
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))
    if category:
        q = q.filter(Product.category == category)
    if stock_status == "in_stock":
        q = q.filter(Product.stock_quantity > LOW_STOCK_THRESHOLD)
    elif stock_status == "low_stock":
        q = q.filter(Product.stock_quantity > 0, Product.stock_quantity <= LOW_STOCK_THRESHOLD)
    elif stock_status == "out_of_stock":
        q = q.filter(Product.stock_quantity == 0)
    return q.order_by(Product.created_at.desc()).all()


@app.post("/api/products", response_model=ProductOut)
def create_product(
    name: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    stock_quantity: int = Form(...),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    image_url = None
    if image and image.filename:
        ext = image.filename.split(".")[-1]
        filename = f"{datetime.now().timestamp()}_{image.filename}"
        path = os.path.join(UPLOAD_DIR, filename)
        with open(path, "wb") as f:
            f.write(image.file.read())
        image_url = f"/uploads/{filename}"

    product = Product(
        name=name, category=category,
        price=price, stock_quantity=stock_quantity,
        image_url=image_url
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.put("/api/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@app.delete("/api/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}


@app.get("/api/products/categories")
def get_categories(db: Session = Depends(get_db), user=Depends(get_current_user)):
    cats = db.query(Product.category).distinct().all()
    return [c[0] for c in cats]


# ══════════════════════════════════════════════════════════════
# SALES ROUTES
# ══════════════════════════════════════════════════════════════

@app.post("/api/sales", response_model=SaleOut)
async def create_sale(
    payload: SaleCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="No items in sale")

    total = Decimal("0")
    item_data = []

    # Validate stock before creating sale
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if product.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.name}'. Available: {product.stock_quantity}"
            )
        subtotal = Decimal(str(product.price)) * item.quantity
        total += subtotal
        item_data.append((product, item.quantity, product.price))

    # Use stored procedure logic — create sale header first
    sale = Sale(total_amount=total)
    db.add(sale)
    db.flush()  # get sale.id without committing

    # Insert sale items (MySQL TRIGGER will auto-deduct stock)
    for product, qty, price in item_data:
        si = SaleItem(
            sale_id=sale.id,
            product_id=product.id,
            quantity=qty,
            price=price
        )
        db.add(si)
        # Also manually update (in case running without MySQL triggers in dev)
        product.stock_quantity -= qty

    db.commit()
    db.refresh(sale)

    # Broadcast low-stock alerts via WebSocket
    low_stock_items = db.query(Product).filter(
        Product.stock_quantity <= LOW_STOCK_THRESHOLD,
        Product.stock_quantity > 0
    ).all()
    out_of_stock = db.query(Product).filter(Product.stock_quantity == 0).all()

    if low_stock_items or out_of_stock:
        await manager.broadcast({
            "type": "stock_alert",
            "low_stock": [{"id": p.id, "name": p.name, "qty": p.stock_quantity} for p in low_stock_items],
            "out_of_stock": [{"id": p.id, "name": p.name} for p in out_of_stock],
        })

    # Build response with product names
    items_out = []
    for si in sale.items:
        items_out.append(SaleItemOut(
            id=si.id,
            product_id=si.product_id,
            product_name=si.product.name,
            quantity=si.quantity,
            price=si.price,
        ))

    return SaleOut(
        id=sale.id,
        total_amount=sale.total_amount,
        created_at=sale.created_at,
        items=items_out,
    )


@app.get("/api/sales", response_model=List[SaleOut])
def list_sales(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    q = db.query(Sale)
    if date_from:
        q = q.filter(func.date(Sale.created_at) >= date_from)
    if date_to:
        q = q.filter(func.date(Sale.created_at) <= date_to)
    sales = q.order_by(Sale.created_at.desc()).all()

    result = []
    for sale in sales:
        items_out = [
            SaleItemOut(
                id=si.id,
                product_id=si.product_id,
                product_name=si.product.name,
                quantity=si.quantity,
                price=si.price,
            )
            for si in sale.items
        ]
        result.append(SaleOut(
            id=sale.id,
            total_amount=sale.total_amount,
            created_at=sale.created_at,
            items=items_out,
        ))
    return result


# ══════════════════════════════════════════════════════════════
# PDF INVOICE GENERATION
# ══════════════════════════════════════════════════════════════

@app.get("/api/sales/{sale_id}/invoice")
def generate_invoice(
    sale_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontSize=22, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#4f46e5'), spaceAfter=6)
    subtitle_style = ParagraphStyle('Sub', fontSize=10, textColor=colors.gray)
    normal = styles['Normal']

    elements = []
    elements.append(Paragraph("🛍 Smart Mall", title_style))
    elements.append(Paragraph("Inventory & Sales Management System", subtitle_style))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(f"<b>INVOICE #SM-{sale.id:04d}</b>", styles['Heading2']))
    elements.append(Paragraph(f"Date: {sale.created_at.strftime('%d %B %Y, %I:%M %p')}", normal))
    elements.append(Spacer(1, 0.5*cm))

    # Table
    table_data = [["#", "Product", "Qty", "Unit Price", "Subtotal"]]
    for i, si in enumerate(sale.items, 1):
        subtotal = float(si.price) * si.quantity
        table_data.append([
            str(i),
            si.product.name,
            str(si.quantity),
            f"₹{float(si.price):,.2f}",
            f"₹{subtotal:,.2f}",
        ])
    table_data.append(["", "", "", "TOTAL", f"₹{float(sale.total_amount):,.2f}"])

    t = Table(table_data, colWidths=[1*cm, 7*cm, 2*cm, 3.5*cm, 3.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 11),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f5f3ff')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fef3c7')),
        ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID',       (0, 0), (-1, -2), 0.5, colors.HexColor('#e5e7eb')),
        ('BOX',        (0, 0), (-1, -1), 1, colors.HexColor('#4f46e5')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph("Thank you for shopping at Smart Mall!", subtitle_style))

    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{sale_id}.pdf"}
    )


# ══════════════════════════════════════════════════════════════
# EXCEL EXPORT
# ══════════════════════════════════════════════════════════════

@app.get("/api/reports/export")
def export_excel(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    wb = openpyxl.Workbook()

    # Sheet 1: Products
    ws1 = wb.active
    ws1.title = "Products"
    ws1.append(["ID", "Name", "Category", "Price", "Stock", "Status", "Created"])
    for p in db.query(Product).all():
        status = "Out of Stock" if p.stock_quantity == 0 else ("Low Stock" if p.stock_quantity <= LOW_STOCK_THRESHOLD else "In Stock")
        ws1.append([p.id, p.name, p.category, float(p.price), p.stock_quantity, status, str(p.created_at)])

    # Sheet 2: Sales
    ws2 = wb.create_sheet("Sales")
    ws2.append(["Sale ID", "Product", "Quantity", "Price", "Subtotal", "Total", "Date"])
    for sale in db.query(Sale).order_by(Sale.created_at.desc()).all():
        for si in sale.items:
            ws2.append([
                sale.id, si.product.name, si.quantity,
                float(si.price), float(si.price) * si.quantity,
                float(sale.total_amount), str(sale.created_at)
            ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=smart_mall_report.xlsx"}
    )


# ── Health check ──────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "app": "Smart Mall API"}
