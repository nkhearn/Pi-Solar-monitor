import sqlite3
import json
import asyncio
import threading
import time
from typing import List, Optional, Any, Dict, Annotated
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
import re
import ast

DB_PATH = "data/inverter_logs.db"

_db_conn = None
_db_lock = threading.Lock()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

_virtual_metrics_cache = None
_sql_expressions_cache = {}
_compiled_formulas_cache = {}

_stats_cache = {}
STATS_CACHE_TTL = 30
STATS_CACHE_MAX_SIZE = 100

def get_db_connection():
    global _db_conn
    if _db_conn is None:
        with _db_lock:
            if _db_conn is None:
                _db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
                _db_conn.row_factory = sqlite3.Row
                _db_conn.execute('PRAGMA synchronous=NORMAL')
                _db_conn.execute('PRAGMA cache_size=-10000')
                _db_conn.execute('PRAGMA mmap_size=268435456')
    return _db_conn

def _get_virtual_metrics_from_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, formula FROM virtual_metrics')
    return cursor.fetchall()

async def get_virtual_metrics_map():
    global _virtual_metrics_cache
    if _virtual_metrics_cache is not None:
        return _virtual_metrics_cache

    rows = await asyncio.to_thread(_get_virtual_metrics_from_db)
    _virtual_metrics_cache = {row['name']: row['formula'] for row in rows}
    return _virtual_metrics_cache

def invalidate_vm_cache():
    global _virtual_metrics_cache
    global _sql_expressions_cache
    global _compiled_formulas_cache
    _virtual_metrics_cache = None
    _sql_expressions_cache = {}
    _compiled_formulas_cache = {}

def is_safe_formula(formula: str):
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

def sanitize_column_name(name):
    """
    Sanitizes a name for use as a SQL column name.
    Must match engine.py implementation.
    """
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if sanitized and sanitized[0].isdigit():
        sanitized = "_" + sanitized
    return sanitized.lower()

def formula_to_sql(formula: str):
    """
    Converts a formula like (m1 + m2) / m3 into a SQLite expression based on columns.
    """
    if formula in _sql_expressions_cache:
        return _sql_expressions_cache[formula]

    metrics = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]*\b', formula)
    metrics.sort(key=len, reverse=True)

    sql_expression = formula
    for m in metrics:
        # Sanitize metric names to match column names
        sanitized = sanitize_column_name(m)
        sql_expression = re.sub(r'\b' + re.escape(m) + r'\b', f"IFNULL({sanitized}, 0)", sql_expression)

    _sql_expressions_cache[formula] = sql_expression
    return sql_expression

def evaluate_formula(formula: str, data: dict):
    global _compiled_formulas_cache
    if formula not in _compiled_formulas_cache:
        if not is_safe_formula(formula):
            _compiled_formulas_cache[formula] = None
        else:
            try:
                metrics = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]*\b', formula)
                code = compile(formula, '<string>', 'eval')
                _compiled_formulas_cache[formula] = (code, metrics)
            except Exception:
                _compiled_formulas_cache[formula] = None

    cached = _compiled_formulas_cache[formula]
    if cached is None:
        return None

    code, metrics = cached
    try:
        # Build local namespace for eval - handle original keys and sanitized keys
        context = {}
        for m in metrics:
            val = data.get(m)
            if val is None:
                val = data.get(sanitize_column_name(m), 0)
            context[m] = float(val)
        return eval(code, {"__builtins__": {}}, context)
    except Exception:
        pass
    return None

def _get_last_from_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM data_points ORDER BY timestamp DESC LIMIT 1')
    return cursor.fetchone()

@app.get("/api/last")
async def get_last():
    row = await asyncio.to_thread(_get_last_from_db)
    if row:
        data = dict(row)
        # Remove 'id' and 'timestamp' from data part
        timestamp = data.pop("timestamp")
        data.pop("id")

        v_metrics = await get_virtual_metrics_map()
        if v_metrics:
            for name, formula in v_metrics.items():
                data[name] = evaluate_formula(formula, data)

        return {"timestamp": timestamp, "data": data}
    return {"error": "No data available"}

