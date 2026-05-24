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

The easiest way to install the Pi Solar Monitor is using the interactive installation script.

### 1. Clone the Repository

```bash
git clone https://github.com/nkhearn/Pi-Solar-monitor.git
cd pi-solar-monitor
```

### 2. Run the Installer

The `install.sh` script automates dependency installation, database initialization, and systemd service setup. It also handles PEP 668 (externally managed environments) by offering to create a virtual environment.

```bash
chmod +x install.sh
./install.sh
```

**The installer will:**
- Verify Python 3.9+ is installed.
- Install all dependencies from `requirements.txt`.
- Initialize the SQLite database with optimized settings (WAL mode).
- Create a `pi-solar.service` and configure it to start on boot.

---

## 🚀 Phase 3: Post-Installation

### ⏱️ Manual Control

If you need to manually stop or restart the monitor:

```bash
# Stop the service
sudo systemctl stop pi-solar.service

# Start the service
sudo systemctl start pi-solar.service

# View live logs
sudo journalctl -u pi-solar.service -f
```

The dashboard will be accessible at `http://<your-pi-ip>:8000`.

---

## 📋 Technical Notes

- **Database**: The system uses **SQLite** located at `data/inverter_logs.db`. It stores all historical data indefinitely.
- **Environment**: If you used a virtual environment during installation, the systemd service is automatically configured to use the correct Python binary within that environment.
- **Permissions**: Ensure the user running the service has write access to the project directory and read/write access to `/dev/hidraw0`.
