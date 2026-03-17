import sqlite3
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

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

@app.get("/api/history")
async def get_history(start: Optional[str] = None, end: Optional[str] = None, limit: int = 100):
    conn = get_db_connection()
    cursor = conn.cursor()

    query = 'SELECT * FROM data_points'
    params = []

    conditions = []
    if start:
        conditions.append('timestamp >= ?')
        params.append(start)
    if end:
        conditions.append('timestamp <= ?')
        params.append(end)

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

# Helper function to be called by the engine
async def notify_new_data(data):
    message = json.dumps({"type": "new_data", "payload": data})
    await manager.broadcast(message)

# Serve static files for the dashboard
app.mount("/", StaticFiles(directory="static", html=True), name="static")
