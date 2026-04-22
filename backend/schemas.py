"""
schemas.py — Pydantic models for request & response validation
"""

from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from decimal import Decimal


# ── Auth ──────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


# ── Products ──────────────────────────────────────────────────
class ProductCreate(BaseModel):
    name: str
    category: str
    price: Decimal
    stock_quantity: int
    image_url: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[Decimal] = None
    stock_quantity: Optional[int] = None
    image_url: Optional[str] = None

class ProductOut(BaseModel):
    id: int
    name: str
    category: str
    price: Decimal
    stock_quantity: int
    image_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Sales ─────────────────────────────────────────────────────
class SaleItemIn(BaseModel):
    product_id: int
    quantity: int

class SaleCreate(BaseModel):
    items: List[SaleItemIn]

class SaleItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    price: Decimal

class SaleOut(BaseModel):
    id: int
    total_amount: Decimal
    created_at: datetime
    items: List[SaleItemOut] = []

    class Config:
        from_attributes = True


# ── Dashboard ─────────────────────────────────────────────────
class DashboardStats(BaseModel):
    total_products: int
    total_stock: int
    sales_today: Decimal
    low_stock_count: int
    sales_last_7_days: list
    top_categories: list
