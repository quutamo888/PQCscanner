import subprocess

import pqc_probe


def test_openssl_version_gate_accepts_only_3_5_or_newer(monkeypatch):
    monkeypatch.setattr(pqc_probe, "find_openssl", lambda: "openssl.exe")
    monkeypatch.setattr(
        pqc_probe.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "OpenSSL 3.5.0 1 Apr 2025", ""),
    )
    assert pqc_probe.openssl_supports_pqc("openssl.exe") is True


def test_openssl_version_gate_rejects_old_engine(monkeypatch):
    monkeypatch.setattr(
        pqc_probe.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "OpenSSL 3.0.13 30 Jan 2024", ""),
    )
    assert pqc_probe.openssl_supports_pqc("openssl.exe") is False


def test_probe_command_uses_process_timeout_not_unknown_s_client_option():
    command = pqc_probe.build_openssl_command("example.com", 443, "X25519MLKEM768")
    assert "-timeout" not in command
