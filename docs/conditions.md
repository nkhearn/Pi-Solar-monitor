# ⚡ Conditional Actions

The **pi solar monitor** supports automated actions based on custom conditions. These are defined in `.cond` files within the `conditions/` directory.

## 📂 Directory Structure
Place your condition files in the root `conditions/` folder:
```text
/conditions
  ├── high_voltage_alert.cond
  └── battery_low.cond
```

## 📝 File Format
Condition files use a simple section-based format:

```ini
[conditions]
[or]
/api/data/pv_voltage/last > 240
/api/data/pv_voltage/last < 90

[and]
round('/api/data/pv_voltage/stats/avg?start=1h', 1) != 0

[action]
python3 ~/actions/notify.py "Voltage Anomaly Detected"

[cooldown]
5m
```

### 🔍 Sections Explained

| Section | Description |
| :--- | :--- |
| `[or]` | One or more conditions. If any are true, the OR block passes. |
| `[and]` | One or more conditions. ALL must be true for the AND block to pass. |
| `[action]` | The shell command to execute when conditions are met. |
| `[cooldown]` | Prevents the action from re-triggering for a set time (e.g., `5m`, `1h`, `1d`). |

## 🛠️ Data Paths
You can reference any system data using internal API paths. The engine fetches these values directly from the database for high performance.

### Last Value
`'/api/data/{key}/last'`
Returns the most recent value for a specific key.

### Stats
`'/api/data/{key}/stats/{stat_key}?start={timeframe}'`
Available stat keys: `avg`, `min`, `max`, `sum`, `count`.
Example: `'/api/data/battery_voltage/stats/avg?start=24h'`

## 🧮 Math & Logic
Conditions are evaluated as Python expressions. You can use standard operators (`>`, `<`, `==`, `!=`, `+`, `-`, `*`, `/`) and basic functions:
- `round(value, precision)`
- `abs(value)`
- `min(a, b)`
- `max(a, b)`
- `int()`, `float()`, `bool()`

> [!IMPORTANT]
> The engine evaluates `(OR_conditions) AND (AND_conditions)`. If a section is missing, it is considered passed.

## ⏱️ Cooldowns
Cooldowns are tracked in `/tmp/pi_solar_cooldowns.json`.
- They persist across engine restarts but are stored in temporary storage.
- Entries older than 48 hours are automatically purged to keep the system lean.
