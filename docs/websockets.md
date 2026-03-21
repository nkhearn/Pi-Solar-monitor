# ⚡ WebSocket API Documentation 💓

The **Pi Solar Monitor** uses WebSockets to push live data updates to clients as soon as they are collected, ensuring your dashboard is always in sync.

---

## 🔗 Connection

- **URL**: `ws://<your-pi-ip>:8000/ws`
- **Protocol**: Standard WebSocket

The server maintains a list of active connections and broadcasts a message to all of them every time a new data point is saved to the database (typically every minute).

### 📡 Data Flow
```text
[ Collectors ] --(JSON)--> [ Engine ] --(Save)--> [ SQLite DB ]
                                |
                         [ WebSocket Server ]
                                |
                         (JSON Broadcast)
                                |
                   [-------------------------]
                   |            |            |
              [ Browser ]  [ Browser ]  [ Other App ]
```

---

## 📦 Message Format

All messages sent from the server are JSON strings.

### `new_data` Message
Sent when a new collection cycle completes.

**Structure**:
```json
{
    "type": "new_data",
    "payload": {
        "timestamp": "YYYY-MM-DD HH:MM:SS.sss",
        "data": {
            "key1": value,
            "key2": value,
            ...
        }
    }
}
```

---

## 💻 Client Implementation Example (JavaScript)

```javascript
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const socket = new WebSocket(`${protocol}//${window.location.host}/ws`);

socket.onopen = () => {
    console.log('Connected to Solar Monitor WebSocket');
};

socket.onmessage = (event) => {
    const message = JSON.parse(event.data);

    if (message.type === 'new_data') {
        const { timestamp, data } = message.payload;
        console.log(`New data at ${timestamp}:`, data);

        // Update your UI here
        updateDashboard(data);
    }
};

socket.onclose = () => {
    console.log('Disconnected. Attempting to reconnect...');
    setTimeout(connectWebSocket, 5000);
};
```

---

## 💡 Client Considerations

> [!IMPORTANT]
> **Read-Only**: The WebSocket is currently **one-way** (Server -> Client). Any messages sent from the client to the server will be ignored.

- **Auto-Reconnect**: Always implement a reconnection strategy. Network blips or server restarts shouldn't break your live view.
- **Payload Size**: The system is designed to send only the latest data point to keep bandwidth low, making it perfect for the **Pi Zero 2 W**.
