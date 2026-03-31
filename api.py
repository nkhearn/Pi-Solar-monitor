import sqlite3
import json
import asyncio
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import re
import ast

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

# Simple in-memory cache for virtual metrics and pre-compiled SQL expressions
_virtual_metrics_cache = None
_sql_expressions_cache = {}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Performance optimizations for SQLite (WAL is already set at DB init)
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-10000')  # 10MB cache for faster lookups
    return conn

def get_virtual_metrics_map():
    global _virtual_metrics_cache
    if _virtual_metrics_cache is not None:
        return _virtual_metrics_cache

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, formula FROM virtual_metrics')
    rows = cursor.fetchall()
    conn.close()
    _virtual_metrics_cache = {row['name']: row['formula'] for row in rows}
    return _virtual_metrics_cache

def invalidate_vm_cache():
    global _virtual_metrics_cache
    global _sql_expressions_cache
    _virtual_metrics_cache = None
    _sql_expressions_cache = {}

def is_safe_formula(formula: str):
    """
    Checks if a formula is safe to evaluate using ast.parse.
    Only allows basic math and alphanumeric characters.
    """
    if not re.match(r'^[a-zA-Z0-9_+*/() \-.]+$', formula):
        return False
    if '__' in formula:
        return False
    try:
        root = ast.parse(formula, mode='eval')
        for node in ast.walk(root):
            if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant,
                                     ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)):
                return False
            if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
                return False
        return True
    except Exception:
        return False

def formula_to_sql(formula: str):
    """
    Converts a formula like (m1 + m2) / m3 into a SQLite JSON extraction expression.
    Caches results for performance.
    """
    if formula in _sql_expressions_cache:
        return _sql_expressions_cache[formula]

    metrics = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]*\b', formula)
    metrics.sort(key=len, reverse=True)

    sql_expression = formula
    for m in metrics:
        sql_expression = re.sub(r'\b' + re.escape(m) + r'\b', f"CAST(json_extract(data, '$.{m}') AS REAL)", sql_expression)

    _sql_expressions_cache[formula] = sql_expression
    return sql_expression

def evaluate_formula(formula: str, data: dict):
    """
    Safely evaluates a virtual metric formula using the provided data.
    """
    try:
        # Extract variables from formula
        metrics = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]*\b', formula)
        # Build local namespace for eval
        context = {m: float(data.get(m, 0)) for m in metrics}
        # Use a restricted eval with only necessary operators
        if is_safe_formula(formula):
            return eval(formula, {"__builtins__": {}}, context)
    except Exception:
        pass
    return None

@app.get("/api/last")
async def get_last():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM data_points ORDER BY timestamp DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    if row:
        data = json.loads(row["data"])
        v_metrics = get_virtual_metrics_map()
        if v_metrics:
            for name, formula in v_metrics.items():
                data[name] = evaluate_formula(formula, data)

        return {"timestamp": row["timestamp"], "data": data}
    return {"error": "No data available"}

@app.get("/api/keys")
async def get_keys():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT DISTINCT json_each.key
    FROM data_points, json_each(data_points.data)
    WHERE data_points.id IN (SELECT id FROM data_points ORDER BY timestamp DESC LIMIT 100)
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    keys = [row[0] for row in rows]

    v_metrics = get_virtual_metrics_map()
    keys.extend(v_metrics.keys())

    conn.close()
    return sorted(list(set(keys)))

@app.get("/api/data/{key}/last")
async def get_data_last(key: str):
    v_metrics = get_virtual_metrics_map()
    if key in v_metrics:
        sql_expr = formula_to_sql(v_metrics[key])
        query = f"SELECT timestamp, {sql_expr} as value FROM data_points WHERE {sql_expr} IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
        params = []
    else:
        # Restore parameter substitution for JSON path to prevent SQL injection
        query = "SELECT timestamp, json_extract(data, ?) as value FROM data_points WHERE json_extract(data, ?) IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
        params = [f"$.{key}", f"$.{key}"]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        row = cursor.fetchone()
    except sqlite3.OperationalError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Error evaluating virtual metric: {e}")
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
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Error evaluating virtual metric: {e}")
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
    v_metrics = get_virtual_metrics_map()
    params = []
    if key in v_metrics:
        sql_expr = formula_to_sql(v_metrics[key])
    else:
        sql_expr = "json_extract(data, ?)"
        params.extend([f"$.{key}"] * 5) # For the 5 aggregations

    select_clause = (
        f"AVG({sql_expr}) as avg, "
        f"MIN({sql_expr}) as min, "
        f"MAX({sql_expr}) as max, "
        f"SUM({sql_expr}) as sum, "
        f"COUNT({sql_expr}) as count"
    )

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
        if key in v_metrics:
            conditions.append(f"{sql_expr} > ?")
        else:
            conditions.append("json_extract(data, ?) > ?")
            params.append(f"$.{key}")
        params.append(gt)

    if lt is not None:
        if key in v_metrics:
            conditions.append(f"{sql_expr} < ?")
        else:
            conditions.append("json_extract(data, ?) < ?")
            params.append(f"$.{key}")
        params.append(lt)

    if eq is not None:
        if key in v_metrics:
            conditions.append(f"{sql_expr} = ?")
        else:
            conditions.append("json_extract(data, ?) = ?")
            params.append(f"$.{key}")
        params.append(eq)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        row = cursor.fetchone()
    except sqlite3.OperationalError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Error evaluating virtual metric: {e}")
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

