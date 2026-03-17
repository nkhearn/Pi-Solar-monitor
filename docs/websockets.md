# WebSocket API Documentation

The Pi Solar Monitor uses WebSockets to push live data updates to clients as soon as they are collected.

## Connection
- **URL**: `ws://<your-pi-ip>:8000/ws`
- **Protocol**: Standard WebSocket

The server maintains a list of active connections and broadcasts a message to all of them every time a new data point is saved to the database (typically every minute).

---

## Message Format

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

**Example**:
```json
{
    "type": "new_data",
    "payload": {
        "timestamp": "2026-03-17 15:45:01.080",
        "data": {
            "solar_prediction": 1523.08,
            "battery_voltage": 13.2
        }
    }
}
```

---

## Client Implementation Example (JavaScript)

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

## Considerations
- **Read-Only**: Currently, the WebSocket is one-way (Server -> Client). Any messages sent from the client to the server are ignored.
- **Auto-Reconnect**: It is highly recommended to implement an auto-reconnect strategy on the client side, as shown in the example above.
