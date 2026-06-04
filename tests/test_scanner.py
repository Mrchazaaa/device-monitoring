import subprocess

import pytest

from app.scanner import ArpScanError, ArpScanner, parse_arp_scan_output


def test_parse_arp_scan_output_extracts_devices(monkeypatch):
    monkeypatch.setattr("app.scanner.resolve_hostname", lambda ip: f"host-{ip}")
    output = """
192.168.1.1	00:11:22:33:44:55	Router Inc.
192.168.1.24	aa:bb:cc:dd:ee:01	Phone Maker
"""

    devices = parse_arp_scan_output(output)

    assert len(devices) == 2
    assert devices[0].mac == "00:11:22:33:44:55"
    assert devices[0].ip == "192.168.1.1"
    assert devices[0].hostname == "host-192.168.1.1"
    assert devices[0].vendor == "Router Inc."


def test_arp_scanner_uses_plain_machine_readable_output(monkeypatch):
    def fake_run(command, **kwargs):
        assert command == [
            "arp-scan",
            "--plain",
            "--format=${ip}\t${mac}\t${vendor}",
            "192.168.1.0/24",
            "--interface",
            "wlan0",
        ]
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="192.168.1.1\t00:11:22:33:44:55\tRouter Inc.\n",
            stderr="",
        )

    monkeypatch.setattr("app.scanner.subprocess.run", fake_run)
    monkeypatch.setattr("app.scanner.resolve_hostname", lambda ip: None)

    devices = ArpScanner(interface="wlan0", cidr="192.168.1.0/24").scan()

    assert len(devices) == 1
    assert devices[0].ip == "192.168.1.1"
    assert devices[0].vendor == "Router Inc."


def test_arp_scanner_includes_stderr_when_command_fails(monkeypatch):
    def fake_run(command, **kwargs):
        assert command == [
            "arp-scan",
            "--plain",
            "--format=${ip}\t${mac}\t${vendor}",
            "192.168.1.0/24",
        ]
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="pcap_activate: wlp1s0: permission denied\n",
        )

    monkeypatch.setattr("app.scanner.subprocess.run", fake_run)

    with pytest.raises(ArpScanError, match="pcap_activate: wlp1s0"):
        ArpScanner(cidr="192.168.1.0/24").scan()
