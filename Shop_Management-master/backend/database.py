"""
database.py — SQLAlchemy setup + table models
Connects to MySQL using environment variables
"""

import os
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    DateTime, ForeignKey, Enum, Text, DECIMAL
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func

# ── Connection ────────────────────────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "smart_mall")
DB_USER = os.getenv("DB_USER", "malluser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "mall123")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Models ────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True, index=True)
    email      = Column(String(255), unique=True, nullable=False)
    password   = Column(String(255), nullable=False)
    role       = Column(Enum("admin", "staff"), default="admin")
    created_at = Column(DateTime, server_default=func.now())


class Product(Base):
    __tablename__ = "products"
    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(255), nullable=False, index=True)
    category       = Column(String(100), nullable=False, index=True)
    price          = Column(DECIMAL(10, 2), nullable=False)
    stock_quantity = Column(Integer, default=0, nullable=False)
    image_url      = Column(String(500), nullable=True)
    created_at     = Column(DateTime, server_default=func.now())
    updated_at     = Column(DateTime, server_default=func.now(), onupdate=func.now())

    sale_items = relationship("SaleItem", back_populates="product")


class Sale(Base):
    __tablename__ = "sales"
    id           = Column(Integer, primary_key=True, index=True)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    created_at   = Column(DateTime, server_default=func.now())

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete")


class SaleItem(Base):
    __tablename__ = "sale_items"
    id         = Column(Integer, primary_key=True, index=True)
    sale_id    = Column(Integer, ForeignKey("sales.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity   = Column(Integer, nullable=False)
    price      = Column(DECIMAL(10, 2), nullable=False)  # price snapshot

    sale    = relationship("Sale", back_populates="items")
    product = relationship("Product", back_populates="sale_items")


# ── Dependency ────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
