from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.system_service import SystemService

logger = logging.getLogger(__name__)


class VmService:
    """Wraps ``virsh`` commands for libvirt/KVM/QEMU VM management."""

    def __init__(self, system_service: SystemService):
        self._sys = system_service

    # ── List / Info ──────────────────────────────────────────

    def get_vms(self) -> list[dict]:
        """Return a list of all VMs with detailed info from ``virsh dominfo``."""
        out, err, rc = self._sys._run_command("virsh list --all", timeout=15)
        if rc != 0:
            raise RuntimeError(err.strip() or "virsh list failed")

        names: list[str] = []
        for line in out.splitlines()[2:]:  # skip header + separator
            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) >= 2:
                names.append(parts[1])

        vms: list[dict] = []
        for name in names:
            try:
                info = self._dominfo(name)
                # Fetch IPs only for running VMs
                if info["state"] == "running":
                    try:
                        addrs = self.get_vm_addresses(name)
                        ipv4 = [a["address"] for a in addrs if a["protocol"] == "ipv4"]
                        info["ip"] = ", ".join(ipv4) if ipv4 else "-"
                    except Exception:
                        info["ip"] = "-"
                else:
                    info["ip"] = "-"
                vms.append(info)
            except Exception:
                logger.warning("Failed to get dominfo for %s", name, exc_info=True)
        return vms

    def _dominfo(self, name: str) -> dict:
        """Parse ``virsh dominfo <name>`` into a dict."""
        out, err, rc = self._sys._run_command(f"virsh dominfo {name}", timeout=10)
        if rc != 0:
            raise RuntimeError(err.strip() or f"virsh dominfo {name} failed")

        info: dict[str, str] = {}
        for line in out.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                info[key.strip().lower()] = val.strip()

        mem_kib = int(info.get("max memory", "0").replace("KiB", "").strip() or "0")
        return {
            "name": info.get("name", name),
            "state": info.get("state", "unknown"),
            "id": info.get("id", "-"),
            "vcpus": info.get("cpu(s)", "-"),
            "memory_mib": mem_kib // 1024,
            "autostart": info.get("autostart", "-"),
            "persistent": info.get("persistent", "-"),
            "uuid": info.get("uuid", ""),
        }

    # ── Lifecycle actions ────────────────────────────────────

    def vm_start(self, name: str) -> tuple[str, int]:
        out, err, rc = self._sys._run_command(f"virsh start {name}", timeout=30)
        return (out + err).strip(), rc

    def vm_shutdown(self, name: str) -> tuple[str, int]:
        out, err, rc = self._sys._run_command(f"virsh shutdown {name}", timeout=30)
        return (out + err).strip(), rc

    def vm_destroy(self, name: str) -> tuple[str, int]:
        out, err, rc = self._sys._run_command(f"virsh destroy {name}", timeout=30)
        return (out + err).strip(), rc

    def vm_reboot(self, name: str) -> tuple[str, int]:
        out, err, rc = self._sys._run_command(f"virsh reboot {name}", timeout=30)
        return (out + err).strip(), rc

    def vm_suspend(self, name: str) -> tuple[str, int]:
        out, err, rc = self._sys._run_command(f"virsh suspend {name}", timeout=30)
        return (out + err).strip(), rc

    def vm_resume(self, name: str) -> tuple[str, int]:
        out, err, rc = self._sys._run_command(f"virsh resume {name}", timeout=30)
        return (out + err).strip(), rc

    def vm_undefine(self, name: str) -> tuple[str, int]:
        out, err, rc = self._sys._run_command(
            f"virsh undefine {name} --managed-save --snapshots-metadata",
            timeout=60,
        )
        return (out + err).strip(), rc

    def vm_set_autostart(self, name: str, enable: bool) -> tuple[str, int]:
        flag = "" if enable else " --disable"
        out, err, rc = self._sys._run_command(
            f"virsh autostart{flag} {name}", timeout=15
        )
        return (out + err).strip(), rc

    # ── Details ──────────────────────────────────────────────

    def get_vm_disks(self, name: str) -> list[dict]:
        """Parse ``virsh domblklist --details``."""
        out, err, rc = self._sys._run_command(
            f"virsh domblklist {name} --details", timeout=10
        )
        if rc != 0:
            return []

        disks: list[dict] = []
        lines = out.splitlines()
        for line in lines[2:]:  # skip header + separator
            parts = line.split()
            if len(parts) >= 4:
                disks.append({
                    "type": parts[0],
                    "device": parts[1],
                    "target": parts[2],
                    "source": " ".join(parts[3:]) if parts[3] != "-" else "-",
                })
        return disks

    def get_vm_interfaces(self, name: str) -> list[dict]:
        """Parse ``virsh domiflist``."""
        out, err, rc = self._sys._run_command(
            f"virsh domiflist {name}", timeout=10
        )
        if rc != 0:
            return []

        interfaces: list[dict] = []
        lines = out.splitlines()
        for line in lines[2:]:  # skip header + separator
            parts = line.split()
            if len(parts) >= 5:
                interfaces.append({
                    "interface": parts[0],
                    "type": parts[1],
                    "source": parts[2],
                    "model": parts[3],
                    "mac": parts[4],
                })
        return interfaces

    def get_vm_memory_stats(self, name: str) -> dict:
        """Parse ``virsh dommemstat``."""
        out, err, rc = self._sys._run_command(
            f"virsh dommemstat {name}", timeout=10
        )
        if rc != 0:
            return {}

        stats: dict[str, int] = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) == 2:
                try:
                    stats[parts[0]] = int(parts[1])
                except ValueError:
                    pass
        return stats

    def get_vm_addresses(self, name: str) -> list[dict]:
        """Parse ``virsh domifaddr`` to get IP addresses of a running VM."""
        out, err, rc = self._sys._run_command(
            f"virsh domifaddr {name}", timeout=10
        )
        if rc != 0:
            return []

        addresses: list[dict] = []
        for line in out.splitlines()[2:]:  # skip header + separator
            parts = line.split()
            if len(parts) >= 4:
                addr = parts[3].split("/")[0]  # strip CIDR prefix
                addresses.append({
                    "interface": parts[0],
                    "mac": parts[1],
                    "protocol": parts[2],
                    "address": addr,
                    "full": parts[3],
                })
        return addresses

    # ── Snapshots ────────────────────────────────────────────

    def get_snapshots(self, name: str) -> list[dict]:
        """Parse ``virsh snapshot-list --details``."""
        out, err, rc = self._sys._run_command(
            f"virsh snapshot-list {name} --details", timeout=15
        )
        if rc != 0:
            return []

        snapshots: list[dict] = []
        lines = out.splitlines()
        # Find the header separator line to know where data starts
        data_start = 0
        for i, line in enumerate(lines):
            if line.startswith("---") or line.startswith(" ---"):
                data_start = i + 1
                break

        for line in lines[data_start:]:
            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) >= 4:
                snapshots.append({
                    "name": parts[0],
                    "creation_time": parts[1],
                    "state": parts[2],
                    "parent": parts[3] if len(parts) > 3 else "",
                })
        return snapshots

    def create_snapshot(self, name: str, snap_name: str) -> tuple[str, int]:
        out, err, rc = self._sys._run_command(
            f"virsh snapshot-create-as {name} --name {snap_name} --atomic",
            timeout=120,
        )
        return (out + err).strip(), rc

    def revert_snapshot(self, name: str, snap_name: str) -> tuple[str, int]:
        out, err, rc = self._sys._run_command(
            f"virsh snapshot-revert {name} {snap_name} --force",
            timeout=120,
        )
        return (out + err).strip(), rc

    def delete_snapshot(self, name: str, snap_name: str) -> tuple[str, int]:
        out, err, rc = self._sys._run_command(
            f"virsh snapshot-delete {name} {snap_name}",
            timeout=60,
        )
        return (out + err).strip(), rc

    # ── Export / Import / Clone ───────────────────────────────

    def export_vm(self, name: str, output_dir: str) -> tuple[str, int]:
        """Export VM XML definition and list disk paths."""
        # Dump XML
        out, err, rc = self._sys._run_command(
            f"virsh dumpxml {name}", timeout=30
        )
        if rc != 0:
            return (err or "Failed to dump XML").strip(), rc

        xml_path = f"{output_dir}/{name}.xml"
        # Write XML to file
        escaped_xml = out.replace("'", "'\\''")
        write_cmd = f"cat > {xml_path} << 'XMLEOF'\n{out}\nXMLEOF"
        _, werr, wrc = self._sys._run_command(write_cmd, timeout=15)
        if wrc != 0:
            return f"Failed to write XML: {werr}".strip(), wrc

        # Copy disk files
        disks = self.get_vm_disks(name)
        copied: list[str] = [xml_path]
        for disk in disks:
            src = disk.get("source", "")
            if src and src != "-":
                dst = f"{output_dir}/{src.split('/')[-1]}"
                cp_out, cp_err, cp_rc = self._sys._run_command(
                    f"cp '{src}' '{dst}'", timeout=600
                )
                if cp_rc == 0:
                    copied.append(dst)
                else:
                    return f"Failed to copy disk {src}: {cp_err}".strip(), cp_rc

        return f"Exported to: {', '.join(copied)}", 0

    def import_vm(self, xml_path: str) -> tuple[str, int]:
        """Import (define) a VM from an XML file."""
        out, err, rc = self._sys._run_command(
            f"virsh define '{xml_path}'", timeout=30
        )
        return (out + err).strip(), rc

    def clone_vm(self, name: str, new_name: str) -> tuple[str, int]:
        """Clone a VM using virt-clone."""
        out, err, rc = self._sys._run_command(
            f"virt-clone --original {name} --name {new_name} --auto-clone",
            timeout=600,
        )
        return (out + err).strip(), rc
