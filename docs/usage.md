# 🖥️ Usage Guide

The **Pi Solar Monitor** provides a real-time web dashboard and automation integrations to monitor and manage your solar power system.

---

## 📊 Web Dashboard

Access the dashboard at `http://<your-pi-ip>:8000`.

### Real-time Metrics

The dashboard automatically categorizes and displays metrics collected by the system.
- **Solar ☀️**: PV voltage, power, and yield.
- **Battery 🔋**: Voltage, charge/discharge current, and state of charge (SOC).
- **Temperature 🌡️**: Readings from your DS18B20 sensors.

![Dashboard Light Mode](../screenshots/dashboard_light.png)

---

## ✨ Dashboard Customization

### 🎨 Themes
Toggle between **Light** and **Dark** modes using the toggle in the header. Your preference is saved in your browser's local storage.

![Dashboard Dark Mode](../screenshots/dashboard_dark.png)

### 📈 Adding Charts
You can add custom charts to visualize any numeric metric.
1. Click the **+ Add Chart** button.
2. Select the **Metric** to visualize.
3. Choose the **Chart Type**:
    - **Line Chart**: Shows historical trends over time (1h, 24h, 7d).
    - **Gauge**: Shows the latest value on a semi-circular scale.
4. Set a **Max Value** for Gauge charts.

![Add Chart Modal](../screenshots/add_chart_modal.png)

### 🛠️ Managing Charts
- **Time Range**: On line charts, use the 1h, 24h, or 7d buttons to change the scale.
- **Removing**: Click the **Remove** button on any chart card to delete it from your dashboard.

---

## 📲 Automation (Macrodroid)

The system can trigger Macrodroid webhooks on every data collection cycle (every minute), allowing for mobile notifications and complex logic.

### ⚙️ Configuration

1. Open `engine.py`.
2. Locate the `MACRODROID_URL` constant.
3. Replace the placeholder URL with your device's unique Macrodroid webhook URL.

```python
MACRODROID_URL = "https://trigger.macrodroid.com/YOUR_DEVICE_UUID/solar_data"
```

> [!TIP]
> **Best Practices for Automation**:
> - Use the **battery_voltage** to trigger alerts when it drops below a threshold.
> - Monitor **solar_prediction** to decide when to run heavy loads.
> - Send a "Critical" notification if **inverter_error** is not empty.

### 📦 Data Payload

The entire collected data object is sent as a JSON payload in a POST request. You can use Macrodroid's "HTTP Request" trigger and parse the JSON variables to create custom automations (e.g., "Notify me if battery is below 48V").
