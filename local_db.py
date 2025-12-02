import sqlite3
import os

DB_PATH = "local_data.db"

def init_local_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            distance REAL,
            line_side TEXT,
            voltage REAL,
            synced INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()

def insert_local_record(timestamp, distance, line_side, voltage):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO sensor_data(timestamp, distance, line_side, voltage, synced)
        VALUES (?, ?, ?, ?, 0)
    """, (timestamp, distance, line_side, voltage))

    conn.commit()
    conn.close()

def get_unsynced_records():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT * FROM sensor_data WHERE synced = 0")
    rows = c.fetchall()

    conn.close()
    return rows

def mark_as_synced(row_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("UPDATE sensor_data SET synced = 1 WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()
