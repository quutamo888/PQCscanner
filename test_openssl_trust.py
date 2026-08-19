from pathlib import Path

import pqc_probe


def test_finds_shining_light_ca_bundle():
    executable = r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe"
    ca_file = pqc_probe.find_openssl_ca_file(executable)
    assert ca_file == r"C:\Program Files\OpenSSL-Win64\bin\PEM\cert.pem"


def test_probe_command_uses_ca_file():
    command = pqc_probe.build_openssl_command(
        "example.com", 443, "X25519MLKEM768", ca_file="C:\\ca.pem"
    )
    assert command[command.index("-CAfile") + 1] == "C:\\ca.pem"