def _get_keys_from_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(data_points)")
    rows = cursor.fetchall()
    return [row[1] for row in rows if row[1] not in ('id', 'timestamp')]

@app.get("/api/keys")
async def get_keys():
    keys = await asyncio.to_thread(_get_keys_from_db)
    v_metrics = await get_virtual_metrics_map()
    keys.extend(v_metrics.keys())
    return sorted(list(set(keys)))

def _execute_query_one(query, params):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.fetchone()

@app.get("/api/data/{key}/last")
async def get_data_last(key: str):
    v_metrics = await get_virtual_metrics_map()
    sanitized_key = sanitize_column_name(key)

    if key in v_metrics:
        sql_expr = formula_to_sql(v_metrics[key])
    else:
        sql_expr = sanitized_key

    query = f"SELECT timestamp, {sql_expr} as value FROM data_points WHERE {sql_expr} IS NOT NULL ORDER BY timestamp DESC LIMIT 1"

    try:
        row = await asyncio.to_thread(_execute_query_one, query, [])
    except sqlite3.OperationalError as e:
        # Might happen if column doesn't exist yet
        if "no such column" in str(e):
             return {"timestamp": None, "value": None}
        raise HTTPException(status_code=400, detail=f"Error querying data: {e}")

    if row:
        return {"timestamp": row["timestamp"], "value": row["value"]}
    return {"timestamp": None, "value": None}

def _execute_query_all(query, params):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()

@app.get("/api/data/{key}/history")
async def get_data_history(
    key: str,
    start: Annotated[Optional[str], Query()] = None,
    end: Annotated[Optional[str], Query()] = None,
    gt: Annotated[Optional[float], Query()] = None,
    lt: Annotated[Optional[float], Query()] = None,
    eq: Annotated[Optional[float], Query()] = None,
    limit: Annotated[int, Query()] = 100
):
    v_metrics = await get_virtual_metrics_map()
    try:
        query, params = build_data_query(key, v_metrics, start, end, gt, lt, eq, limit)
        rows = await asyncio.to_thread(_execute_query_all, query, params)
    except sqlite3.OperationalError as e:
        if "no such column" in str(e):
             return []
        raise HTTPException(status_code=400, detail=f"Error querying data: {e}")

    return [[row["timestamp"], row["value"]] for row in rows]

@app.get("/api/data/{key}/stats")
async def get_data_stats(
    key: str,
    start: Annotated[Optional[str], Query()] = None,
    end: Annotated[Optional[str], Query()] = None,
    gt: Annotated[Optional[float], Query()] = None,
    lt: Annotated[Optional[float], Query()] = None,
    eq: Annotated[Optional[float], Query()] = None
):
    cache_key = (key, 'all', start, end, gt, lt, eq)
    now = time.time()
    if cache_key in _stats_cache:
        ts, result = _stats_cache[cache_key]
        if now - ts < STATS_CACHE_TTL:
            return result

    v_metrics = await get_virtual_metrics_map()
    sanitized_key = sanitize_column_name(key)

    if key in v_metrics:
        sql_expr = formula_to_sql(v_metrics[key])
    else:
        sql_expr = sanitized_key

    select_clause = (
        f"AVG({sql_expr}) as avg, "
        f"MIN({sql_expr}) as min, "
        f"MAX({sql_expr}) as max, "
        f"SUM({sql_expr}) as sum, "
        f"COUNT({sql_expr}) as count"
    )

    query = f"SELECT {select_clause} FROM data_points"
    conditions = []
    params = []
    start_ts = parse_relative_time(start)
    if start_ts:
        conditions.append("timestamp >= ?")
        params.append(start_ts)

    end_ts = parse_relative_time(end)
    if end_ts:
        conditions.append("timestamp <= ?")
        params.append(end_ts)

    if gt is not None:
        conditions.append(f"{sql_expr} > ?")
        params.append(gt)
    if lt is not None:
        conditions.append(f"{sql_expr} < ?")
        params.append(lt)
    if eq is not None:
        conditions.append(f"{sql_expr} = ?")
        params.append(eq)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    try:
        row = await asyncio.to_thread(_execute_query_one, query, params)
    except sqlite3.OperationalError as e:
        if "no such column" in str(e):
             return {"avg": None, "min": None, "max": None, "sum": None, "count": 0}
        raise HTTPException(status_code=400, detail=f"Error querying stats: {e}")

    if row:
        result = {
            "avg": row["avg"],
            "min": row["min"],
            "max": row["max"],
            "sum": row["sum"],
            "count": row["count"]
        }
    else:
        result = {"avg": None, "min": None, "max": None, "sum": None, "count": 0}

    if len(_stats_cache) >= STATS_CACHE_MAX_SIZE:
        oldest_key = min(_stats_cache.keys(), key=lambda k: _stats_cache[k][0])
        del _stats_cache[oldest_key]

    _stats_cache[cache_key] = (now, result)
    return result

