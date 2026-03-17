# Installation Guide

This guide provides detailed instructions for setting up the Pi Solar Monitor on a Raspberry Pi (optimized for Pi Zero 2 W).

## Hardware Setup

### 1-Wire Interface (for Temperature Sensors)

The system uses DS18B20 sensors via the 1-Wire protocol. This must be enabled in the Pi's configuration.

1.  **Enable via raspi-config:**
    - Run `sudo raspi-config`.
    - Go to **Interface Options** -> **1-Wire**.
    - Select **Yes** to enable the interface.
    - Reboot the Pi: `sudo reboot`.

2.  **Manual Enable:**
    - Edit `/boot/config.txt`: `sudo nano /boot/config.txt`.
    - Add `dtoverlay=w1-gpio` to the end of the file.
    - Save and reboot.

### Inverter Connection

The system typically communicates with Voltronic-compatible inverters via USB.
- Ensure the inverter is connected to the Pi.
- The default `inverter.py` collector expects the device at `/dev/hidraw0`.
- You may need to grant permissions: `sudo chmod a+rw /dev/hidraw0`.

---

## Software Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd pi-solar-monitor
```

### 2. Install Python Dependencies

It is recommended to use a virtual environment or ensure all system dependencies are met.

```bash
pip install -r requirements.txt
```

### 3. Initialize the Database

The system uses SQLite to store historical data. Run the initialization script to create the necessary tables.

```bash
python3 init_db.py
```

---

## Running the Monitor

### Manual Start

To start both the collection engine and the web/API server:

```bash
python3 main.py
```

The dashboard will be accessible at `http://<your-pi-ip>:8000`.

### Background Service (Systemd)

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
