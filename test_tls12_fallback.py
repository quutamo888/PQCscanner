import subprocess

import pqc_probe


def test_tls12_command_is_supported_diagnostic():
    command = pqc_probe.build_openssl_command("example.com", 443, "X25519", tls_version="1.2")
    assert "-tls1_2" in command
    assert "-tls1_3" not in command


def test_tls12_evidence_reports_verified_protocol():
    output = """
Protocol version: TLSv1.2
Ciphersuite: ECDHE-RSA-AES256-GCM-SHA384
Verification: OK
SSL handshake has read 1234 bytes and written 456 bytes
"""
    evidence = pqc_probe.parse_openssl_result(subprocess.CompletedProcess([], 0, output, ""))
    assert evidence["handshake_completed"] is True
    assert evidence["tls_version"] == "TLS 1.2"
    assert evidence["verification_status"] == "verified"
    assert evidence["transport_pqc"] is False