@app.get("/api/data/{key}/stats/{stat_key}")
async def get_data_single_stat(
    key: str,
    stat_key: str,
    start: Annotated[Optional[str], Query()] = None,
    end: Annotated[Optional[str], Query()] = None,
    gt: Annotated[Optional[float], Query()] = None,
    lt: Annotated[Optional[float], Query()] = None,
    eq: Annotated[Optional[float], Query()] = None
):
    valid_stats = {"avg", "min", "max", "sum", "count"}
    if stat_key not in valid_stats:
        raise HTTPException(status_code=400, detail=f"Invalid stat_key: {stat_key}. Available: avg, min, max, sum, count")

    cache_key = (key, stat_key, start, end, gt, lt, eq)
    now = time.time()
    if cache_key in _stats_cache:
        ts, result = _stats_cache[cache_key]
        if now - ts < STATS_CACHE_TTL:
            return result

    v_metrics = await get_virtual_metrics_map()
    try:
        query, params = build_data_query(key, v_metrics, start, end, gt, lt, eq, aggregate=stat_key)
        row = await asyncio.to_thread(_execute_query_one, query, params)
    except sqlite3.OperationalError as e:
        if "no such column" in str(e):
             return {"value": None}
        raise HTTPException(status_code=400, detail=f"Error querying stat: {e}")

    result = {"value": row["value"]}
    if len(_stats_cache) >= STATS_CACHE_MAX_SIZE:
        oldest_key = min(_stats_cache.keys(), key=lambda k: _stats_cache[k][0])
        del _stats_cache[oldest_key]

    _stats_cache[cache_key] = (now, result)
    return result

@app.get("/api/chart/data")
async def get_chart_data(
    chart_type: Annotated[str, Query(alias="type", pattern="^(line|gauge)$")],
    metric: Annotated[str, Query()],
    period: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query()] = 100
):
    if chart_type == "gauge":
        return await get_data_last(metric)
    elif chart_type == "line":
        return await get_data_history(key=metric, start=period, limit=limit)

@app.get("/api/history")
async def get_history(start: Optional[str] = Query(None), end: Optional[str] = Query(None), limit: int = Query(100)):
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

    rows = await asyncio.to_thread(_execute_query_all, query, params)

    results = []
    for row in rows:
        data = dict(row)
        timestamp = data.pop("timestamp")
        data.pop("id")
        # Clean up None values
        data = {k: v for k, v in data.items() if v is not None}
        results.append({"timestamp": timestamp, "data": data})

    return results

@app.get("/api/virtual_metrics")
async def get_virtual_metrics():
    v_metrics = await get_virtual_metrics_map()
    return [{"name": k, "formula": v} for k, v in v_metrics.items()]

def _save_virtual_metric(name, formula):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO virtual_metrics (name, formula) VALUES (?, ?)', (name, formula))
    conn.commit()

@app.post("/api/virtual_metrics")
async def create_virtual_metric(name: str = Body(..., embed=True), formula: str = Body(..., embed=True)):
    if not is_safe_formula(formula):
        raise HTTPException(status_code=400, detail="Invalid formula. Only basic math and alphanumeric characters allowed.")

    try:
        await asyncio.to_thread(_save_virtual_metric, name, formula)
        invalidate_vm_cache()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "success"}

