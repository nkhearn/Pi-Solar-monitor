# 🧮 Virtual Metrics Documentation

Virtual metrics allow you to create new data points by performing arithmetic calculations on existing ones. They are calculated in real-time as new data arrives and can be used throughout the system just like physical metrics.

---

## 🚀 Concept

A virtual metric is defined by a **Name** and a **Formula**.
- **Real-time calculation**: When a new data point is collected, all virtual metrics are immediately recalculated using the updated values.
- **WebSocket updates**: Recalculated values are broadcast to the dashboard in real-time.
- **Historical Analysis**: Virtual metrics can be queried for history and statistics. The system automatically converts formulas into optimized SQLite expressions for retroactive calculations.
- **Timestamps**: A virtual metric's timestamp is derived from the **latest (maximum)** timestamp of all its constituent physical metrics, ensuring accurate synchronization.

---

## 🧮 Formula Capabilities

Formulas are evaluated safely on the server. The following elements are supported:

### 🔢 Supported Operators
- **Basic Math**: `+` (addition), `-` (subtraction), `*` (multiplication), `/` (division).
- **Grouping**: `(` and `)` to control operation order.
- **Constants**: Integers and floating-point numbers (e.g., `100`, `0.5`).

### 🏷️ Referencing Metrics
You can use any existing physical or virtual metric name in your formula.
- **Sanitization**: Metric names are automatically sanitized to match the internal database format (lowercase, underscores instead of spaces/special characters).
- **Nested Metrics**: Virtual metrics can reference other virtual metrics. The system handles dependency ordering automatically.

### 🛡️ Safety & Constraints
- **Secure Evaluation**: Formulas are parsed into an Abstract Syntax Tree (AST) before execution to prevent arbitrary code execution.
- **No Functions**: Formulas are limited to arithmetic operations. Functions like `sin()`, `abs()`, or `round()` are **not** supported within the virtual metric definition (though they are supported in the [Condition Engine](conditions.md)).
- **No History in Formulas**: Virtual metrics can only reference the **latest** value of other metrics. You cannot access historical data (e.g., `avg(pv_power, 1h)`) directly within a formula.

---

## 📖 Examples

### 🟢 Simple Virtual Metrics
Used for basic scaling or unit conversion.

- **Convert Watts to Kilowatts**:
  - `name`: `pv_power_kw`
  - `formula`: `pv_power / 1000`
- **Battery Percentage (Estimate)**:
  - `name`: `battery_soc_estimate`
  - `formula`: `(battery_voltage - 44) / (54 - 44) * 100`

### 🟡 Complex Virtual Metrics
Performing calculations across multiple physical sensors.

- **System Efficiency**:
  - `name`: `efficiency`
  - `formula`: `(load_power + battery_charge_power) / pv_power`
- **Total Power Input**:
  - `name`: `total_input`
  - `formula`: `pv_power + grid_power + generator_power`

### 🔴 Highly Complex Virtual Metrics
Utilizing nested virtual metrics and multiple data sources.

- **Net Energy Flow**:
  - `name`: `net_flow`
  - `formula`: `pv_power - load_power - charger_loss`
  - *Note: `charger_loss` could itself be another virtual metric defined as `battery_charge_power * 0.05`.*
- **Customized Load Priority Index**:
  - `name`: `load_priority_score`
  - `formula`: `(battery_voltage * 0.6) + (pv_power / 1000 * 0.4)`

---

## 📊 Sum, Avg, and Statistics Facilities

While formulas themselves are arithmetic-only, you can perform powerful aggregations on virtual metrics using the **REST API**.

The system retroactively calculates these stats by converting your formula into a SQL expression.

### 📡 Available Stats Endpoints
- `/api/data/{key}/stats`: Returns `avg`, `min`, `max`, `sum`, and `count`.
- `/api/data/{key}/stats/{stat_key}`: Returns a single value (e.g., just the `avg`).

### 💡 Examples
- **Average efficiency today**:
  - `GET /api/data/efficiency/stats/avg?start=today`
- **Total PV yield (sum of power) for the last hour**:
  - `GET /api/data/pv_power_kw/stats/sum?start=1h`

---

## 🛠️ Management

### Web Dashboard
1. Click the **🧮 Virtual Metrics** button in the header.
2. View existing metrics or add new ones.
3. Deleting a virtual metric is instant and does not affect the underlying physical data.

### API Access
- **List All**: `GET /api/virtual_metrics`
- **Create/Update**: `POST /api/virtual_metrics` (requires `name` and `formula`)
- **Delete**: `DELETE /api/virtual_metrics/{name}`

For full technical details, see the [REST API Documentation](api.md#virtual-metric-management-endpoints).
