# ☀️ Pi Solar Monitor

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-v0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-v3.0%2B-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-Zero%202%20W-C51A4A?logo=raspberry-pi&logoColor=white)](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/)
[![Chart.js](https://img.shields.io/badge/Chart.js%20-v4.0-%20blue?logo=chartdotjs)](https://www.chartjs.org/)


A lightweight, modular data collection and monitoring system designed for solar power setups. It is explicitly compatible with the **Raspberry Pi Zero 2 W**.

The system periodically polls various data sources via custom "collectors", stores the results in a local SQLite database, and provides a real-time web dashboard and API for data access.

## 📺 Visual Overview

### Demo
<video src="screenshots/dashboard_demo.webm" autoplay loop muted playsinline controls width="100%">
</video>

### Dashboard
| Light Mode | Dark Mode |
| :---: | :---: |
| ![Dashboard Light](screenshots/dashboard_light.png) | ![Dashboard Dark](screenshots/dashboard_dark.png) |

## ✨ Features

- 🔌 **Modular Collection**: Run any executable script or binary (Python, Bash, etc.) to collect data.
- 🗄️ **Efficient Storage**: High-performance local SQLite data retention with zero external dependencies.
- 📊 **Real-time Dashboard**: Built-in web interface with live updates via WebSockets and historical visualization using Chart.js.
- 🧮 **Advanced Virtual Metrics**: Define calculated values using arithmetic formulas with secure and efficient server-side evaluation.
- ⚡ **Conditional Actions**: Define logic in `.cond` files to automate responses to system events.
- 🔌 **Robust API**: REST and WebSocket endpoints for easy access to live and historical data.
- 📲 **Automation Ready**: Integrated Macrodroid webhook support to trigger mobile notifications or logic.
- 🪶 **Ultra Lightweight**: Specifically optimized for low-power hardware like the Pi Zero 2 W.

## 🚀 High-Performance for Low-Power Hardware

The Pi Solar Monitor is engineered for maximum efficiency on the Raspberry Pi Zero 2 W:
- **Optimized SQLite**: Uses Write-Ahead Logging (WAL), `PRAGMA synchronous=NORMAL`, and optimized cache sizes for minimal disk I/O latency.
- **Asynchronous I/O**: Database writes are offloaded to separate threads, ensuring the main event loop remains responsive.
- **Compact API**: Specialized endpoints provide slim JSON payloads (up to 90% reduction) for fast chart rendering even on low-power mobile devices.
- **Secure Virtual Metrics**: Formulas are safely pre-validated using Python's `ast` module and evaluated efficiently with cached SQL expressions.
- **Visual Cues**: Subtle CSS pulsing animations provide real-time connection status without heavy CPU overhead.

## ⏱️ Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/nkhearn/Pi-Solar-monitor.git
cd pi-solar-monitor

# Install dependencies
pip install -r requirements.txt

# Initialize the database
python3 init_db.py
```

### Running

To start the collection engine and web server:
```bash
python3 main.py
```
The dashboard will be available at `http://<your-pi-ip>:8000`.

---

## 📚 Documentation

Detailed documentation for installation, customization, and advanced usage is available in the `docs/` directory:

- [**📘 Documentation Home**](docs/Home.md) - Overview and quick links to all sections.
- [**⚙️ Hardware Setup**](docs/installation.md#hardware-setup) - Enabling 1-Wire and connecting sensors/inverters.
- [**🚀 Installation Guide**](docs/installation.md) - Full setup instructions and systemd service configuration.
- [**🖥️ Usage Guide**](docs/usage.md) - Dashboard customization and Macrodroid integration.
- [**🔌 Data Collectors**](docs/collectors.md) - How to write and schedule your own sensors.
- [**⚡ Conditional Actions**](docs/conditions.md) - Automation based on real-time and historical metrics.
- [**📡 REST API**](docs/api.md) - Endpoint documentation and query parameters.
- [**🛰️ WebSockets**](docs/websockets.md) - Real-time data streaming specifications.

---
*Note: This project stores all historical data indefinitely in `data/inverter_logs.db`. Ensure your SD card has sufficient space for long-term use.*
