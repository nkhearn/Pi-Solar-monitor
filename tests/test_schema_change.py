import asyncio
from engine import save_to_db
import sqlite3
import os

DB_PATH = "data/inverter_logs.db"

def test_dynamic_columns():
    data1 = {"pv_voltage": 120.5, "battery_voltage": 13.2}
    save_to_db(data1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(data_points)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Columns after data1: {columns}")

    data2 = {"new_metric": 42, "PV-Voltage": 121.0} # Testing sanitization too
    save_to_db(data2)

    cursor.execute("PRAGMA table_info(data_points)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"Columns after data2: {columns}")

    cursor.execute("SELECT * FROM data_points")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()

if __name__ == "__main__":
    test_dynamic_columns()
