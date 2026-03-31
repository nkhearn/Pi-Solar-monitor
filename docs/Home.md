# ☀️ Pi-Solar-Monitor Documentation

Welcome to the **Pi-Solar-Monitor** documentation! This project provides a lightweight, robust system for monitoring solar inverter data, specifically optimized for the Raspberry Pi Zero 2 W.

---

## 🚀 Quick Navigation

Explore the core sections to get started, customize your setup, or integrate with other tools.

| Section | Description |
| :--- | :--- |
| [**⚙️ Installation**](installation.md) | How to set up the hardware and software. |
| [**🖥️ Usage**](usage.md) | Dashboard overview, themes, and customization. |
| [**🔌 Collectors**](collectors.md) | Managing and creating data collection scripts. |
| [**⚡ Conditional Actions**](conditions.md) | Automate actions based on live system data. |
| [**📡 REST API**](api.md) | Detailed documentation on data endpoints. |
| [**🛰️ WebSockets**](websockets.md) | Real-time data streaming specifications. |

---

## 🔍 Overview

Pi-Solar-Monitor is designed to be:
- **Lightweight**: Minimal CPU/RAM footprint (~512MB RAM target).
- **Modular**: Easy to add new sensors via custom collectors.
- **Real-time**: Live updates via WebSockets and a responsive dashboard.
- **Durable**: Reliable local SQLite storage with Write-Ahead Logging (WAL) and optimized performance parameters.
- **Automated**: Integrated conditional logic engine for smart triggers.

---

## ✨ New Features

- **Advanced Virtual Metrics**: Create calculated values using arithmetic formulas with secure server-side evaluation.
- **Conditional Action Engine**: Define complex logic in `.cond` files to trigger shell commands or scripts based on system metrics.
- **High-Performance API**: Slim history and stats endpoints reduce payload sizes by up to 90%.
- **Smart Data Persistence**: SQLite optimized for SD cards with background writes.
- **Real-time UX**: Pulsing status indicators and instant dashboard updates.

---
*This documentation is maintained in the `docs/` folder of the repository.*
