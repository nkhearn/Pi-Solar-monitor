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
import numpy as np
from scipy.optimize import curve_fit

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
_latest_metrics_cache = {}
_cache_initialized = False
_cache_lock = asyncio.Lock()

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

async def ensure_cache_initialized():
    global _cache_initialized
    if not _cache_initialized:
        async with _cache_lock:
            if not _cache_initialized:
                await asyncio.to_thread(_init_latest_metrics)
                # After physical metrics are loaded, calculate virtual ones
                v_metrics = await get_virtual_metrics_map()
                current_values = {k: v["value"] for k, v in _latest_metrics_cache.items()}
                for name, formula in v_metrics.items():
                    val = evaluate_formula(formula, current_values)
                    if val is not None:
                        # Find the latest timestamp among components if possible
                        ts = "1970-01-01 00:00:00"
                        metrics_in_formula = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]*\b', formula)
                        for m in metrics_in_formula:
                            m_san = sanitize_column_name(m)
                            if m_san in _latest_metrics_cache:
                                if _latest_metrics_cache[m_san]["timestamp"] > ts:
                                    ts = _latest_metrics_cache[m_san]["timestamp"]
                        _latest_metrics_cache[name] = {"value": val, "timestamp": ts}
                _cache_initialized = True

def _init_latest_metrics():
    global _latest_metrics_cache
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(data_points)")
        columns = [row[1] for row in cursor.fetchall() if row[1] not in ('id', 'timestamp')]
    except sqlite3.Error:
        columns = []

    new_cache = {}
    for col in columns:
        try:
            # Explicitly select the column and timestamp where column is NOT NULL
            cursor.execute(f"SELECT {col}, timestamp FROM data_points WHERE {col} IS NOT NULL ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                new_cache[col] = {"value": row[col], "timestamp": row["timestamp"]}
        except sqlite3.Error:
            pass

    _latest_metrics_cache = new_cache

def invalidate_vm_cache():
    global _virtual_metrics_cache
    global _sql_expressions_cache
    global _compiled_formulas_cache
    global _cache_initialized
    global _latest_metrics_cache
    _virtual_metrics_cache = None
    _sql_expressions_cache = {}
    _compiled_formulas_cache = {}
    _cache_initialized = False
    _latest_metrics_cache = {}

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
    await ensure_cache_initialized()
    if not _latest_metrics_cache:
        return {"error": "No data available"}

    # Return a merged view. Note that for the dashboard, it wants a 'timestamp' and 'data'.
    # Since we now have per-metric timestamps, we provide the latest overall timestamp
    # as the primary one, but include all individual metrics.
    latest_ts = max((m["timestamp"] for m in _latest_metrics_cache.values()), default=None)
    data_with_timestamps = {k: v["value"] for k, v in _latest_metrics_cache.items()}
    # We also include a special field for individual timestamps if the frontend wants them
    metric_timestamps = {k: v["timestamp"] for k, v in _latest_metrics_cache.items()}

    return {
        "timestamp": latest_ts,
        "data": data_with_timestamps,
        "metric_timestamps": metric_timestamps
    }

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
    await ensure_cache_initialized()
    sanitized_key = sanitize_column_name(key)

    if key in _latest_metrics_cache:
        return _latest_metrics_cache[key]
    elif sanitized_key in _latest_metrics_cache:
        return _latest_metrics_cache[sanitized_key]

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

def bell_curve(x, a, x0, sigma):
    """Gaussian model for a single solar day."""
    return a * np.exp(-(x - x0)**2 / (2 * sigma**2))

@app.get("/api/daily_report")
async def get_daily_report(date: str = Query(...)):
    """
    Calculates various metrics for a specific date (YYYY-MM-DD).
    """
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    start_str = target_date.strftime('%Y-%m-%d 00:00:00')
    end_str = target_date.strftime('%Y-%m-%d 23:59:59')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch all data for that day
    cursor.execute("SELECT * FROM data_points WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp ASC", (start_str, end_str))
    rows = cursor.fetchall()

    if not rows:
        return {"error": "No data found for this date", "date": date}

    data_by_key = {}
    timestamps = []
    for row in rows:
        timestamps.append(row['timestamp'])
        for key in row.keys():
            if key in ('id', 'timestamp'): continue
            if key not in data_by_key: data_by_key[key] = []
            data_by_key[key].append(row[key])

    # Fill Nones with 0 for power/voltage calculations
    def get_clean_series(key):
        if key not in data_by_key: return np.array([])
        return np.array([float(x) if x is not None else 0.0 for x in data_by_key[key]])

    results = []

    # 1. Missed PV Power Yield (Clipping)
    pv_power = get_clean_series('pv_input_power')
    clipping_report = {"title": "PV Power Clipping", "value": "N/A", "unit": "Wh", "partial": False}
    if len(pv_power) > 60:
        max_observed = np.max(pv_power)
        if max_observed > 10:
            times = np.arange(len(pv_power))
            mask = (pv_power > (max_observed * 0.15)) & (pv_power < (max_observed * 0.80))
            x_train = times[mask]
            y_train = pv_power[mask]

            if len(x_train) >= 60:
                try:
                    p0 = [max_observed * 1.1, np.argmax(pv_power), 150]
                    lower = [max_observed, 0, 50]
                    upper = [max_observed * 3, len(pv_power) * 1.5, 600]
                    popt, _ = curve_fit(bell_curve, x_train, y_train, p0=p0, bounds=(lower, upper))
                    theoretical_p = bell_curve(times, *popt)
                    missed_w = np.maximum(0, theoretical_p - pv_power)
                    # Assuming 1-minute intervals roughly.
                    # More accurately: (total_missed_watts * minutes_between_samples) / 60
                    # For simplicity and matching user script: sum / 60
                    total_missed_wh = np.sum(missed_w) / 60
                    clipping_report["value"] = round(total_missed_wh, 2)
                    if max_observed > popt[0] * 0.95:
                        clipping_report["status"] = "Clipping Detected"
                    else:
                        clipping_report["status"] = "Normal"
                except:
                    clipping_report["error"] = "Irregular data for curve fitting"
            else:
                clipping_report["error"] = "Insufficient active sun data"
        else:
            clipping_report["value"] = 0
            clipping_report["status"] = "Night time / Low Power"
    else:
        clipping_report["error"] = "Insufficient data points"

    if len(rows) < 1300: clipping_report["partial"] = True # ~90% of a day
    results.append(clipping_report)

    # 2. Daily Self-Consumption Ratio (%)
    # (Solar used by load) / (Total Solar)
    # Solar used by load = Total Load - (Grid Power if any) - (Battery Discharge if positive)
    # This is complex without knowing all flows. Let's simplify:
    # If battery is charging: Solar used = Load + Charge
    # If battery is discharging: Solar used = Solar (all goes to load)
    # Ratio = (Solar - Battery Charge) / Solar? No.
    # Self consumption = (Solar - Export) / Solar. We don't have export.
    # Let's use: (Load met by Solar) / (Total Solar)
    load_power = get_clean_series('ac_output_active_power')
    pv_power = get_clean_series('pv_input_power')
    batt_charge = get_clean_series('battery_charging_current') * get_clean_series('battery_voltage')

    # Solar used directly = min(PV, Load) - actually it's PV - Charge (if we assume PV goes to battery first or load first)
    # Let's use: (PV energy - Battery Charge energy) / PV energy  (percentage of solar that went straight to load)
    pv_wh = np.sum(pv_power) / 60
    charge_wh = np.sum(batt_charge) / 60

    self_cons = {"title": "Solar Self-Consumption", "value": "N/A", "unit": "%", "partial": len(rows) < 1300}
    if pv_wh > 10:
        direct_wh = max(0, pv_wh - charge_wh)
        ratio = (direct_wh / pv_wh) * 100
        self_cons["value"] = round(min(100, ratio), 1)
    results.append(self_cons)

    # 3. Battery Round-trip Efficiency (%)
    # Discharge / Charge
    batt_disch = get_clean_series('battery_discharge_current') * get_clean_series('battery_voltage')
    disch_wh = np.sum(batt_disch) / 60
    # charge_wh already calculated
    batt_eff = {"title": "Battery Efficiency", "value": "N/A", "unit": "%", "partial": len(rows) < 1300}
    if charge_wh > 10:
        eff = (disch_wh / charge_wh) * 100
        batt_eff["value"] = round(min(100, eff), 1)
    results.append(batt_eff)

    # 4. Solar Harvest Efficiency
    # Actual PV Wh / Predicted Wh
    solar_predict = get_clean_series('solar_prediction')
    # Solar prediction might only be available in some rows or one row.
    # Let's take the max or the one from the start of the day.
    predicted_wh = np.max(solar_predict) if len(solar_predict) > 0 else 0
    harvest_eff = {"title": "Solar Harvest Efficiency", "value": "N/A", "unit": "%", "partial": len(rows) < 1300}
    if predicted_wh > 10 and pv_wh > 0:
        h_ratio = (pv_wh / predicted_wh) * 100
        harvest_eff["value"] = round(h_ratio, 1)
    results.append(harvest_eff)

    # 5. Peak Load Hour
    # Hour with max average load
    peak_load_hour = {"title": "Peak Load Hour", "value": "N/A", "unit": "", "partial": len(rows) < 1300}
    if len(load_power) > 60:
        hourly_loads = []
        for h in range(24):
            h_start = f"{target_date} {h:02d}:00:00"
            h_end = f"{target_date} {h:02d}:59:59"
            mask = [(ts >= h_start and ts <= h_end) for ts in timestamps]
            if any(mask):
                avg_l = np.mean(load_power[mask])
                hourly_loads.append((h, avg_l))
        if hourly_loads:
            best_h, val = max(hourly_loads, key=lambda x: x[1])
            peak_load_hour["value"] = f"{best_h:02d}:00"
            peak_load_hour["description"] = f"Avg load: {val:.0f}W"
    results.append(peak_load_hour)

    # 6. Grid/Generator Dependency
    # AC Input Wh / (AC Input Wh + PV Wh + Battery Discharge Wh)
    ac_input = get_clean_series('ac_input_active_power') # Might not exist, fallback to 0
    ac_wh = np.sum(ac_input) / 60
    total_in_wh = ac_wh + pv_wh + disch_wh
    grid_dep = {"title": "Energy Source: AC Input", "value": "N/A", "unit": "%", "partial": len(rows) < 1300}
    if total_in_wh > 10:
        dep_ratio = (ac_wh / total_in_wh) * 100
        grid_dep["value"] = round(dep_ratio, 1)
    results.append(grid_dep)

    return {
        "date": date,
        "metrics": results,
        "sample_count": len(rows)
    }

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
    await ensure_cache_initialized()

    new_data = data_payload["data"]
    ts = data_payload["timestamp"]

    # Update cache with new physical metrics
    for k, v in new_data.items():
        sanitized_k = sanitize_column_name(k)
        _latest_metrics_cache[sanitized_k] = {"value": v, "timestamp": ts}

    # Recalculate all virtual metrics using the updated cache
    v_metrics = await get_virtual_metrics_map()
    current_values = {k: v["value"] for k, v in _latest_metrics_cache.items()}
    for name, formula in v_metrics.items():
        val = evaluate_formula(formula, current_values)
        if val is not None:
            # For virtual metrics, use the latest timestamp of its components
            comp_ts = "1970-01-01 00:00:00"
            metrics_in_formula = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_]*\b', formula)
            for m in metrics_in_formula:
                m_san = sanitize_column_name(m)
                if m_san in _latest_metrics_cache:
                    if _latest_metrics_cache[m_san]["timestamp"] > comp_ts:
                        comp_ts = _latest_metrics_cache[m_san]["timestamp"]
            _latest_metrics_cache[name] = {"value": val, "timestamp": comp_ts}

    # Prepare merged payload for broadcast
    merged_data = {k: v["value"] for k, v in _latest_metrics_cache.items()}
    merged_timestamps = {k: v["timestamp"] for k, v in _latest_metrics_cache.items()}

    broadcast_payload = {
        "timestamp": ts,
        "data": merged_data,
        "metric_timestamps": merged_timestamps
    }

    message = json.dumps({"type": "new_data", "payload": broadcast_payload})
    await manager.broadcast(message)

app.mount("/", StaticFiles(directory="static", html=True), name="static")
