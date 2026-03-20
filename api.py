import sqlite3
import json
import asyncio
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import re

DB_PATH = "data/inverter_logs.db"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active websocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Performance optimizations for SQLite (WAL is already set at DB init)
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-10000')  # 10MB cache for faster lookups
    return conn

@app.get("/api/last")
async def get_last():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM data_points ORDER BY timestamp DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"timestamp": row["timestamp"], "data": json.loads(row["data"])}
    return {"error": "No data available"}

@app.get("/api/keys")
async def get_keys():
    """
    Returns a list of all unique keys in the last 100 records.
    Uses SQLite's json_each for more efficient key extraction directly in the database.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Use json_each to find unique keys within the last 100 records
    query = """
    SELECT DISTINCT json_each.key
    FROM data_points, json_each(data_points.data)
    WHERE data_points.id IN (SELECT id FROM data_points ORDER BY timestamp DESC LIMIT 100)
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    keys = [row[0] for row in rows]
    return sorted(keys)

@app.get("/api/data/{key}/last")
async def get_data_last(key: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Find the most recent record where this key is present
    # Using parameter substitution for JSON path to prevent SQL injection
    json_path = f"$.{key}"
    query = "SELECT timestamp, json_extract(data, ?) as value FROM data_points WHERE json_extract(data, ?) IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
    cursor.execute(query, (json_path, json_path))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {"timestamp": row["timestamp"], "value": row["value"]}
    return {"timestamp": None, "value": None}

@app.get("/api/data/{key}/history")
async def get_data_history(
    key: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    gt: Optional[float] = Query(None),
    lt: Optional[float] = Query(None),
    eq: Optional[float] = Query(None),
    limit: int = Query(100)
):
    query, params = build_data_query(key, start, end, gt, lt, eq, limit)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [[row["timestamp"], row["value"]] for row in rows]

@app.get("/api/data/{key}/stats")
async def get_data_stats(
    key: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    gt: Optional[float] = Query(None),
    lt: Optional[float] = Query(None),
    eq: Optional[float] = Query(None)
):
    # Perform all aggregations in a single efficient query
    json_path = f"$.{key}"

    select_clause = (
        "AVG(json_extract(data, ?)) as avg, "
        "MIN(json_extract(data, ?)) as min, "
        "MAX(json_extract(data, ?)) as max, "
        "SUM(json_extract(data, ?)) as sum, "
        "COUNT(json_extract(data, ?)) as count"
    )
    params = [json_path] * 5

    query = f"SELECT {select_clause} FROM data_points"

    # Add conditions
    conditions = []
    start_ts = parse_relative_time(start)
    if start_ts:
        conditions.append("timestamp >= ?")
        params.append(start_ts)

    end_ts = parse_relative_time(end)
    if end_ts:
        conditions.append("timestamp <= ?")
        params.append(end_ts)

    if gt is not None:
        conditions.append("json_extract(data, ?) > ?")
        params.extend([json_path, gt])
    if lt is not None:
        conditions.append("json_extract(data, ?) < ?")
        params.extend([json_path, lt])
    if eq is not None:
        conditions.append("json_extract(data, ?) = ?")
        params.extend([json_path, eq])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "avg": row["avg"],
            "min": row["min"],
            "max": row["max"],
            "sum": row["sum"],
            "count": row["count"]
        }
    return {"avg": None, "min": None, "max": None, "sum": None, "count": 0}

@app.get("/api/history")
async def get_history(start: Optional[str] = Query(None), end: Optional[str] = Query(None), limit: int = Query(100)):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = 'SELECT * FROM data_points'
    params = []

    conditions = []
    start_ts = parse_relative_time(start)
    if start_ts:
        conditions.append('timestamp >= ?')
        params.append(start_ts)

    end_ts = parse_relative_time(end)
    if end_ts:
        conditions.append('timestamp <= ?')
        params.append(end_ts)

    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)

    query += ' ORDER BY timestamp DESC LIMIT ?'
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [{"timestamp": row["timestamp"], "data": json.loads(row["data"])} for row in rows]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from client, but we need to keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def parse_relative_time(time_str: str) -> str:
    """
    Parses a relative time string (e.g., '1h', '24h', '1d', 'today') or an ISO timestamp.
    Returns an ISO-formatted string suitable for SQLite comparison.
    """
    if not time_str:
        return None

    if time_str.lower() == "today":
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%f')

    match = re.match(r'^(\d+)([smhd])$', time_str.lower())
    if match:
        value, unit = match.groups()
        value = int(value)
        if unit == 's':
            delta = timedelta(seconds=value)
        elif unit == 'm':
            delta = timedelta(minutes=value)
        elif unit == 'h':
            delta = timedelta(hours=value)
        elif unit == 'd':
            delta = timedelta(days=value)

        return (datetime.now() - delta).strftime('%Y-%m-%d %H:%M:%f')

    # Just return as is for SQLite to handle (ISO timestamp or other)
    return time_str

def build_data_query(
    key: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    gt: Optional[float] = None,
    lt: Optional[float] = None,
    eq: Optional[float] = None,
    limit: int = 100,
    aggregate: Optional[str] = None
):
    """
    Builds a dynamic SQLite query to extract a specific key from the JSON data.
    Uses parameter substitution for JSON path to prevent SQL injection.
    """
    params = []
    json_path = f"$.{key}"

    if aggregate:
        if aggregate == "avg":
            select_clause = "AVG(json_extract(data, ?)) as value"
        elif aggregate == "min":
            select_clause = "MIN(json_extract(data, ?)) as value"
        elif aggregate == "max":
            select_clause = "MAX(json_extract(data, ?)) as value"
        elif aggregate == "sum":
            select_clause = "SUM(json_extract(data, ?)) as value"
        elif aggregate == "count":
            select_clause = "COUNT(json_extract(data, ?)) as value"
        else:
            raise HTTPException(status_code=400, detail=f"Invalid aggregate function: {aggregate}")

        query = f"SELECT {select_clause} FROM data_points"
        params.append(json_path)
    else:
        query = "SELECT timestamp, json_extract(data, ?) as value FROM data_points"
        params.append(json_path)

    conditions = []

    start_ts = parse_relative_time(start)
    if start_ts:
        conditions.append("timestamp >= ?")
        params.append(start_ts)

    end_ts = parse_relative_time(end)
    if end_ts:
        conditions.append("timestamp <= ?")
        params.append(end_ts)

    if gt is not None:
        conditions.append("json_extract(data, ?) > ?")
        params.extend([json_path, gt])
    if lt is not None:
        conditions.append("json_extract(data, ?) < ?")
        params.extend([json_path, lt])
    if eq is not None:
        conditions.append("json_extract(data, ?) = ?")
        params.extend([json_path, eq])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if not aggregate:
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

    return query, params

# Helper function to be called by the engine
async def notify_new_data(data):
    message = json.dumps({"type": "new_data", "payload": data})
    await manager.broadcast(message)

# Serve static files for the dashboard
app.mount("/", StaticFiles(directory="static", html=True), name="static")
