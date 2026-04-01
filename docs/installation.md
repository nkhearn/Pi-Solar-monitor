# 🛠️ Installation Guide

This guide provides detailed instructions for setting up the **Pi Solar Monitor** on a Raspberry Pi, specifically optimized for the **Pi Zero 2 W**.

---

## 🔌 Phase 1: Hardware Setup

### 🌡️ 1-Wire Interface (for Temperature Sensors)

The system uses **DS18B20** sensors via the 1-Wire protocol. This must be enabled in the Pi's configuration.

1.  **Enable via raspi-config:**
    - Run `sudo raspi-config`.
    - Go to **Interface Options** -> **1-Wire**.
    - Select **Yes** to enable the interface.
    - Reboot the Pi: `sudo reboot`.

2.  **Manual Enable:**
    - Edit `/boot/config.txt`: `sudo nano /boot/config.txt`.
    - Add `dtoverlay=w1-gpio` to the end of the file.
    - Save and reboot.

> [!TIP]
> Ensure your DS18B20 sensors are correctly wired with a 4.7kΩ pull-up resistor between the Data and 3.3V lines for reliable readings.

### 🔋 Inverter Connection

The system typically communicates with Voltronic-compatible inverters via USB.

- **Direct Link**: Connect the inverter's USB port to the Pi.
- **Device Path**: The default `inverter.py` collector expects the device at `/dev/hidraw0`.
- **Permissions**: You may need to grant access permissions: `sudo chmod a+rw /dev/hidraw0`.

---

## 💻 Phase 2: Software Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd pi-solar-monitor
```

### 2. Install Python Dependencies

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)

It is recommended to use a virtual environment or ensure all system dependencies are met.

```bash
pip install -r requirements.txt
```

> [!NOTE]
> For data migration from EmonCMS or for running automated tests, you may need additional packages:
> - **Migration**: `mysql-connector-python`
> - **Testing**: `pytest`, `pytest-asyncio`, `httpx`, `playwright`

### 3. Initialize the Database

The system uses **SQLite** to store historical data, optimized for long-term use on SD cards. Run the initialization script to create the necessary tables and enable Write-Ahead Logging (WAL).

```bash
python3 init_db.py
```

> [!IMPORTANT]
> The database stores all historical data indefinitely in `data/inverter_logs.db`. Ensure your SD card has sufficient free space for long-term logging.

---

## 🚀 Phase 3: Running the Monitor

### ⏱️ Manual Start

To start both the collection engine and the web/API server:

```bash
python3 main.py
```

The dashboard will be accessible at `http://<your-pi-ip>:8000`.

### ⚡ Background Service (Systemd)

To ensure the monitor starts automatically on boot and restarts on failure, set it up as a systemd service.

1.  **Create the service file:**
    ```bash
    sudo nano /etc/systemd/system/pi-solar.service
    ```

2.  **Paste the following configuration** (adjust `User` and `WorkingDirectory` as needed):
    ```ini
    [Unit]
    Description=Pi Solar Monitor Service
    After=network.target

    [Service]
    User=pi
    WorkingDirectory=/home/pi/pi-solar-monitor
    ExecStart=/usr/bin/python3 main.py
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
    ```

3.  **Enable and start the service:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable pi-solar.service
    sudo systemctl start pi-solar.service
    ```

4.  **Check status:**
    ```bash
    sudo systemctl status pi-solar.service
    ```
