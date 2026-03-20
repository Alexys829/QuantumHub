<p align="center">
  <img src="quantumhub.png" alt="QuantumHub" width="128" height="128">
</p>

<h1 align="center">QuantumHub</h1>

<p align="center">
  <strong>All-in-one Linux system &amp; Docker management tool</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/PyQt6-6.6+-green?logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/platform-Linux-lightgrey?logo=linux&logoColor=white" alt="Linux">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="MIT License">
  <img src="https://img.shields.io/github/v/release/Alexys829/QuantumHub?label=release" alt="Release">
</p>

---

QuantumHub is a desktop application for Linux that lets you monitor and manage your system, Docker containers, virtual machines, and network configuration from a single interface. It works on **localhost** and on **remote servers via SSH**.

## Features

### System Monitoring
- **Dashboard** - Real-time CPU, memory, disk, network, and temperature metrics with circular gauges, per-core bars, and sparkline charts
- **Temperature Monitoring** - Hardware sensors via hwmon/thermal zones with color-coded thresholds + NVIDIA GPU support
- **System Tray** - Minimize to tray with live CPU, RAM, and temperature info in the right-click menu
- **Processes** - List, filter, and kill processes with per-process I/O stats
- **Disk Usage** - Partition analysis and visualization
- **System Logs** - systemd journal viewer with unit filtering

### Docker Management
- **Containers** - Start, stop, restart, kill, remove, view logs, exec shell, live resource stats
- **Images** - Pull, build, tag, push, remove, inspect
- **Volumes** - Create, inspect, remove
- **Networks** - Create, inspect, connect/disconnect containers
- **Compose** - Deploy and manage docker-compose projects
- **Registry** - Browse and manage Docker registries

### System Administration
- **Services** - Manage systemd services (start/stop/restart/enable/disable)
- **Packages** - Search, install, remove packages (APT, Snap, Flatpak)
- **Firewall** - UFW rule management
- **Network Config** - NetworkManager connections (DHCP/Static IP)
- **Hosts File** - Edit `/etc/hosts`
- **APT Repos** - Add/remove/toggle package repositories
- **Startup** - Manage systemd and XDG autostart entries
- **Cron Jobs** - View and edit scheduled tasks
- **Users & Groups** - User and group management

### Advanced
- **Terminal** - Multi-tab terminal emulator with command history
- **File Transfer** - SFTP-based file browser and transfer
- **Virtual Machines** - libvirt/KVM/QEMU management via virsh
- **Network Tools** - Ping, tracepath, DNS lookup, interface statistics
- **Remote Servers** - SSH connections with key-based or password authentication

## Screenshots

> Coming soon

## Installation

### AppImage (recommended)

Download the latest `.AppImage` from the [Releases](https://github.com/Alexys829/QuantumHub/releases) page:

```bash
chmod +x QuantumHub-*-x86_64.AppImage
./QuantumHub-*-x86_64.AppImage
```

### From source

```bash
git clone https://github.com/Alexys829/QuantumHub.git
cd QuantumHub
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

### Requirements

- Python 3.12+
- PyQt6 >= 6.6.0
- docker >= 7.0.0 (Python SDK)
- paramiko >= 3.4.0

### Build AppImage

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller quantumhub.spec
# Then package with appimagetool
```

## Architecture

QuantumHub follows the **MVC pattern**:

```
Service (data collection)  →  Controller (signals/threading)  →  View (PyQt6 UI)
```

- **Services** execute commands via `subprocess` (local) or `paramiko` SSH (remote)
- **Controllers** manage background threads (`QThreadPool`, `QThread`) and emit Qt signals
- **Views** are stacked in a `QStackedWidget` with sidebar navigation

## Tech Stack

| Component | Purpose |
|-----------|---------|
| **PyQt6** | Desktop UI framework |
| **Docker SDK** | Docker daemon API |
| **Paramiko** | SSH/SFTP connections |
| **SQLite3** | Local database (servers, settings, history) |

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