def _delete_virtual_metric(name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM virtual_metrics WHERE name = ?', (name,))
    conn.commit()

@app.delete("/api/virtual_metrics/{name}")
async def delete_virtual_metric(name: str):
    await asyncio.to_thread(_delete_virtual_metric, name)
    invalidate_vm_cache()
    return {"status": "success"}

def _get_charts_from_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM dashboard_charts')
    return cursor.fetchall()

@app.get("/api/charts")
async def get_charts():
    rows = await asyncio.to_thread(_get_charts_from_db)
    return [json.loads(row['config']) for row in rows]

def _save_charts_to_db(charts):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM dashboard_charts')
    for chart in charts:
        cursor.execute('INSERT INTO dashboard_charts (id, config) VALUES (?, ?)', (chart['id'], json.dumps(chart)))
    conn.commit()

@app.post("/api/charts")
async def save_charts(charts: List[Dict] = Body(...)):
    try:
        await asyncio.to_thread(_save_charts_to_db, charts)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "success"}

def _get_metric_configs_from_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM metric_configs')
    return cursor.fetchall()

@app.get("/api/metric_configs")
async def get_metric_configs():
    rows = await asyncio.to_thread(_get_metric_configs_from_db)
    return {row['key']: json.loads(row['config']) for row in rows}

def _save_metric_configs_to_db(configs: Dict[str, Dict]):
    conn = get_db_connection()
    cursor = conn.cursor()
    for key, config in configs.items():
        cursor.execute('INSERT OR REPLACE INTO metric_configs (key, config) VALUES (?, ?)', (key, json.dumps(config)))
    conn.commit()

@app.post("/api/metric_configs")
async def save_metric_configs(configs: Dict[str, Dict] = Body(...)):
    try:
        await asyncio.to_thread(_save_metric_configs_to_db, configs)
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
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
    now_utc = datetime.now(timezone.utc)
    if time_str.lower() == "today":
        return now_utc.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    match = re.match(r'^(\d+)([smhd])$', time_str.lower())
    if match:
        value, unit = match.groups()
        value = int(value)
        if unit == 's': delta = timedelta(seconds=value)
        elif unit == 'm': delta = timedelta(minutes=value)
        elif unit == 'h': delta = timedelta(hours=value)
        elif unit == 'd': delta = timedelta(days=value)
        return (now_utc - delta).strftime('%Y-%m-%d %H:%M:%S')
    return time_str

def build_data_query(
    key: str,
    v_metrics: Dict[str, str],
    start: Optional[str] = None,
    end: Optional[str] = None,
    gt: Optional[float] = None,
    lt: Optional[float] = None,
    eq: Optional[float] = None,
    limit: int = 100,
    aggregate: Optional[str] = None
):
    sanitized_key = sanitize_column_name(key)
    if key in v_metrics:
        sql_expr = formula_to_sql(v_metrics[key])
    else:
        sql_expr = sanitized_key

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
    params = []
    start_ts = parse_relative_time(start)
    if start_ts:
        conditions.append("timestamp >= ?")
        params.append(start_ts)
    end_ts = parse_relative_time(end)
    if end_ts:
        conditions.append("timestamp <= ?")
        params.append(end_ts)

    if gt is not None:
        conditions.append(f"{sql_expr} > ?")
        params.append(gt)
    if lt is not None:
        conditions.append(f"{sql_expr} < ?")
        params.append(lt)
    if eq is not None:
        conditions.append(f"{sql_expr} = ?")
        params.append(eq)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if not aggregate:
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

    return query, params

async def notify_new_data(data_payload):
    v_metrics = await get_virtual_metrics_map()
    if v_metrics:
        data_payload = data_payload.copy()
        data = data_payload["data"].copy()
        for name, formula in v_metrics.items():
            data[name] = evaluate_formula(formula, data)
        data_payload["data"] = data

    message = json.dumps({"type": "new_data", "payload": data_payload})
    await manager.broadcast(message)

app.mount("/", StaticFiles(directory="static", html=True), name="static")
