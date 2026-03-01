"""
data/database.py
────────────────
SQLAlchemy ORM definitions + engine factory.
SQLite for MVP — swap DATABASE_URL in .env to PostgreSQL for production.
One config line change is the only difference.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from config.settings import DATABASE_URL


# ── Engine ────────────────────────────────────────────────────────────────────

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

# Enable WAL mode for SQLite (better concurrent reads)
if "sqlite" in DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── ORM Models ────────────────────────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    sku_id         = Column(String(32), primary_key=True)
    product_name   = Column(String(120), nullable=False)
    category       = Column(String(60), nullable=False)
    subcategory    = Column(String(60), nullable=False)
    brand          = Column(String(60))
    size           = Column(Float)          # numeric quantity (8, 16, 32 …)
    size_unit      = Column(String(10))     # "oz", "ml", "pk"
    regular_price  = Column(Float, nullable=False)
    cost_price     = Column(Float, nullable=False)
    margin_pct     = Column(Float)
    is_seasonal    = Column(Boolean, default=False)
    peak_seasons   = Column(Text)           # JSON array: '["diwali","christmas"]'

    sales          = relationship("Sale", back_populates="product")
    promotions     = relationship("Promotion", back_populates="product")


class Store(Base):
    __tablename__ = "stores"

    store_id            = Column(String(16), primary_key=True)
    store_name          = Column(String(80))
    channel             = Column(String(20))   # 'physical' | 'online'
    region              = Column(String(10))   # 'NE' | 'SE' | 'MW' | 'W'
    state               = Column(String(30))
    city                = Column(String(60))
    size_tier           = Column(String(20))   # 'large' | 'medium' | 'small'
    avg_weekly_footfall = Column(Integer)

    sales               = relationship("Sale", back_populates="store")


class Sale(Base):
    __tablename__ = "sales"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    date         = Column(Date, nullable=False, index=True)
    week_number  = Column(Integer)
    year         = Column(Integer)
    sku_id       = Column(String(32), ForeignKey("products.sku_id"), index=True)
    store_id     = Column(String(16), ForeignKey("stores.store_id"), index=True)
    units_sold   = Column(Float, nullable=False)
    revenue      = Column(Float)
    price_paid   = Column(Float)
    discount_pct = Column(Float, default=0.0)
    is_promo     = Column(Boolean, default=False)
    promo_id     = Column(String(32), ForeignKey("promotions.promo_id"), nullable=True)
    channel      = Column(String(20), default="physical")

    product      = relationship("Product", back_populates="sales")
    store        = relationship("Store", back_populates="sales")
    promotion    = relationship("Promotion", back_populates="sales")


class Promotion(Base):
    __tablename__ = "promotions"

    promo_id          = Column(String(32), primary_key=True)
    sku_id            = Column(String(32), ForeignKey("products.sku_id"), index=True)
    start_date        = Column(Date, nullable=False)
    end_date          = Column(Date, nullable=False)
    discount_pct      = Column(Float, nullable=False)
    promo_type        = Column(String(20))   # 'TPR' | 'BOGO' | 'Bundle' | 'Clearance'
    promo_mechanism   = Column(String(30))   # 'percent_off' | 'fixed_off' | 'multibuy'
    display_flag      = Column(Boolean, default=False)
    feature_flag      = Column(Boolean, default=False)
    digital_flag      = Column(Boolean, default=False)
    funding_type      = Column(String(30))   # 'self_funded' | 'vendor_funded' | 'co_op'

    product           = relationship("Product", back_populates="promotions")
    sales             = relationship("Sale", back_populates="promotion")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    date                = Column(Date, nullable=False, index=True)
    event_name          = Column(String(80))
    event_type          = Column(String(30))   # 'holiday' | 'retail_event' | 'cultural'
    intensity           = Column(Integer)       # 1 (minor) → 5 (major)
    relevant_categories = Column(Text)          # JSON


class SeasonalityIndex(Base):
    __tablename__ = "seasonality_index"

    id                     = Column(Integer, primary_key=True, autoincrement=True)
    sku_id                 = Column(String(32), ForeignKey("products.sku_id"), index=True)
    week_of_year           = Column(Integer)
    seasonality_multiplier = Column(Float)
    confidence             = Column(Float, default=1.0)


class CompetitorEvent(Base):
    __tablename__ = "competitor_events"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    date                  = Column(Date, nullable=False, index=True)
    competitor_name       = Column(String(80))
    category              = Column(String(60))
    product_description   = Column(String(120))
    estimated_discount_pct = Column(Float)
    promo_type            = Column(String(30))
    source                = Column(String(20), default="synthetic")
    impact_on_own_sales   = Column(Float)   # estimated % depression


class CustomerSegment(Base):
    __tablename__ = "customer_segments"

    id                            = Column(Integer, primary_key=True, autoincrement=True)
    store_id                      = Column(String(16), ForeignKey("stores.store_id"))
    segment_name                  = Column(String(40))   # 'price_sensitive' | 'loyalist' | 'occasional'
    segment_share_pct             = Column(Float)
    price_elasticity              = Column(Float)
    promo_response_multiplier     = Column(Float)
    cannibalization_susceptibility = Column(Float)


class User(Base):
    """Application user account — passwords stored as bcrypt hashes."""
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String(80), unique=True, nullable=False, index=True)
    email         = Column(String(120), unique=True, nullable=True, index=True)
    password_hash = Column(String(256), nullable=False)
    role          = Column(String(20), default="viewer")  # 'admin' | 'analyst' | 'viewer'
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    last_login    = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<User {self.username!r} role={self.role!r}>"


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_tables():
    """Create all tables (idempotent — safe to call on every startup)."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Dependency-injection style session factory."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """Direct session factory for use outside FastAPI/Dash callbacks."""
    return SessionLocal()
