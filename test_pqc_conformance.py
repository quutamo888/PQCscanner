import subprocess

import pqc_probe


def test_x25519_mlkem768_is_current_standard():
    info = pqc_probe.get_group_info(0x11EC)
    assert info["name"] == "X25519MLKEM768"
    assert info["standard_status"] == "standard"
    assert info["reference"] == "RFC 10024"


def test_draft_group_is_not_reported_as_standard():
    info = pqc_probe.get_group_info(0x6399)
    assert info["standard_status"] == "draft"
    assert info["is_pqc"] is False


def test_openssl_command_requires_single_pqc_group_and_hostname_validation():
    command = pqc_probe.build_openssl_command(
        "example.com", 443, "X25519MLKEM768", timeout=4.0
    )
    assert command[:2] == ["openssl", "s_client"]
    assert "-tls1_3" in command
    assert command[command.index("-groups") + 1] == "X25519MLKEM768"
    assert command[command.index("-verify_hostname") + 1] == "example.com"
    assert "-brief" in command


def test_parse_openssl_success_requires_completed_tls13_handshake():
    output = """
Protocol version: TLSv1.3
Ciphersuite: TLS_AES_128_GCM_SHA256
Verification: OK
SSL handshake has read 1234 bytes and written 456 bytes
"""
    evidence = pqc_probe.parse_openssl_result(
        subprocess.CompletedProcess([], 0, output, "")
    )
    assert evidence["handshake_completed"] is True
    assert evidence["tls_version"] == "TLS 1.3"
    assert evidence["certificate_trusted"] is True
    assert evidence["verification_status"] == "verified"


def test_parse_openssl_failure_never_reports_pqc_pass():
    evidence = pqc_probe.parse_openssl_result(
        subprocess.CompletedProcess([], 1, "", "Connection refused")
    )
    assert evidence["handshake_completed"] is False
    assert evidence["verification_status"] == "error"
    assert evidence["transport_pqc"] is False


def test_engine_unavailable_is_explicit(monkeypatch):
    monkeypatch.setattr(pqc_probe, "find_openssl", lambda: None)
    result = pqc_probe.scan_pqc("https://example.com")
    assert result["verification_status"] == "engine_unavailable"
    assert result["passed"] is False
    assert result["transport_pqc"] is None
    assert result["error"] == "OpenSSL 3.5+ PQC engine unavailable"