@app.get("/api/data/{key}/stats/{stat_key}")
async def get_data_single_stat(
    key: str,
    stat_key: str,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    gt: Optional[float] = Query(None),
    lt: Optional[float] = Query(None),
    eq: Optional[float] = Query(None)
):
    valid_stats = {"avg", "min", "max", "sum", "count"}
    if stat_key not in valid_stats:
        raise HTTPException(status_code=400, detail=f"Invalid stat_key: {stat_key}. Available: avg, min, max, sum, count")

    query, params = build_data_query(key, start, end, gt, lt, eq, aggregate=stat_key)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        row = cursor.fetchone()
    except sqlite3.OperationalError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Error evaluating virtual metric: {e}")
    conn.close()

    return {"value": row["value"]}

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

@app.get("/api/virtual_metrics")
async def get_virtual_metrics():
    v_metrics = get_virtual_metrics_map()
    return [{"name": k, "formula": v} for k, v in v_metrics.items()]

@app.post("/api/virtual_metrics")
async def create_virtual_metric(name: str = Body(..., embed=True), formula: str = Body(..., embed=True)):
    if not is_safe_formula(formula):
        raise HTTPException(status_code=400, detail="Invalid formula. Only basic math and alphanumeric characters allowed.")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT OR REPLACE INTO virtual_metrics (name, formula) VALUES (?, ?)', (name, formula))
        conn.commit()
        invalidate_vm_cache()
    except sqlite3.Error as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    conn.close()
    return {"status": "success"}

@app.delete("/api/virtual_metrics/{name}")
async def delete_virtual_metric(name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM virtual_metrics WHERE name = ?', (name,))
    conn.commit()
    conn.close()
    invalidate_vm_cache()
    return {"status": "success"}

@app.get("/api/charts")
async def get_charts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM dashboard_charts')
    rows = cursor.fetchall()
    conn.close()
    return [json.loads(row['config']) for row in rows]

@app.post("/api/charts")
async def save_charts(charts: List[Dict] = Body(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM dashboard_charts')
        for chart in charts:
            cursor.execute('INSERT INTO dashboard_charts (id, config) VALUES (?, ?)', (chart['id'], json.dumps(chart)))
        conn.commit()
    except sqlite3.Error as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
    conn.close()
    return {"status": "success"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

def parse_relative_time(time_str: str) -> str:
    if not time_str:
        return None
    if time_str.lower() == "today":
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%f')
    match = re.match(r'^(\d+)([smhd])$', time_str.lower())
    if match:
        value, unit = match.groups()
        value = int(value)
        if unit == 's': delta = timedelta(seconds=value)
        elif unit == 'm': delta = timedelta(minutes=value)
        elif unit == 'h': delta = timedelta(hours=value)
        elif unit == 'd': delta = timedelta(days=value)
        return (datetime.now() - delta).strftime('%Y-%m-%d %H:%M:%f')
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
    v_metrics = get_virtual_metrics_map()
    params = []
    if key in v_metrics:
        sql_expr = formula_to_sql(v_metrics[key])
    else:
        sql_expr = "json_extract(data, ?)"
        params.append(f"$.{key}")

    if aggregate:
        if aggregate == "avg": select_clause = f"AVG({sql_expr}) as value"
        elif aggregate == "min": select_clause = f"MIN({sql_expr}) as value"
        elif aggregate == "max": select_clause = f"MAX({sql_expr}) as value"
        elif aggregate == "sum": select_clause = f"SUM({sql_expr}) as value"
        elif aggregate == "count": select_clause = f"COUNT({sql_expr}) as value"
        else: raise HTTPException(status_code=400, detail=f"Invalid aggregate function: {aggregate}")
        query = f"SELECT {select_clause} FROM data_points"
    else:
        query = f"SELECT timestamp, {sql_expr} as value FROM data_points"

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
        if key in v_metrics:
            conditions.append(f"{sql_expr} > ?")
        else:
            conditions.append("json_extract(data, ?) > ?")
            params.append(f"$.{key}")
        params.append(gt)
    if lt is not None:
        if key in v_metrics:
            conditions.append(f"{sql_expr} < ?")
        else:
            conditions.append("json_extract(data, ?) < ?")
            params.append(f"$.{key}")
        params.append(lt)
    if eq is not None:
        if key in v_metrics:
            conditions.append(f"{sql_expr} = ?")
        else:
            conditions.append("json_extract(data, ?) = ?")
            params.append(f"$.{key}")
        params.append(eq)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if not aggregate:
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

    return query, params

async def notify_new_data(data_payload):
    v_metrics = get_virtual_metrics_map()
    if v_metrics:
        data = data_payload["data"]
        for name, formula in v_metrics.items():
            data[name] = evaluate_formula(formula, data)

    message = json.dumps({"type": "new_data", "payload": data_payload})
    await manager.broadcast(message)

app.mount("/", StaticFiles(directory="static", html=True), name="static")
