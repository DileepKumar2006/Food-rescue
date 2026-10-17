"""HarvestLink: a small, persistent food donation and redistribution app."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))
DB_PATH = DATA_DIR / "harvestlink.sqlite3"
PORT = int(os.environ.get("PORT", "8000"))
STATUSES = {"available", "reserved", "collected"}


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def initialize():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, category TEXT NOT NULL, quantity REAL NOT NULL,
            unit TEXT NOT NULL, location TEXT NOT NULL, donor TEXT NOT NULL,
            phone TEXT NOT NULL, expires_at TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'available', claimed_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )""")
        if db.execute("SELECT COUNT(*) FROM donations").fetchone()[0] == 0:
            now = datetime.now(timezone.utc)
            samples = [
                ("Fresh produce boxes", "Produce", 18, "boxes", "Indiranagar, Bengaluru", "Green Basket Market", "+91 98765 43210", 8, "Seasonal vegetables and fruit. Bring reusable crates.", "available"),
                ("Bakery assortment", "Bakery", 42, "items", "Koramangala, Bengaluru", "Daily Crumb Bakery", "+91 98765 43211", 5, "Bread, buns and pastries baked this morning.", "available"),
                ("Cooked lunch packs", "Prepared meals", 26, "meals", "Jubilee Hills, Hyderabad", "Kind Table Kitchen", "+91 98765 43212", 3, "Vegetarian meals packed and labeled. Pickup before 2 pm.", "available"),
                ("Pantry staples", "Pantry", 30, "kg", "Kothrud, Pune", "Community Pantry Co-op", "+91 98765 43213", 48, "Rice and lentils in sealed, food-grade bags.", "reserved"),
                ("Dairy and yogurt", "Dairy", 12, "litres", "T. Nagar, Chennai", "Morning Milk Collective", "+91 98765 43214", 10, "Kept chilled throughout. Please bring a cooler.", "available"),
                ("Banana crate", "Produce", 16, "kg", "Civil Lines, Jaipur", "Sunrise Fruit Stall", "+91 98765 43215", 12, "Ripe bananas, ideal for same-day distribution.", "available"),
            ]
            for title, category, qty, unit, location, donor, phone, hours, notes, status in samples:
                db.execute("""INSERT INTO donations
                    (title, category, quantity, unit, location, donor, phone, expires_at, notes, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (title, category, qty, unit, location, donor, phone,
                     (now + timedelta(hours=hours)).isoformat(), notes, status, now.isoformat()))


def clean(value, maximum=160):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = min(int(self.headers.get("Content-Length", "0")), 16_384)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self.send_json({"ok": True, "database": "sqlite"})
        if parsed.path == "/api/donations":
            with connect() as db:
                rows = db.execute("SELECT * FROM donations ORDER BY CASE status WHEN 'available' THEN 0 WHEN 'reserved' THEN 1 ELSE 2 END, expires_at").fetchall()
                items = [dict(row) for row in rows]
            stats = {
                "active": sum(row["status"] == "available" for row in items),
                "meals": sum(row["quantity"] for row in items if row["unit"] in ("meals", "items", "boxes")),
                "rescued": sum(row["status"] == "collected" for row in items),
            }
            return self.send_json({"donations": items, "stats": stats})
        return super().do_GET()

    def do_POST(self):
        if urlparse(self.path).path != "/api/donations":
            return self.send_json({"error": "Not found"}, 404)
        try:
            data = self.read_json()
            required = {key: clean(data.get(key), limit) for key, limit in {
                "title": 90, "category": 40, "unit": 20, "location": 120,
                "donor": 70, "phone": 40, "expires_at": 40,
            }.items()}
            if any(not value for value in required.values()):
                return self.send_json({"error": "Please complete all required fields."}, 400)
            quantity = float(data.get("quantity", 0))
            if quantity <= 0 or quantity > 1_000_000:
                return self.send_json({"error": "Quantity must be a positive number."}, 400)
            expires = datetime.fromisoformat(required["expires_at"].replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= datetime.now(timezone.utc):
                return self.send_json({"error": "Choose a pickup deadline in the future."}, 400)
            with connect() as db:
                cursor = db.execute("""INSERT INTO donations
                    (title, category, quantity, unit, location, donor, phone, expires_at, notes, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'available', ?)""",
                    (required["title"], required["category"], quantity, required["unit"],
                     required["location"], required["donor"], required["phone"], expires.isoformat(),
                     clean(data.get("notes"), 500), datetime.now(timezone.utc).isoformat()))
                item = dict(db.execute("SELECT * FROM donations WHERE id = ?", (cursor.lastrowid,)).fetchone())
            return self.send_json({"donation": item}, 201)
        except (ValueError, TypeError, json.JSONDecodeError):
            return self.send_json({"error": "Please check the donation details and try again."}, 400)

    def do_PATCH(self):
        match = re.fullmatch(r"/api/donations/(\d+)/(claim|status)", urlparse(self.path).path)
        if not match:
            return self.send_json({"error": "Not found"}, 404)
        donation_id, action = int(match.group(1)), match.group(2)
        try:
            data = self.read_json()
            with connect() as db:
                item = db.execute("SELECT * FROM donations WHERE id = ?", (donation_id,)).fetchone()
                if not item:
                    return self.send_json({"error": "Donation not found."}, 404)
                if action == "claim":
                    partner = clean(data.get("partner"), 70)
                    if not partner:
                        return self.send_json({"error": "Add your organization name to reserve this donation."}, 400)
                    # Conditional update prevents two groups reserving the same listing at once.
                    cursor = db.execute(
                        "UPDATE donations SET status = 'reserved', claimed_by = ? WHERE id = ? AND status = 'available'",
                        (partner, donation_id),
                    )
                    if cursor.rowcount != 1:
                        return self.send_json({"error": "This donation is no longer available."}, 409)
                else:
                    status = clean(data.get("status"), 20)
                    if status not in STATUSES:
                        return self.send_json({"error": "Choose a valid status."}, 400)
                    current = item["status"]
                    allowed = {"reserved": "collected", "collected": "available"}
                    if allowed.get(current) != status:
                        return self.send_json({"error": f"Cannot change a {current} listing to {status}."}, 409)
                    db.execute("UPDATE donations SET status = ?, claimed_by = CASE WHEN ? = 'available' THEN '' ELSE claimed_by END WHERE id = ?",
                               (status, status, donation_id))
                updated = dict(db.execute("SELECT * FROM donations WHERE id = ?", (donation_id,)).fetchone())
            return self.send_json({"donation": updated})
        except (ValueError, TypeError, json.JSONDecodeError):
            return self.send_json({"error": "Could not update this donation."}, 400)

    def log_message(self, format, *args):
        print(f"{self.log_date_time_string()} {args[0] if args else ''}")


if __name__ == "__main__":
    initialize()
    print(f"HarvestLink running on port {PORT}; SQLite database: {DB_PATH}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
