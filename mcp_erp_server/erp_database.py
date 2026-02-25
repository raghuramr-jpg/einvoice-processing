"""Simulated ERP database using SQLite.

Pre-seeded with sample French suppliers, purchase orders, and bank details
so the MCP tools have realistic data to validate against.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parent / "erp_data.db"


def _get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = str(db_path or _DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def get_db(db_path: Path | str | None = None):
    conn = _get_connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS suppliers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    vat_number  TEXT NOT NULL UNIQUE,
    siret       TEXT NOT NULL UNIQUE,
    iban        TEXT NOT NULL,
    bic         TEXT NOT NULL,
    address     TEXT NOT NULL,
    city        TEXT NOT NULL,
    country     TEXT NOT NULL DEFAULT 'FR',
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number    TEXT NOT NULL UNIQUE,
    supplier_id  INTEGER NOT NULL REFERENCES suppliers(id),
    status       TEXT NOT NULL DEFAULT 'open',
    total_amount REAL NOT NULL,
    currency     TEXT NOT NULL DEFAULT 'EUR',
    created_date TEXT NOT NULL,
    description  TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS erp_invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    erp_invoice_id  TEXT NOT NULL UNIQUE,
    supplier_id     INTEGER NOT NULL REFERENCES suppliers(id),
    po_number       TEXT NOT NULL,
    invoice_number  TEXT NOT NULL,
    invoice_date    TEXT NOT NULL,
    total_ht        REAL NOT NULL,
    tva_amount      REAL NOT NULL,
    total_ttc       REAL NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'EUR',
    status          TEXT NOT NULL DEFAULT 'posted',
    created_at      TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Seed data — 5 realistic French suppliers
# ---------------------------------------------------------------------------

_SEED_SUPPLIERS = [
    {
        "name": "TechnoVision SAS",
        "vat_number": "FR82123456789",
        "siret": "12345678900014",
        "iban": "FR7630006000011234567890189",
        "bic": "BNPAFRPP",
        "address": "15 Rue de la Paix",
        "city": "Paris",
        "country": "FR",
    },
    {
        "name": "Fournitures Dupont SARL",
        "vat_number": "FR55987654321",
        "siret": "98765432100028",
        "iban": "FR7610011000202345678901234",
        "bic": "PSSTFRPP",
        "address": "42 Avenue des Champs-Élysées",
        "city": "Lyon",
        "country": "FR",
    },
    {
        "name": "LogiServ Europe SA",
        "vat_number": "FR31456789012",
        "siret": "45678901200035",
        "iban": "FR7620041000013456789012345",
        "bic": "CEPAFRPP",
        "address": "8 Boulevard Haussmann",
        "city": "Marseille",
        "country": "FR",
    },
    {
        "name": "GreenSupply France",
        "vat_number": "FR19234567890",
        "siret": "23456789000042",
        "iban": "FR7630004000034567890123456",
        "bic": "BNPAFRPP",
        "address": "120 Rue du Commerce",
        "city": "Toulouse",
        "country": "FR",
    },
    {
        "name": "MétalPro Industries",
        "vat_number": "FR67890123456",
        "siret": "89012345600019",
        "iban": "FR7610096000005678901234567",
        "bic": "CMCIFRPP",
        "address": "5 Impasse des Ateliers",
        "city": "Bordeaux",
        "country": "FR",
    },
]

_SEED_PURCHASE_ORDERS = [
    {"po_number": "PO-2025-001", "supplier_id": 1, "status": "open", "total_amount": 15000.00, "created_date": "2025-01-15", "description": "IT Equipment Q1"},
    {"po_number": "PO-2025-002", "supplier_id": 2, "status": "open", "total_amount": 8500.00, "created_date": "2025-02-01", "description": "Office supplies"},
    {"po_number": "PO-2025-003", "supplier_id": 3, "status": "partially_received", "total_amount": 32000.00, "created_date": "2025-01-20", "description": "Logistics services"},
    {"po_number": "PO-2025-004", "supplier_id": 4, "status": "open", "total_amount": 5200.00, "created_date": "2025-02-10", "description": "Eco-friendly packaging"},
    {"po_number": "PO-2025-005", "supplier_id": 5, "status": "closed", "total_amount": 45000.00, "created_date": "2024-11-05", "description": "Metal fabrication Year-end"},
    {"po_number": "PO-2025-006", "supplier_id": 1, "status": "open", "total_amount": 22000.00, "created_date": "2025-02-18", "description": "Cloud infrastructure setup"},
]


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init_database(db_path: Path | str | None = None) -> None:
    """Create tables and seed data if the DB is empty."""
    with get_db(db_path) as conn:
        conn.executescript(_SCHEMA_SQL)

        count = conn.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
        if count == 0:
            for s in _SEED_SUPPLIERS:
                conn.execute(
                    "INSERT INTO suppliers (name, vat_number, siret, iban, bic, address, city, country) "
                    "VALUES (:name, :vat_number, :siret, :iban, :bic, :address, :city, :country)",
                    s,
                )
            for po in _SEED_PURCHASE_ORDERS:
                conn.execute(
                    "INSERT INTO purchase_orders (po_number, supplier_id, status, total_amount, created_date, description) "
                    "VALUES (:po_number, :supplier_id, :status, :total_amount, :created_date, :description)",
                    po,
                )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def find_supplier_by_vat(vat_number: str, db_path=None) -> Optional[dict]:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM suppliers WHERE vat_number = ? AND active = 1",
            (vat_number,),
        ).fetchone()
        return dict(row) if row else None


def find_supplier_by_siret(siret: str, db_path=None) -> Optional[dict]:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM suppliers WHERE siret = ? AND active = 1",
            (siret,),
        ).fetchone()
        return dict(row) if row else None


def find_supplier_by_name(name: str, db_path=None) -> Optional[dict]:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM suppliers WHERE LOWER(name) LIKE LOWER(?) AND active = 1",
            (f"%{name}%",),
        ).fetchone()
        return dict(row) if row else None


def find_supplier_bank(iban: str, bic: str, db_path=None) -> Optional[dict]:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM suppliers WHERE iban = ? AND bic = ? AND active = 1",
            (iban, bic),
        ).fetchone()
        return dict(row) if row else None


def find_purchase_order(po_number: str, db_path=None) -> Optional[dict]:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM purchase_orders WHERE po_number = ?",
            (po_number,),
        ).fetchone()
        return dict(row) if row else None


def create_invoice(
    supplier_id: int,
    po_number: str,
    invoice_number: str,
    invoice_date: str,
    total_ht: float,
    tva_amount: float,
    total_ttc: float,
    currency: str = "EUR",
    db_path=None,
) -> str:
    """Insert an invoice into the ERP and return the generated erp_invoice_id."""
    erp_invoice_id = f"ERP-INV-{uuid.uuid4().hex[:8].upper()}"
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO erp_invoices "
            "(erp_invoice_id, supplier_id, po_number, invoice_number, invoice_date, "
            "total_ht, tva_amount, total_ttc, currency, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'posted', ?)",
            (
                erp_invoice_id, supplier_id, po_number, invoice_number,
                invoice_date, total_ht, tva_amount, total_ttc, currency,
                datetime.utcnow().isoformat(),
            ),
        )
    return erp_invoice_id
