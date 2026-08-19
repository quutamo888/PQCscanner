import ssl

import pqc_probe


def test_verified_context_enforces_chain_and_hostname():
    context = pqc_probe.build_verified_context("example.com")
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
