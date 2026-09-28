import sqlite3
import os
from datetime import datetime, timezone

VALID_STATUSES = {
    "CREATED",
    "SHIPPED",
    "IN_TRANSIT",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "CANCELLED"
}

TERMINAL_STATUSES = {
    "DELIVERED",
    "CANCELLED"
}

def get_db_connection(db_path: str):
    """Establishes and returns a connection to the SQLite database."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str):
    """Initializes the SQLite database with the required schema."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cargo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_number TEXT NOT NULL UNIQUE,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'CREATED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def create_cargo(tracking_number: str, sender: str, receiver: str, db_path: str) -> dict:
    """Creates a new cargo record in SQLite."""
    if not tracking_number or not str(tracking_number).strip():
        raise ValueError("tracking_number cannot be empty")
    if not sender or not str(sender).strip():
        raise ValueError("sender cannot be empty")
    if not receiver or not str(receiver).strip():
        raise ValueError("receiver cannot be empty")

    tracking_number = str(tracking_number).strip()
    sender = str(sender).strip()
    receiver = str(receiver).strip()

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Check duplicate tracking number
    cursor.execute("SELECT id FROM cargo WHERE tracking_number = ?", (tracking_number,))
    if cursor.fetchone():
        conn.close()
        raise ValueError(f"Cargo with tracking number '{tracking_number}' already exists")

    cursor.execute(
        "INSERT INTO cargo (tracking_number, sender, receiver, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (tracking_number, sender, receiver, "CREATED", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    cargo_id = cursor.lastrowid
    
    cursor.execute("SELECT * FROM cargo WHERE id = ?", (cargo_id,))
    row = cursor.fetchone()
    cargo = dict(row)
    conn.close()
    return cargo

def get_cargo_by_id(cargo_id: int, db_path: str) -> dict | None:
    """Retrieves a single cargo by ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cargo WHERE id = ?", (cargo_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_cargo_by_tracking_number(tracking_number: str, db_path: str) -> dict | None:
    """Retrieves a single cargo by tracking number."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cargo WHERE tracking_number = ?", (tracking_number,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_cargos(db_path: str) -> list[dict]:
    """Retrieves all cargos from database."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cargo ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_cargo_status(cargo_id: int, new_status: str, db_path: str) -> dict:
    """Updates cargo status with validation rules."""
    if not new_status or new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: '{new_status}'. Valid statuses are: {', '.join(sorted(VALID_STATUSES))}")

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cargo WHERE id = ?", (cargo_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    current_cargo = dict(row)
    current_status = current_cargo['status']

    # Terminal state checks
    if current_status == "DELIVERED":
        conn.close()
        raise ValueError("Delivered cargo cannot change status")
    
    if current_status == "CANCELLED":
        conn.close()
        raise ValueError("Cancelled cargo cannot change status")

    cursor.execute("UPDATE cargo SET status = ? WHERE id = ?", (new_status, cargo_id))
    conn.commit()

    cursor.execute("SELECT * FROM cargo WHERE id = ?", (cargo_id,))
    updated_row = cursor.fetchone()
    updated_cargo = dict(updated_row)
    conn.close()
    return updated_cargo

def delete_cargo(cargo_id: int, db_path: str) -> bool:
    """Deletes a cargo record by ID."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM cargo WHERE id = ?", (cargo_id,))
    if not cursor.fetchone():
        conn.close()
        return False

    cursor.execute("DELETE FROM cargo WHERE id = ?", (cargo_id,))
    conn.commit()
    conn.close()
    return True
