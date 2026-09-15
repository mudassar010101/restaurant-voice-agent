import os
import random
import smtplib
import sqlite3
from datetime import datetime, timezone
from email.mime.text import MIMEText

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))

app = FastAPI(title="NexSpicy Voice Agent Backend")

DB_PATH = "orders.db"

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            contact TEXT,
            delivery_address TEXT,
            food TEXT,
            special_request TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reservations (
            reservation_id TEXT PRIMARY KEY,
            name TEXT,
            contact TEXT,
            party_size INTEGER,
            start_time TEXT,
            end_time TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS emails_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            to_email TEXT,
            subject TEXT,
            body TEXT,
            status TEXT,
            sent_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


@app.get("/emails")
async def list_emails():
    conn = get_db()
    rows = conn.execute("SELECT * FROM emails_log ORDER BY sent_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/orders")
async def list_orders():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/availability")
async def get_availability(start_time: str, end_time: str):
    """
    Check whether the requested time window overlaps with any existing reservation.
    start_time and end_time must be ISO 8601 strings, e.g. 2026-09-15T19:00:00
    """
    if end_time <= start_time:
        return {"error": "invalid_time_range", "message": "end_time must be after start_time."}

    conn = get_db()
    overlapping = conn.execute(
        """
        SELECT reservation_id, name, start_time, end_time FROM reservations
        WHERE start_time < ? AND end_time > ?
        """,
        (end_time, start_time),
    ).fetchall()
    conn.close()

    if overlapping:
        return {"available": False, "conflicts": [dict(row) for row in overlapping]}

    return {"available": True}


class UpdateOrderRequest(BaseModel):
    name: str | None = None
    contact: str | None = None
    delivery_address: str | None = None
    food: str | None = None
    special_request: str | None = None


@app.patch("/orders/{order_id}")
async def update_order(order_id: str, update: UpdateOrderRequest):
    conn = get_db()
    existing = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()

    if not existing:
        conn.close()
        return {"error": "not_found", "message": f"No order found with id {order_id}"}

    fields = update.model_dump(exclude_unset=True, exclude_none=True)
    if not fields:
        conn.close()
        return {"error": "no_changes", "message": "No fields provided to update."}

    updated_at = datetime.now(timezone.utc).isoformat()
    fields["updated_at"] = updated_at

    set_clause = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [order_id]

    conn.execute(f"UPDATE orders SET {set_clause} WHERE order_id = ?", values)
    conn.commit()
    conn.close()

    return {"order_id": order_id, "status": "updated", "updated_at": updated_at, "changed_fields": list(fields.keys())}


class CreateOrderRequest(BaseModel):
    name: str
    email: str | None = None
    contact: str
    delivery_address: str
    food: str
    special_request: str | None = None


def generate_order_id(conn):
    """Generate a random 6-digit numeric order ID, retrying if it already exists."""
    while True:
        candidate = str(random.randint(100000, 999999))
        exists = conn.execute("SELECT 1 FROM orders WHERE order_id = ?", (candidate,)).fetchone()
        if not exists:
            return candidate


@app.post("/orders")
async def create_order(order: CreateOrderRequest):
    conn = get_db()
    order_id = generate_order_id(conn)
    created_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO orders (order_id, name, email, contact, delivery_address, food, special_request, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (order_id, order.name, order.email, order.contact, order.delivery_address, order.food, order.special_request, created_at),
    )
    conn.commit()
    conn.close()

    return {
        "order_id": order_id,
        "status": "created",
        "created_at": created_at,
    }


class CreateReservationRequest(BaseModel):
    name: str
    start_time: str
    end_time: str
    contact: str | None = None
    party_size: int | None = None


def generate_reservation_id(conn):
    """Generate a random 6-digit numeric reservation ID, retrying if it already exists."""
    while True:
        candidate = str(random.randint(100000, 999999))
        exists = conn.execute("SELECT 1 FROM reservations WHERE reservation_id = ?", (candidate,)).fetchone()
        if not exists:
            return candidate


@app.post("/reservations")
async def create_reservation(reservation: CreateReservationRequest):
    if reservation.end_time <= reservation.start_time:
        return {"error": "invalid_time_range", "message": "end_time must be after start_time."}

    conn = get_db()

    # Check for overlapping reservations before booking (same rule as /availability)
    overlapping = conn.execute(
        """
        SELECT reservation_id FROM reservations
        WHERE start_time < ? AND end_time > ?
        """,
        (reservation.end_time, reservation.start_time),
    ).fetchone()

    if overlapping:
        conn.close()
        return {"error": "not_available", "message": "That time slot is already booked."}

    reservation_id = generate_reservation_id(conn)
    created_at = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO reservations (reservation_id, name, contact, party_size, start_time, end_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (reservation_id, reservation.name, reservation.contact, reservation.party_size, reservation.start_time, reservation.end_time, created_at),
    )
    conn.commit()
    conn.close()

    return {
        "reservation_id": reservation_id,
        "status": "created",
        "created_at": created_at,
    }


@app.get("/reservations")
async def list_reservations():
    conn = get_db()
    rows = conn.execute("SELECT * FROM reservations ORDER BY start_time ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


class UpdateReservationRequest(BaseModel):
    name: str | None = None
    contact: str | None = None
    party_size: int | None = None


@app.patch("/reservations/{reservation_id}")
async def update_reservation(reservation_id: str, update: UpdateReservationRequest):
    conn = get_db()
    existing = conn.execute("SELECT * FROM reservations WHERE reservation_id = ?", (reservation_id,)).fetchone()

    if not existing:
        conn.close()
        return {"error": "not_found", "message": f"No reservation found with id {reservation_id}"}

    fields = update.model_dump(exclude_unset=True, exclude_none=True)
    if not fields:
        conn.close()
        return {"error": "no_changes", "message": "No fields provided to update."}

    updated_at = datetime.now(timezone.utc).isoformat()
    fields["updated_at"] = updated_at

    set_clause = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [reservation_id]

    conn.execute(f"UPDATE reservations SET {set_clause} WHERE reservation_id = ?", values)
    conn.commit()
    conn.close()

    return {"reservation_id": reservation_id, "status": "updated", "updated_at": updated_at, "changed_fields": list(fields.keys())}


class SendEmailRequest(BaseModel):
    to_email: str
    subject: str
    text: str


@app.post("/send-email")
async def send_email(email: SendEmailRequest):
    sent_at = datetime.now(timezone.utc).isoformat()

    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        return {"error": "smtp_not_configured", "message": "SMTP_EMAIL / SMTP_APP_PASSWORD not set in .env.local"}

    msg = MIMEText(email.text)
    msg["Subject"] = email.subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = email.to_email

    conn = get_db()
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
            server.sendmail(SMTP_EMAIL, [email.to_email], msg.as_string())

        conn.execute(
            "INSERT INTO emails_log (to_email, subject, body, status, sent_at) VALUES (?, ?, ?, ?, ?)",
            (email.to_email, email.subject, email.text, "sent", sent_at),
        )
        conn.commit()
        conn.close()
        return {"status": "sent", "to": email.to_email, "sent_at": sent_at}

    except Exception as e:
        conn.execute(
            "INSERT INTO emails_log (to_email, subject, body, status, sent_at) VALUES (?, ?, ?, ?, ?)",
            (email.to_email, email.subject, email.text, f"failed: {e}", sent_at),
        )
        conn.commit()
        conn.close()
        return {"error": "send_failed", "message": str(e)}