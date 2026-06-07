from __future__ import annotations

import ipaddress
import logging
import re
import socket
import subprocess

from app.models import ScanDevice


logger = logging.getLogger(__name__)

ARP_SCAN_LINE = re.compile(
    r"^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+"
    r"(?P<mac>[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})"
    r"(?:\s+(?P<vendor>.+))?$"
)


class ArpScanError(RuntimeError):
    def __init__(self, command: list[str], returncode: int, stderr: str):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr.strip()
        details = self.stderr or f"exit status {returncode}"
        super().__init__(f"{' '.join(command)} failed: {details}")


def parse_arp_scan_output(output: str) -> list[ScanDevice]:
    devices: list[ScanDevice] = []
    for line in output.splitlines():
        match = ARP_SCAN_LINE.match(line.strip())
        if not match:
            continue
        vendor = match.group("vendor")
        devices.append(
            ScanDevice(
                mac=match.group("mac").lower(),
                ip=match.group("ip"),
                hostname=resolve_hostname(match.group("ip")),
                vendor=vendor.strip() if vendor else None,
            )
        )
    return devices


def resolve_hostname(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (OSError, socket.herror):
        return None


def detect_default_cidr() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
    except OSError:
        return None
    return str(ipaddress.ip_network(f"{local_ip}/24", strict=False))


class ArpScanner:
    def __init__(self, interface: str | None = None, cidr: str | None = None):
        self.interface = interface
        self.cidr = cidr

    def scan(self) -> list[ScanDevice]:
        target = self.cidr or detect_default_cidr()
        output_options = ["--plain", "--format=${ip}\t${mac}\t${vendor}"]
        command = ["arp-scan", *output_options, "--localnet"]
        if target:
            command = ["arp-scan", *output_options, target]
        if self.interface:
            command.extend(["--interface", self.interface])

        logger.debug(
            "Running ARP scan: target=%s interface=%s",
            target or "localnet",
            self.interface or "default",
        )
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise ArpScanError(command, result.returncode, result.stderr)
        devices = parse_arp_scan_output(result.stdout)
        logger.debug("ARP scan returned %d devices", len(devices))
        return devices
