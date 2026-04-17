# 📉 Charts Explorer

The **Charts Explorer** is a powerful tool within the Pi Solar Monitor that allows for deep analysis of historical data. Unlike the main dashboard, which focuses on real-time monitoring and preset charts, the Charts Explorer gives you full control over what data to visualize and over what time period.

---

## 🚀 Overview

Access the Charts Explorer by clicking the 📈 icon in the main dashboard header.

### Key Features
- **Multi-Metric Support**: Compare multiple metrics on a single chart.
- **Dual Y-Axes**: Automatically uses a secondary Y-axis when multiple metrics with different scales are selected.
- **Custom Time Ranges**: Select specific start and end dates/times using the native system picker.
- **Dynamic Chart Types**: Toggle between Line, Bar, and Area charts.
- **URL Persistence**: Your selection is saved in the URL, making it easy to bookmark or share specific views.

---

## 🛠️ How to Use

### 1. Selecting Metrics
On the left side of the controls (or top on mobile), you'll find a multi-select list of all available metrics.
- **Single Metric**: Click a metric to select it.
- **Multiple Metrics**: Hold `Ctrl` (Windows/Linux) or `Cmd` (Mac) while clicking to select multiple data points for comparison.

### 2. Choosing a Chart Type
Choose how you want your data to be visualized:
- **Line**: Best for seeing trends over time.
- **Bar**: Useful for comparing discrete intervals or yield.
- **Area**: Similar to line charts but with a filled area below the line for better visual impact.

### 3. Setting the Time Range
The Charts Explorer defaults to the last 24 hours. You can customize this using the **Start Time** and **End Time** inputs.
- Click the input to open your browser's native date and time picker.
- After changing the times, click **Update Chart** to fetch the new data.

---

## 💡 Pro Tips

### URL Sharing
The Charts Explorer automatically updates the browser's URL as you change selections. This means you can:
- **Bookmark** a specific view (e.g., "Last Week's Battery Voltage").
- **Share** a specific data finding with someone else by just sending the link.

### Dual Axis Visualization
When you select multiple metrics, the first metric selected will use the **left Y-axis**, and all subsequent metrics will share the **right Y-axis**. This allows you to compare different units of measurement (e.g., Watts and Volts) on the same graph without one flattening the other.

### Performance
The explorer is optimized to fetch up to 5,000 data points per metric. On a Raspberry Pi Zero 2 W, selecting very long time ranges with many metrics might take a few seconds to load. A loading spinner will indicate that data is being retrieved.
