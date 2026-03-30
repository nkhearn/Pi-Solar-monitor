# ⚡ Conditional Actions

The **pi solar monitor** supports automated actions based on custom conditions. These are defined in `.cond` files within the `conditions/` directory.

## 📂 Directory Structure
Place your condition files in the root `conditions/` folder:
```text
/conditions
  ├── battery_low.cond
  ├── voltage_anomaly.cond
  └── smart_load.cond
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

> [!IMPORTANT]
> The engine evaluates `(OR_conditions) AND (AND_conditions)`. If a section is missing, it is considered passed.

---

## 💡 Examples

### 🟢 Simple: Low Battery Alert
Trigger a notification when the battery voltage drops below a threshold.

**`battery_low.cond`**
```ini
[or]
/api/data/battery_voltage/last < 11.5

[action]
python3 ~/scripts/notify.py "Low Battery Alert: Check system!"

[cooldown]
1h
```

### 🟡 Complex: Load Shedding
Reduce high power loads if the PV voltage is outside normal operating range AND the current load is high.

**`load_shedding.cond`**
```ini
[or]
/api/data/pv_voltage/last > 240
/api/data/pv_voltage/last < 90

[and]
/api/data/load_watts/last > 1000

[action]
/usr/bin/python3 ~/scripts/smart_switch.py --off "Heater"

[cooldown]
15m
```

### 🔴 Very Complex: Smart Conservation Mode
Enable conservation mode if the 1-hour average battery voltage is low, OR if the current voltage is significantly lower than the 24-hour average. Only trigger during daylight hours when not charging at full power.

**`smart_conservation.cond`**
```ini
[or]
# 1-hour average is low
round('/api/data/battery_voltage/stats/avg?start=1h', 2) < 12.0

# OR current voltage is 0.5V lower than the 24-hour average
/api/data/battery_voltage/last < ('/api/data/battery_voltage/stats/avg?start=24h' - 0.5)

[and]
# Only trigger if PV panels are active (Daylight)
/api/data/pv_voltage/last > 20

# And not currently receiving significant solar power
/api/data/solar_watts/last < 500

[action]
/home/pi/scripts/control_system.sh --mode=conservation --reason="Voltage drop detected"

[cooldown]
30m
```

---

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

## ⏱️ Cooldowns
Cooldowns are tracked in `/tmp/pi_solar_cooldowns.json`.
- They persist across engine restarts but are stored in temporary storage.
- Entries older than 48 hours are automatically purged to keep the system lean.
- Format: `s` (seconds), `m` (minutes), `h` (hours), `d` (days). Default is seconds if no unit is provided.
