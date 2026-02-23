from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


class SystemService:
    """Runs system commands locally (subprocess) or remotely (SSH).

    Uses the same local/remote pattern as ComposeService._run_compose().
    """

    def __init__(self, connection_manager: ConnectionManager):
        self._cm = connection_manager
        self._sudo_password: str | None = None

    @property
    def sudo_password(self) -> str | None:
        return self._sudo_password

    @sudo_password.setter
    def sudo_password(self, value: str | None) -> None:
        self._sudo_password = value

    def _run_command(
        self, cmd: str, timeout: int = 30, stdin_data: str | None = None
    ) -> tuple[str, str, int]:
        """Execute a shell command and return (stdout, stderr, returncode).

        If *stdin_data* is provided it is written to the process stdin
        (used by ``sudo -S`` to receive the password).
        """
        ssh = self._cm.ssh_client
        if ssh is not None:
            logger.debug("Remote cmd: %s", cmd)
            transport = ssh.get_transport()
            if transport is None or not transport.is_active():
                raise RuntimeError("SSH transport is not active")
            channel = transport.open_session()
            channel.settimeout(timeout)
            channel.exec_command(cmd)

            if stdin_data is not None:
                channel.sendall(stdin_data.encode("utf-8"))
                channel.shutdown_write()

            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []
            while True:
                if channel.recv_ready():
                    data = channel.recv(65536)
                    if data:
                        stdout_chunks.append(data.decode("utf-8", errors="replace"))
                if channel.recv_stderr_ready():
                    data = channel.recv_stderr(65536)
                    if data:
                        stderr_chunks.append(data.decode("utf-8", errors="replace"))
                if channel.exit_status_ready():
                    while channel.recv_ready():
                        data = channel.recv(65536)
                        if data:
                            stdout_chunks.append(data.decode("utf-8", errors="replace"))
                    while channel.recv_stderr_ready():
                        data = channel.recv_stderr(65536)
                        if data:
                            stderr_chunks.append(data.decode("utf-8", errors="replace"))
                    break

            rc = channel.recv_exit_status()
            channel.close()
            return "".join(stdout_chunks), "".join(stderr_chunks), rc
        else:
            logger.debug("Local cmd: %s", cmd)
            env = os.environ.copy()
            env.setdefault("TERM", "xterm-256color")
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=stdin_data,
                env=env,
            )
            return result.stdout, result.stderr, result.returncode

    def _run_sudo_command(self, cmd: str, timeout: int = 30) -> tuple[str, str, int]:
        """Run a command with ``sudo -S``, piping the stored password via stdin."""
        if self._sudo_password is None:
            raise PermissionError("sudo password not set")
        sudo_cmd = f"sudo -S {cmd}"
        stdin_data = self._sudo_password + "\n"
        out, err, rc = self._run_command(sudo_cmd, timeout=timeout, stdin_data=stdin_data)
        # sudo -S echoes the prompt on stderr — strip it
        err_lines = [
            ln for ln in err.splitlines()
            if not ln.strip().startswith("[sudo]") and ln.strip() != "Password:"
        ]
        return out, "\n".join(err_lines), rc

    # ── System Info ──────────────────────────────────────────

    def get_system_info(self) -> dict:
        """Return hostname, kernel, OS, arch, cpu_cores."""
        info: dict[str, str] = {}

        out, _, _ = self._run_command("hostname")
        info["hostname"] = out.strip()

        out, _, _ = self._run_command("uname -a")
        parts = out.strip().split()
        info["kernel"] = parts[2] if len(parts) > 2 else out.strip()
        info["arch"] = parts[-2] if len(parts) >= 2 else ""

        out, _, _ = self._run_command("cat /etc/os-release")
        for line in out.splitlines():
            if line.startswith("PRETTY_NAME="):
                info["os"] = line.split("=", 1)[1].strip().strip('"')
                break
        else:
            info["os"] = ""

        out, _, _ = self._run_command("nproc")
        info["cpu_cores"] = out.strip()

        return info

    def get_uptime(self) -> dict:
        """Return uptime_str, load_1, load_5, load_15."""
        result: dict[str, str] = {}

        out, _, _ = self._run_command("uptime -p")
        result["uptime_str"] = out.strip()

        out, _, _ = self._run_command("cat /proc/loadavg")
        parts = out.strip().split()
        result["load_1"] = parts[0] if len(parts) > 0 else "0"
        result["load_5"] = parts[1] if len(parts) > 1 else "0"
        result["load_15"] = parts[2] if len(parts) > 2 else "0"

        return result

    # ── Memory ───────────────────────────────────────────────

    def get_memory(self) -> dict:
        """Return total, used, available, swap_total, swap_used (bytes)."""
        out, _, _ = self._run_command("free -b")
        mem: dict[str, int] = {
            "total": 0, "used": 0, "available": 0,
            "swap_total": 0, "swap_used": 0,
        }
        for line in out.splitlines():
            parts = line.split()
            if parts and parts[0].startswith("Mem"):
                mem["total"] = int(parts[1])
                mem["used"] = int(parts[2])
                mem["available"] = int(parts[6]) if len(parts) > 6 else 0
            elif parts and parts[0].startswith("Swap"):
                mem["swap_total"] = int(parts[1])
                mem["swap_used"] = int(parts[2])
        return mem

    # ── Disk ─────────────────────────────────────────────────

    def get_disk_usage(self) -> list[dict]:
        """Return list of {device, size, used, avail, percent, mount}."""
        out, _, _ = self._run_command(
            "df -B1 --output=source,size,used,avail,pcent,target"
        )
        disks: list[dict] = []
        for line in out.splitlines()[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 6 and not parts[0].startswith("tmpfs"):
                disks.append({
                    "device": parts[0],
                    "size": int(parts[1]),
                    "used": int(parts[2]),
                    "avail": int(parts[3]),
                    "percent": parts[4],
                    "mount": parts[5],
                })
        return disks

    # ── CPU ──────────────────────────────────────────────────

    def read_cpu_stat(self) -> dict[str, list[int]]:
        """Read /proc/stat once and return ``{cpuN: [jiffies...]}``."""
        out, _, _ = self._run_command("cat /proc/stat")
        cpus: dict[str, list[int]] = {}
        for line in out.splitlines():
            if line.startswith("cpu"):
                parts = line.split()
                name = parts[0]
                if name == "cpu":
                    continue  # skip aggregate
                cpus[name] = [int(x) for x in parts[1:]]
        return cpus

    @staticmethod
    def calc_cpu_percent(
        stat1: dict[str, list[int]], stat2: dict[str, list[int]]
    ) -> list[float]:
        """Calculate per-core CPU% from two /proc/stat snapshots."""
        percents: list[float] = []
        for name in sorted(stat1.keys()):
            if name not in stat2:
                continue
            v1 = stat1[name]
            v2 = stat2[name]
            idle1 = v1[3] + (v1[4] if len(v1) > 4 else 0)
            idle2 = v2[3] + (v2[4] if len(v2) > 4 else 0)
            total1 = sum(v1)
            total2 = sum(v2)
            delta_total = total2 - total1
            delta_idle = idle2 - idle1
            if delta_total == 0:
                percents.append(0.0)
            else:
                percents.append(round((1 - delta_idle / delta_total) * 100, 1))
        return percents

    def get_cpu_percent(self) -> list[float]:
        """Convenience: read → sleep(1s) → read → calc. Blocks ~1s."""
        stat1 = self.read_cpu_stat()
        time.sleep(1)
        stat2 = self.read_cpu_stat()
        return self.calc_cpu_percent(stat1, stat2)

    # ── Network ──────────────────────────────────────────────

    def get_network_stats(self) -> list[dict]:
        """Return list of {interface, rx_bytes, tx_bytes, rx_packets, tx_packets}."""
        out, _, _ = self._run_command("cat /proc/net/dev")
        stats: list[dict] = []
        for line in out.splitlines()[2:]:  # skip header lines
            if ":" not in line:
                continue
            iface, data = line.split(":", 1)
            iface = iface.strip()
            if iface == "lo":
                continue
            parts = data.split()
            if len(parts) >= 10:
                stats.append({
                    "interface": iface,
                    "rx_bytes": int(parts[0]),
                    "tx_bytes": int(parts[8]),
                    "rx_packets": int(parts[1]),
                    "tx_packets": int(parts[9]),
                })
        return stats

    def get_interface_ips(self) -> dict[str, list[str]]:
        """Return {interface: [ip1, ip2, ...]} for all network interfaces."""
        out, _, rc = self._run_command("ip -o addr show")
        ips: dict[str, list[str]] = {}
        if rc != 0:
            return ips
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            # format: index: iface inet/inet6 addr/prefix ...
            iface = parts[1]
            family = parts[2]
            if family not in ("inet", "inet6"):
                continue
            addr = parts[3].split("/")[0]  # strip prefix length
            if iface == "lo":
                continue
            if iface not in ips:
                ips[iface] = []
            ips[iface].append(addr)
        return ips

    # ── Processes ─────────────────────────────────────────────

    def get_processes(self) -> list[dict]:
        """Return list of {pid, user, cpu, mem, vsz, rss, stat, start, time, command}."""
        out, _, _ = self._run_command("ps aux --sort=-pcpu")
        procs: list[dict] = []
        for line in out.splitlines()[1:]:  # skip header
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            procs.append({
                "user": parts[0],
                "pid": parts[1],
                "cpu": parts[2],
                "mem": parts[3],
                "vsz": parts[4],
                "rss": parts[5],
                "stat": parts[7],
                "start": parts[8],
                "time": parts[9],
                "command": parts[10],
            })
        return procs

    def kill_process(self, pid: int, signal: int = 15) -> tuple[str, int]:
        """Kill a process. Returns (output, returncode)."""
        cmd = f"kill -{signal} {int(pid)}"
        out, err, rc = self._run_command(cmd)
        return (out + err).strip(), rc

    # ── Per-Process I/O ─────────────────────────────────────────

    def get_processes_io(self) -> dict[str, dict[str, int]]:
        """Return {pid: {read_bytes, write_bytes}} from /proc/<pid>/io."""
        cmd = (
            "awk '/^read_bytes/{r=$2} /^write_bytes/{w=$2; "
            'split(FILENAME,a,"/"); print a[3],r,w}\' '
            "/proc/[0-9]*/io 2>/dev/null"
        )
        out, _, _ = self._run_command(cmd, timeout=10)
        result: dict[str, dict[str, int]] = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) == 3:
                try:
                    result[parts[0]] = {
                        "read_bytes": int(parts[1]),
                        "write_bytes": int(parts[2]),
                    }
                except ValueError:
                    continue
        return result

    def get_network_io_by_pid(self) -> dict[str, dict[str, int]]:
        """Return {pid: {bytes_sent, bytes_received}} from ss -tnpi."""
        out, _, _ = self._run_command("ss -tnpi", timeout=10)
        result: dict[str, dict[str, int]] = {}
        current_line = ""
        for line in out.splitlines():
            if line.startswith("\t") or line.startswith(" "):
                # Continuation line: contains pid and bytes info
                current_line += " " + line.strip()
                pid_match = re.search(r"pid=(\d+)", current_line)
                sent_match = re.search(r"bytes_sent:(\d+)", current_line)
                recv_match = re.search(r"bytes_received:(\d+)", current_line)
                if pid_match:
                    pid = pid_match.group(1)
                    sent = int(sent_match.group(1)) if sent_match else 0
                    recv = int(recv_match.group(1)) if recv_match else 0
                    if pid in result:
                        result[pid]["bytes_sent"] += sent
                        result[pid]["bytes_received"] += recv
                    else:
                        result[pid] = {"bytes_sent": sent, "bytes_received": recv}
                current_line = ""
            else:
                current_line = line.strip()
        return result

    # ── Services (systemd) ────────────────────────────────────

    def get_services(self) -> list[dict]:
        """Return list of {unit, load, active, sub, description, enabled}."""
        # Get all services including inactive ones
        out, _, _ = self._run_command(
            "systemctl list-units --type=service --all --no-pager --plain"
        )

        # Get boot/enabled status from unit-files
        uf_out, _, _ = self._run_command(
            "systemctl list-unit-files --type=service --no-pager --plain"
        )
        enabled_map: dict[str, str] = {}
        for line in uf_out.splitlines():
            uf_parts = line.split(None, 2)
            if len(uf_parts) >= 2 and uf_parts[0].endswith(".service"):
                enabled_map[uf_parts[0]] = uf_parts[1]

        services: list[dict] = []
        for line in out.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            unit = parts[0]
            if not unit.endswith(".service"):
                continue
            services.append({
                "unit": unit,
                "load": parts[1],
                "active": parts[2],
                "sub": parts[3],
                "description": parts[4] if len(parts) > 4 else "",
                "enabled": enabled_map.get(unit, ""),
            })
        return services

    def service_action(self, unit: str, action: str) -> tuple[str, int]:
        """Run systemctl action on a service unit. Returns (output, returncode)."""
        safe_unit = shlex.quote(unit)
        safe_action = shlex.quote(action)
        cmd = f"systemctl {safe_action} {safe_unit}"
        out, err, rc = self._run_sudo_command(cmd, timeout=30)
        return (out + err).strip(), rc

    # ── Listening Ports ───────────────────────────────────────

    def get_listening_ports(self) -> list[dict]:
        """Return list of {protocol, state, local_address, local_port}."""
        out, _, _ = self._run_command("ss -tuln")
        ports: list[dict] = []
        for line in out.splitlines()[1:]:  # skip header
            parts = line.split()
            if len(parts) < 5:
                continue
            proto = parts[0]
            state = parts[1]
            local = parts[4]
            # Split address:port (handle IPv6 [::]:port)
            if "]::" in local:
                # edge case
                addr, port = local.rsplit(":", 1)
            elif local.startswith("["):
                addr, port = local.rsplit(":", 1)
            else:
                addr, port = local.rsplit(":", 1)
            ports.append({
                "protocol": proto,
                "state": state,
                "local_address": addr,
                "local_port": port,
            })
        return ports

    # ── Installed Packages ─────────────────────────────────────

    @staticmethod
    def _format_size(kb: int) -> tuple[str, int]:
        """Convert KB to human-readable string and raw bytes for sorting."""
        size_bytes = kb * 1024
        if kb >= 1048576:
            return f"{kb / 1048576:.1f} GB", size_bytes
        if kb >= 1024:
            return f"{kb / 1024:.1f} MB", size_bytes
        return f"{kb} KB", size_bytes

    def get_installed_packages(self) -> list[dict]:
        """Return list of installed packages from deb, snap, and flatpak."""
        packages: list[dict] = []
        self._fetch_deb_packages(packages)
        self._fetch_snap_packages(packages)
        self._fetch_flatpak_packages(packages)
        return packages

    def _fetch_deb_packages(self, packages: list[dict]) -> None:
        cmd = (
            "dpkg-query -W -f="
            "'${Package}\\t${Version}\\t${Installed-Size}\\t"
            "${db:Status-Abbrev}\\t${binary:Summary}\\n' 2>/dev/null"
        )
        out, _, rc = self._run_command(cmd, timeout=30)
        if rc != 0:
            return
        for line in out.splitlines():
            parts = line.split("\t", 4)
            if len(parts) < 5:
                continue
            name, version, size_str, status, description = parts
            if not status.startswith("ii"):
                continue
            try:
                kb = int(size_str)
            except ValueError:
                kb = 0
            size_human, size_bytes = self._format_size(kb)
            packages.append({
                "name": name.strip(),
                "version": version.strip(),
                "size": size_human,
                "size_bytes": size_bytes,
                "type": "deb",
                "description": description.strip(),
                "source": "",
            })

    def _fetch_snap_packages(self, packages: list[dict]) -> None:
        out, _, rc = self._run_command("snap list --color=never 2>/dev/null", timeout=15)
        if rc != 0:
            return
        lines = out.splitlines()
        if len(lines) < 2:
            return
        for line in lines[1:]:  # skip header
            parts = line.split()
            if len(parts) < 5:
                continue
            name = parts[0]
            version = parts[1]
            publisher = parts[4] if len(parts) >= 5 else ""
            packages.append({
                "name": name,
                "version": version,
                "size": "",
                "size_bytes": 0,
                "type": "snap",
                "description": "",
                "source": publisher,
            })

    def _fetch_flatpak_packages(self, packages: list[dict]) -> None:
        out, _, rc = self._run_command(
            "flatpak list --app --columns=application,name,version,size,origin 2>/dev/null",
            timeout=15,
        )
        if rc != 0:
            return
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            app_id, display_name, version, size_str, origin = parts
            # Parse size (flatpak gives it like "150.3 MB")
            size_bytes = 0
            size_human = size_str.strip()
            try:
                size_parts = size_human.split()
                if len(size_parts) == 2:
                    val = float(size_parts[0])
                    unit = size_parts[1].upper()
                    multipliers = {"B": 1, "KB": 1024, "MB": 1048576, "GB": 1073741824}
                    size_bytes = int(val * multipliers.get(unit, 1))
            except (ValueError, IndexError):
                pass
            packages.append({
                "name": display_name.strip() or app_id.strip(),
                "version": version.strip(),
                "size": size_human,
                "size_bytes": size_bytes,
                "type": "flatpak",
                "description": "",
                "source": origin.strip(),
            })

    def package_action(
        self, name: str, pkg_type: str, action: str
    ) -> tuple[str, int]:
        """Execute a package management action. Returns (output, returncode)."""
        safe_name = shlex.quote(name)

        commands = {
            ("deb", "uninstall"): f"apt remove -y {safe_name}",
            ("deb", "purge"): f"apt purge -y {safe_name}",
            ("deb", "reinstall"): f"apt install --reinstall -y {safe_name}",
            ("deb", "reset"): f"apt purge -y {safe_name} && apt install -y {safe_name}",
            ("deb", "update"): f"apt install --only-upgrade -y {safe_name}",
            ("snap", "uninstall"): f"snap remove {safe_name}",
            ("snap", "purge"): f"snap remove {safe_name}",
            ("snap", "reinstall"): f"snap refresh {safe_name}",
            ("snap", "reset"): f"snap remove {safe_name} && snap install {safe_name}",
            ("snap", "update"): f"snap refresh {safe_name}",
            ("flatpak", "uninstall"): f"flatpak uninstall -y {safe_name}",
            ("flatpak", "purge"): f"flatpak uninstall -y {safe_name}",
            ("flatpak", "reinstall"): f"flatpak update -y {safe_name}",
            ("flatpak", "reset"): (
                f"flatpak uninstall -y {safe_name} && flatpak install -y {safe_name}"
            ),
            ("flatpak", "update"): f"flatpak update -y {safe_name}",
        }

        cmd = commands.get((pkg_type, action))
        if cmd is None:
            return f"Unknown action '{action}' for type '{pkg_type}'", 1

        out, err, rc = self._run_sudo_command(cmd, timeout=120)
        return (out + err).strip(), rc

    # ── Hosts File ────────────────────────────────────────────

    def get_hosts_file(self) -> str:
        """Read /etc/hosts content."""
        out, _, _ = self._run_command("cat /etc/hosts", timeout=10)
        return out

    def save_hosts_file(self, content: str) -> tuple[str, int]:
        """Write /etc/hosts via temp file + sudo cp."""
        import base64
        encoded = base64.b64encode(content.encode()).decode()
        cmd_write = f"echo {shlex.quote(encoded)} | base64 -d > /tmp/.qh_hosts_tmp"
        out, err, rc = self._run_command(cmd_write, timeout=10)
        if rc != 0:
            return (out + err).strip(), rc
        out, err, rc = self._run_sudo_command(
            "cp /tmp/.qh_hosts_tmp /etc/hosts && rm -f /tmp/.qh_hosts_tmp"
        )
        return (out + err).strip(), rc

    # ── Network Configuration (nmcli) ─────────────────────────

    def check_networkmanager(self) -> bool:
        """Check if NetworkManager is running."""
        _, _, rc = self._run_command("nmcli general status 2>/dev/null", timeout=5)
        return rc == 0

    def get_network_connections(self) -> list[dict]:
        """List network connections via nmcli."""
        out, _, rc = self._run_command(
            "nmcli -t -f NAME,UUID,TYPE,DEVICE,STATE connection show 2>/dev/null",
            timeout=10,
        )
        connections: list[dict] = []
        if rc != 0:
            return connections
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) < 5:
                continue
            connections.append({
                "name": parts[0],
                "uuid": parts[1],
                "type": parts[2],
                "device": parts[3],
                "state": parts[4],
            })
        return connections

    def get_connection_details(self, conn_name: str) -> dict:
        """Get IPv4 config for a connection."""
        safe = shlex.quote(conn_name)
        out, _, rc = self._run_command(
            f"nmcli -t connection show {safe} 2>/dev/null", timeout=10
        )
        details: dict[str, str] = {
            "method": "auto",
            "address": "",
            "prefix": "",
            "gateway": "",
            "dns": "",
            "autoconnect": "yes",
        }
        if rc != 0:
            return details
        for line in out.splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if key == "connection.autoconnect":
                details["autoconnect"] = val
            elif key == "ipv4.method":
                details["method"] = val
            elif key == "ipv4.addresses":
                if val and val != "--":
                    if "/" in val:
                        addr, prefix = val.split("/", 1)
                        details["address"] = addr
                        details["prefix"] = prefix
                    else:
                        details["address"] = val
            elif key == "ipv4.gateway":
                if val and val != "--":
                    details["gateway"] = val
            elif key == "ipv4.dns":
                if val and val != "--":
                    details["dns"] = val
            # Also pick up active values
            elif key == "IP4.ADDRESS[1]" and not details["address"]:
                if "/" in val:
                    addr, prefix = val.split("/", 1)
                    details["address"] = addr
                    details["prefix"] = prefix
            elif key == "IP4.GATEWAY" and not details["gateway"]:
                if val and val != "--":
                    details["gateway"] = val
            elif key == "IP4.DNS[1]" and not details["dns"]:
                details["dns"] = val
        return details

    def set_connection_static(
        self, conn_name: str, address: str, prefix: str,
        gateway: str, dns: str
    ) -> tuple[str, int]:
        """Set connection to static IP and apply."""
        safe = shlex.quote(conn_name)
        addr = shlex.quote(f"{address}/{prefix}")
        gw = shlex.quote(gateway)
        dns_safe = shlex.quote(dns.replace(",", " "))
        cmd = (
            f"nmcli connection modify {safe} "
            f"ipv4.method manual ipv4.addresses {addr} "
            f"ipv4.gateway {gw} ipv4.dns {dns_safe}"
        )
        out, err, rc = self._run_sudo_command(cmd, timeout=15)
        if rc != 0:
            return (out + err).strip(), rc
        # Apply
        out2, err2, rc2 = self._run_sudo_command(
            f"nmcli connection up {safe}", timeout=30
        )
        return (out + err + out2 + err2).strip(), rc2

    def set_connection_dhcp(self, conn_name: str) -> tuple[str, int]:
        """Set connection to DHCP and apply."""
        safe = shlex.quote(conn_name)
        cmd = (
            f"nmcli connection modify {safe} "
            f'ipv4.method auto ipv4.addresses "" ipv4.gateway "" ipv4.dns ""'
        )
        out, err, rc = self._run_sudo_command(cmd, timeout=15)
        if rc != 0:
            return (out + err).strip(), rc
        out2, err2, rc2 = self._run_sudo_command(
            f"nmcli connection up {safe}", timeout=30
        )
        return (out + err + out2 + err2).strip(), rc2

    def rename_connection(self, old_name: str, new_name: str) -> tuple[str, int]:
        """Rename a NetworkManager connection."""
        safe_old = shlex.quote(old_name)
        safe_new = shlex.quote(new_name)
        out, err, rc = self._run_sudo_command(
            f"nmcli connection modify {safe_old} connection.id {safe_new}"
        )
        return (out + err).strip(), rc

    def clone_connection(self, source_name: str, new_name: str) -> tuple[str, int]:
        """Clone a NetworkManager connection."""
        safe_src = shlex.quote(source_name)
        safe_new = shlex.quote(new_name)
        out, err, rc = self._run_sudo_command(
            f"nmcli connection clone {safe_src} {safe_new}"
        )
        return (out + err).strip(), rc

    def set_connection_active(
        self, conn_name: str, activate: bool
    ) -> tuple[str, int]:
        """Activate or deactivate a connection."""
        safe = shlex.quote(conn_name)
        action = "up" if activate else "down"
        out, err, rc = self._run_sudo_command(
            f"nmcli connection {action} {safe}", timeout=30
        )
        return (out + err).strip(), rc

    def delete_connection(self, conn_name: str) -> tuple[str, int]:
        """Delete a NetworkManager connection profile."""
        safe = shlex.quote(conn_name)
        out, err, rc = self._run_sudo_command(
            f"nmcli connection delete {safe}"
        )
        return (out + err).strip(), rc

    def set_connection_autoconnect(
        self, conn_name: str, enabled: bool
    ) -> tuple[str, int]:
        """Set autoconnect on/off for a connection."""
        safe = shlex.quote(conn_name)
        val = "yes" if enabled else "no"
        out, err, rc = self._run_sudo_command(
            f"nmcli connection modify {safe} connection.autoconnect {val}"
        )
        return (out + err).strip(), rc

    def get_interface_macs(self) -> dict[str, str]:
        """Return {interface: mac_address} for all interfaces."""
        out, _, rc = self._run_command("ip -o link show 2>/dev/null", timeout=10)
        macs: dict[str, str] = {}
        if rc != 0:
            return macs
        for line in out.splitlines():
            m = re.search(r"^\d+: (\S+):.*link/ether\s+([0-9a-f:]+)", line)
            if m:
                iface = m.group(1).split("@")[0]
                macs[iface] = m.group(2)
        return macs

    # ── Firewall (ufw) ──────────────────────────────────────

    def get_firewall_status(self) -> dict:
        """Return {enabled: bool, rules: [{num, to, action, from_addr}]}."""
        out, err, rc = self._run_sudo_command(
            "ufw status numbered 2>/dev/null", timeout=10
        )
        result: dict = {"available": True, "enabled": False, "rules": []}
        if rc != 0:
            # Check if ufw is installed at all
            _, _, rc2 = self._run_command("which ufw 2>/dev/null", timeout=5)
            if rc2 != 0:
                result["available"] = False
            return result
        combined = out + err
        for line in combined.splitlines():
            stripped = line.strip()
            if stripped.startswith("Status:"):
                result["enabled"] = "active" in stripped.lower()
            m = re.match(
                r"\[\s*(\d+)\]\s+(.+?)\s{2,}(\w+\s*\w*)\s{2,}(.+)", stripped
            )
            if m:
                result["rules"].append({
                    "num": int(m.group(1)),
                    "to": m.group(2).strip(),
                    "action": m.group(3).strip(),
                    "from_addr": m.group(4).strip(),
                })
        return result

    def set_firewall_enabled(self, enabled: bool) -> tuple[str, int]:
        """Enable or disable the firewall."""
        cmd = "ufw --force enable" if enabled else "ufw disable"
        out, err, rc = self._run_sudo_command(cmd, timeout=15)
        return (out + err).strip(), rc

    def add_firewall_rule(
        self, port: str, protocol: str, action: str, source: str
    ) -> tuple[str, int]:
        """Add a ufw rule. action: 'allow' or 'deny'."""
        safe_action = "allow" if action.lower() == "allow" else "deny"
        # Build port/proto part
        if protocol.lower() == "both":
            port_spec = shlex.quote(port)
        else:
            port_spec = shlex.quote(f"{port}/{protocol.lower()}")
        if source and source.lower() not in ("anywhere", "any", ""):
            safe_src = shlex.quote(source)
            cmd = f"ufw {safe_action} from {safe_src} to any port {port_spec}"
        else:
            cmd = f"ufw {safe_action} {port_spec}"
        out, err, rc = self._run_sudo_command(cmd, timeout=10)
        return (out + err).strip(), rc

    def delete_firewall_rule(self, rule_num: int) -> tuple[str, int]:
        """Delete a ufw rule by number."""
        cmd = f"echo y | ufw delete {int(rule_num)}"
        out, err, rc = self._run_sudo_command(cmd, timeout=10)
        return (out + err).strip(), rc

    # ── Network Tools ─────────────────────────────────────────

    def run_ping(self, host: str, count: int = 4) -> dict:
        """Ping a host and return parsed results."""
        safe = shlex.quote(host)
        out, err, rc = self._run_command(
            f"ping -c {int(count)} -W 2 {safe} 2>&1",
            timeout=count * 3 + 10,
        )
        result: dict = {
            "host": host,
            "output": out + err,
            "reachable": rc == 0,
            "transmitted": 0,
            "received": 0,
            "loss_pct": 100.0,
            "rtt_min": 0.0,
            "rtt_avg": 0.0,
            "rtt_max": 0.0,
        }
        m = re.search(
            r"(\d+) packets transmitted, (\d+) received.*?(\d+)% packet loss",
            out,
        )
        if m:
            result["transmitted"] = int(m.group(1))
            result["received"] = int(m.group(2))
            result["loss_pct"] = float(m.group(3))
        m2 = re.search(r"rtt .* = ([\d.]+)/([\d.]+)/([\d.]+)", out)
        if m2:
            result["rtt_min"] = float(m2.group(1))
            result["rtt_avg"] = float(m2.group(2))
            result["rtt_max"] = float(m2.group(3))
        return result

    def run_tracepath(self, host: str) -> str:
        """Run tracepath and return the output."""
        safe = shlex.quote(host)
        out, err, _ = self._run_command(
            f"tracepath -n {safe} 2>&1", timeout=60
        )
        return (out + err).strip()

    def run_dns_lookup(self, host: str) -> str:
        """DNS lookup via dig or nslookup."""
        safe = shlex.quote(host)
        out, err, rc = self._run_command(
            f"dig +short {safe} 2>/dev/null", timeout=10
        )
        if rc != 0 or not out.strip():
            # Fallback to nslookup
            out, err, _ = self._run_command(
                f"nslookup {safe} 2>&1", timeout=10
            )
        return (out + err).strip()

    # ── APT Repositories ──────────────────────────────────────

    def get_apt_repos(self) -> list[dict]:
        """Parse /etc/apt/sources.list and sources.list.d/*.list files."""
        # Get list of files to parse
        out, _, _ = self._run_command(
            "cat /etc/apt/sources.list 2>/dev/null; "
            "for f in /etc/apt/sources.list.d/*.list; do "
            '[ -f "$f" ] && echo "---FILE:$f---" && cat "$f"; '
            "done",
            timeout=10,
        )
        repos: list[dict] = []
        current_file = "/etc/apt/sources.list"
        line_num = 0
        for line in out.splitlines():
            if line.startswith("---FILE:") and line.endswith("---"):
                current_file = line[8:-3]
                line_num = 0
                continue
            line_num += 1
            stripped = line.strip()
            if not stripped:
                continue

            enabled = True
            parse_line = stripped
            # Check if commented out repo line
            if stripped.startswith("#"):
                rest = stripped.lstrip("# ").strip()
                if rest.startswith("deb"):
                    enabled = False
                    parse_line = rest
                else:
                    continue
            if not parse_line.startswith("deb"):
                continue

            parts = parse_line.split()
            if len(parts) < 3:
                continue
            repo_type = parts[0]  # deb or deb-src
            # Handle [options] like [arch=amd64]
            idx = 1
            options = ""
            if idx < len(parts) and parts[idx].startswith("["):
                opt_parts = []
                while idx < len(parts):
                    opt_parts.append(parts[idx])
                    if parts[idx].endswith("]"):
                        idx += 1
                        break
                    idx += 1
                options = " ".join(opt_parts)
            uri = parts[idx] if idx < len(parts) else ""
            suite = parts[idx + 1] if idx + 1 < len(parts) else ""
            components = " ".join(parts[idx + 2:]) if idx + 2 < len(parts) else ""

            repos.append({
                "enabled": enabled,
                "type": repo_type,
                "uri": uri,
                "suite": suite,
                "components": components,
                "options": options,
                "file": current_file,
                "line_num": line_num,
                "raw_line": stripped,
            })
        return repos

    def toggle_apt_repo(
        self, file: str, line_num: int, enable: bool
    ) -> tuple[str, int]:
        """Comment or uncomment a repo line."""
        safe_file = shlex.quote(file)
        if enable:
            # Remove leading # (and optional space)
            cmd = f"sed -i '{line_num}s/^#\\s*//' {safe_file}"
        else:
            # Add # at beginning
            cmd = f"sed -i '{line_num}s/^/# /' {safe_file}"
        out, err, rc = self._run_sudo_command(cmd)
        return (out + err).strip(), rc

    def add_apt_repo(self, repo_line: str) -> tuple[str, int]:
        """Add a repository line. Uses add-apt-repository for PPAs, else appends to custom file."""
        safe = shlex.quote(repo_line)
        if repo_line.startswith("ppa:"):
            cmd = f"add-apt-repository -y {safe}"
        else:
            cmd = f"echo {safe} >> /etc/apt/sources.list.d/quantumhub-custom.list"
        out, err, rc = self._run_sudo_command(cmd, timeout=60)
        return (out + err).strip(), rc

    def delete_apt_repo(self, file: str, line_num: int) -> tuple[str, int]:
        """Delete a repo line from a file."""
        safe_file = shlex.quote(file)
        cmd = f"sed -i '{line_num}d' {safe_file}"
        out, err, rc = self._run_sudo_command(cmd)
        return (out + err).strip(), rc

    def run_apt_update(self) -> tuple[str, int]:
        """Run apt update."""
        out, err, rc = self._run_sudo_command("apt update", timeout=120)
        return (out + err).strip(), rc

    # ── Startup Applications ──────────────────────────────────

    def get_startup_entries(self) -> list[dict]:
        """Get startup entries from systemd services and XDG autostart."""
        entries: list[dict] = []
        self._fetch_systemd_startup(entries)
        self._fetch_xdg_autostart(entries)
        return entries

    def _fetch_systemd_startup(self, entries: list[dict]) -> None:
        out, _, rc = self._run_command(
            "systemctl list-unit-files --type=service --no-pager --plain 2>/dev/null",
            timeout=15,
        )
        if rc != 0:
            return
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            unit = parts[0]
            state = parts[1]
            if not unit.endswith(".service"):
                continue
            # Only show enabled/disabled (skip static, masked, generated)
            if state not in ("enabled", "disabled"):
                continue
            # Get description
            desc_out, _, _ = self._run_command(
                f"systemctl show -p Description --value {shlex.quote(unit)} 2>/dev/null",
                timeout=5,
            )
            entries.append({
                "name": unit,
                "entry_type": "systemd",
                "enabled": state == "enabled",
                "description": desc_out.strip(),
                "command": "",
                "file": "",
            })

    def _fetch_xdg_autostart(self, entries: list[dict]) -> None:
        # Read from both system and user autostart dirs
        cmd = (
            "for f in /etc/xdg/autostart/*.desktop ~/.config/autostart/*.desktop; do "
            '[ -f "$f" ] && echo "---FILE:$f---" && cat "$f"; '
            "done 2>/dev/null"
        )
        out, _, _ = self._run_command(cmd, timeout=10)
        current_file = ""
        name = ""
        command = ""
        description = ""
        hidden = False
        for line in out.splitlines():
            if line.startswith("---FILE:") and line.endswith("---"):
                # Save previous entry if any
                if current_file and name:
                    entries.append({
                        "name": name,
                        "entry_type": "autostart",
                        "enabled": not hidden,
                        "description": description,
                        "command": command,
                        "file": current_file,
                    })
                current_file = line[8:-3]
                name = ""
                command = ""
                description = ""
                hidden = False
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key == "Name":
                name = val
            elif key == "Exec":
                command = val
            elif key == "Comment":
                description = val
            elif key == "Hidden":
                hidden = val.lower() == "true"
            elif key == "X-GNOME-Autostart-enabled":
                if val.lower() == "false":
                    hidden = True
        # Last entry
        if current_file and name:
            entries.append({
                "name": name,
                "entry_type": "autostart",
                "enabled": not hidden,
                "description": description,
                "command": command,
                "file": current_file,
            })

    def toggle_systemd_startup(self, unit: str, enable: bool) -> tuple[str, int]:
        """Enable or disable a systemd service at boot."""
        action = "enable" if enable else "disable"
        safe = shlex.quote(unit)
        out, err, rc = self._run_sudo_command(f"systemctl {action} {safe}")
        return (out + err).strip(), rc

    def toggle_autostart_entry(self, file: str, enable: bool) -> tuple[str, int]:
        """Toggle XDG autostart entry by setting Hidden=true/false."""
        safe_file = shlex.quote(file)
        if enable:
            # Remove Hidden=true or set to false
            cmd = (
                f"sed -i '/^Hidden=/d' {safe_file} && "
                f"sed -i '/^X-GNOME-Autostart-enabled=/d' {safe_file}"
            )
        else:
            # Remove existing Hidden line and add Hidden=true
            cmd = (
                f"sed -i '/^Hidden=/d' {safe_file} && "
                f"echo 'Hidden=true' >> {safe_file}"
            )
        out, err, rc = self._run_sudo_command(cmd)
        return (out + err).strip(), rc

    def add_autostart_entry(
        self, name: str, command: str, description: str
    ) -> tuple[str, int]:
        """Create a .desktop file in ~/.config/autostart/."""
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name.lower())
        desktop_content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={name}\n"
            f"Exec={command}\n"
            f"Comment={description}\n"
            "Hidden=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        import base64
        encoded = base64.b64encode(desktop_content.encode()).decode()
        cmd = (
            "mkdir -p ~/.config/autostart && "
            f"echo {shlex.quote(encoded)} | base64 -d > "
            f"~/.config/autostart/{safe_name}.desktop"
        )
        out, err, rc = self._run_command(cmd, timeout=10)
        return (out + err).strip(), rc

    def remove_autostart_entry(self, file: str) -> tuple[str, int]:
        """Remove an XDG autostart .desktop file."""
        safe = shlex.quote(file)
        # Only allow removing from user autostart dir
        if "/.config/autostart/" not in file:
            out, err, rc = self._run_sudo_command(f"rm -f {safe}")
        else:
            out, err, rc = self._run_command(f"rm -f {safe}", timeout=10)
        return (out + err).strip(), rc

    # ── Terminal ──────────────────────────────────────────────

    def run_terminal_command(
        self, cmd: str, cwd: str = "~"
    ) -> tuple[str, int]:
        """Run a command in a specific directory. Returns (output, returncode).

        If the command starts with ``sudo`` and a password is stored,
        it is automatically rewritten to ``sudo -S`` with the password
        piped via stdin.
        """
        safe_cwd = "$HOME" if cwd == "~" else shlex.quote(cwd)
        actual_cmd = cmd
        stdin_data: str | None = None

        if cmd.startswith("sudo "):
            rest = cmd[5:]  # strip "sudo "
            if self._sudo_password is not None:
                # Try with stored password (SSH or user-provided)
                actual_cmd = f"sudo -S {rest}"
                stdin_data = self._sudo_password + "\n"
            else:
                # Non-interactive: succeeds only if NOPASSWD is configured
                actual_cmd = f"sudo -n {rest}"

        full_cmd = f"cd {safe_cwd} && {actual_cmd}"
        out, err, rc = self._run_command(full_cmd, timeout=30, stdin_data=stdin_data)

        # Strip sudo prompt noise from stderr
        if stdin_data is not None:
            err_lines = [
                ln for ln in err.splitlines()
                if not ln.strip().startswith("[sudo]") and ln.strip() != "Password:"
            ]
            err = "\n".join(err_lines)

        output = out
        if err.strip():
            output += err
        return output, rc

    # ── Journalctl / System Logs ─────────────────────────────

    def get_journal_units(self) -> list[str]:
        """Return list of systemd unit names (services)."""
        out, _, rc = self._run_command(
            "systemctl list-units --type=service --no-pager --plain --no-legend"
        )
        units: list[str] = []
        if rc == 0:
            for line in out.splitlines():
                parts = line.split()
                if parts:
                    units.append(parts[0])
        return sorted(units)

    def get_journal_logs(
        self,
        unit: str | None = None,
        priority: str | None = None,
        since: str | None = None,
        lines: int = 200,
    ) -> list[str]:
        """Fetch journal logs with optional filters."""
        cmd = f"journalctl --no-pager -n {lines}"
        if unit:
            cmd += f" -u {unit}"
        if priority:
            cmd += f" -p {priority}"
        if since:
            cmd += f" --since '{since}'"
        out, _, _ = self._run_command(cmd, timeout=30)
        return out.splitlines()

    # ── Cron Jobs ─────────────────────────────────────────────

    def get_cron_jobs(self, user: str | None = None) -> list[dict]:
        """Parse crontab and return list of job dicts."""
        cmd = "crontab -l"
        if user:
            cmd = f"sudo crontab -u {user} -l"
            out, err, rc = self._run_sudo_command(cmd)
        else:
            out, err, rc = self._run_command(cmd)
        if rc != 0:
            if "no crontab for" in (out + err).lower():
                return []
            raise RuntimeError(f"crontab error: {err or out}")
        jobs: list[dict] = []
        for i, line in enumerate(out.splitlines()):
            stripped = line.strip()
            if not stripped or stripped.startswith("#!"):
                continue
            enabled = not stripped.startswith("#")
            raw = stripped.lstrip("# ")
            parts = raw.split(None, 5)
            if len(parts) >= 6:
                jobs.append({
                    "index": i,
                    "enabled": enabled,
                    "minute": parts[0],
                    "hour": parts[1],
                    "dom": parts[2],
                    "month": parts[3],
                    "dow": parts[4],
                    "command": parts[5],
                    "raw": line,
                })
            elif len(parts) >= 1 and stripped.startswith("@"):
                # Special schedules like @reboot, @daily etc.
                jobs.append({
                    "index": i,
                    "enabled": enabled,
                    "minute": parts[0],
                    "hour": "",
                    "dom": "",
                    "month": "",
                    "dow": "",
                    "command": " ".join(parts[1:]) if len(parts) > 1 else "",
                    "raw": line,
                })
        return jobs

    def _rewrite_crontab(self, lines: list[str], user: str | None = None) -> None:
        """Rewrite the entire crontab from a list of lines."""
        content = "\n".join(lines) + "\n"
        if user:
            cmd = f"echo {self._shell_quote(content)} | sudo crontab -u {user} -"
            self._run_sudo_command(cmd)
        else:
            cmd = f"echo {self._shell_quote(content)} | crontab -"
            self._run_command(cmd)

    def add_cron_job(self, schedule: str, command: str, user: str | None = None) -> None:
        """Add a new cron job line."""
        cmd_list = "crontab -l"
        if user:
            out, _, _ = self._run_sudo_command(f"sudo crontab -u {user} -l")
        else:
            out, _, _ = self._run_command(cmd_list)
        lines = out.splitlines() if out.strip() else []
        lines.append(f"{schedule} {command}")
        self._rewrite_crontab(lines, user)

    def remove_cron_job(self, line_index: int, user: str | None = None) -> None:
        """Remove a cron job by its line index."""
        cmd_list = "crontab -l"
        if user:
            out, _, _ = self._run_sudo_command(f"sudo crontab -u {user} -l")
        else:
            out, _, _ = self._run_command(cmd_list)
        lines = out.splitlines()
        if 0 <= line_index < len(lines):
            lines.pop(line_index)
        self._rewrite_crontab(lines, user)

    def toggle_cron_job(self, line_index: int, user: str | None = None) -> None:
        """Toggle a cron job (comment/uncomment) by its line index."""
        cmd_list = "crontab -l"
        if user:
            out, _, _ = self._run_sudo_command(f"sudo crontab -u {user} -l")
        else:
            out, _, _ = self._run_command(cmd_list)
        lines = out.splitlines()
        if 0 <= line_index < len(lines):
            line = lines[line_index]
            if line.lstrip().startswith("#"):
                lines[line_index] = line.lstrip("# ")
            else:
                lines[line_index] = "# " + line
        self._rewrite_crontab(lines, user)

    @staticmethod
    def _shell_quote(s: str) -> str:
        """Shell-quote a string for echo."""
        return "'" + s.replace("'", "'\\''") + "'"

    # ── Users & Groups ────────────────────────────────────────

    def get_users(self) -> list[dict]:
        """Parse /etc/passwd and return user list."""
        out, _, rc = self._run_command("cat /etc/passwd")
        users: list[dict] = []
        if rc != 0:
            return users
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 7:
                uid = int(parts[2])
                users.append({
                    "username": parts[0],
                    "uid": uid,
                    "gid": int(parts[3]),
                    "gecos": parts[4],
                    "home": parts[5],
                    "shell": parts[6],
                })
        return users

    def get_groups(self) -> list[dict]:
        """Parse /etc/group and return group list."""
        out, _, rc = self._run_command("cat /etc/group")
        groups: list[dict] = []
        if rc != 0:
            return groups
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 4:
                groups.append({
                    "name": parts[0],
                    "gid": int(parts[2]),
                    "members": parts[3],
                })
        return groups

    def add_user(
        self,
        username: str,
        home: str | None = None,
        shell: str | None = None,
        groups: str | None = None,
    ) -> tuple[str, int]:
        """Create a new user with sudo useradd."""
        cmd = f"useradd -m {username}"
        if home:
            cmd += f" -d {home}"
        if shell:
            cmd += f" -s {shell}"
        if groups:
            cmd += f" -G {groups}"
        out, err, rc = self._run_sudo_command(cmd)
        return (out + err).strip(), rc

    def delete_user(self, username: str, remove_home: bool = False) -> tuple[str, int]:
        """Delete a user with sudo userdel."""
        cmd = f"userdel {'-r ' if remove_home else ''}{username}"
        out, err, rc = self._run_sudo_command(cmd)
        return (out + err).strip(), rc

    def modify_user(
        self,
        username: str,
        shell: str | None = None,
        groups: str | None = None,
    ) -> tuple[str, int]:
        """Modify a user with sudo usermod."""
        cmd = f"usermod {username}"
        if shell:
            cmd = f"usermod -s {shell} {username}"
        if groups:
            cmd = f"usermod -aG {groups} {username}"
        out, err, rc = self._run_sudo_command(cmd)
        return (out + err).strip(), rc

    def change_password(self, username: str, password: str) -> tuple[str, int]:
        """Change user password with chpasswd."""
        cmd = f"echo '{username}:{password}' | sudo chpasswd"
        out, err, rc = self._run_sudo_command(cmd)
        return (out + err).strip(), rc

    def add_group(self, name: str, gid: int | None = None) -> tuple[str, int]:
        """Create a new group with sudo groupadd."""
        cmd = f"groupadd {name}"
        if gid is not None:
            cmd = f"groupadd -g {gid} {name}"
        out, err, rc = self._run_sudo_command(cmd)
        return (out + err).strip(), rc

    def delete_group(self, name: str) -> tuple[str, int]:
        """Delete a group with sudo groupdel."""
        out, err, rc = self._run_sudo_command(f"groupdel {name}")
        return (out + err).strip(), rc

    def modify_group(self, name: str, new_name: str | None = None, gid: int | None = None) -> tuple[str, int]:
        """Modify a group with sudo groupmod."""
        cmd = f"groupmod {name}"
        if new_name:
            cmd = f"groupmod -n {new_name} {name}"
        if gid is not None:
            cmd = f"groupmod -g {gid} {name}"
        out, err, rc = self._run_sudo_command(cmd)
        return (out + err).strip(), rc

    def add_user_to_group(self, username: str, group: str) -> tuple[str, int]:
        """Add a user to a group with sudo usermod -aG."""
        out, err, rc = self._run_sudo_command(f"usermod -aG {group} {username}")
        return (out + err).strip(), rc

    def remove_user_from_group(self, username: str, group: str) -> tuple[str, int]:
        """Remove a user from a group with sudo gpasswd -d."""
        out, err, rc = self._run_sudo_command(f"gpasswd -d {username} {group}")
        return (out + err).strip(), rc

    # ── Power management ─────────────────────────────────────

    def reboot(self) -> tuple[str, int]:
        out, err, rc = self._run_sudo_command("reboot", timeout=10)
        return (out + err).strip(), rc

    def poweroff(self) -> tuple[str, int]:
        out, err, rc = self._run_sudo_command("poweroff", timeout=10)
        return (out + err).strip(), rc

    def shutdown_scheduled(self, minutes: int) -> tuple[str, int]:
        out, err, rc = self._run_sudo_command(
            f"shutdown +{int(minutes)}", timeout=10
        )
        return (out + err).strip(), rc

    def cancel_shutdown(self) -> tuple[str, int]:
        out, err, rc = self._run_sudo_command("shutdown -c", timeout=10)
        return (out + err).strip(), rc
