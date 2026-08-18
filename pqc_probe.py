import socket
import ssl
import struct
import os
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from cryptography import x509
from cryptography.hazmat.backends import default_backend

# Known PQC & Classical Group Registry
PQC_GROUPS = {
    0x11ec: {
        "name": "X25519MLKEM768",
        "type": "Hybrid KEM",
        "standard": "NIST FIPS 203 (ML-KEM) + IETF Draft",
        "desc": "Post-Quantum Hybrid (X25519 ECDH + NIST ML-KEM-768)"
    },
    0x6399: {
        "name": "x25519_kyber768draft00",
        "type": "Hybrid KEM",
        "standard": "Kyber Round 3 Draft00",
        "desc": "Post-Quantum Hybrid (X25519 ECDH + Crystals-Kyber-768 Draft00)"
    },
    0x45ac: {
        "name": "secp256r1_kyber768draft00",
        "type": "Hybrid KEM",
        "standard": "Kyber Round 3 Draft00",
        "desc": "Post-Quantum Hybrid (NIST P-256 + Crystals-Kyber-768 Draft00)"
    },
    0x11eb: {
        "name": "SecP256r1MLKEM768",
        "type": "Hybrid KEM",
        "standard": "NIST FIPS 203 (ML-KEM)",
        "desc": "Post-Quantum Hybrid (NIST P-256 + NIST ML-KEM-768)"
    },
    0x0200: {
        "name": "ML-KEM-512",
        "type": "Pure PQC KEM",
        "standard": "NIST FIPS 203 (Security Category 1)",
        "desc": "Pure Post-Quantum Key Encapsulation (ML-KEM-512)"
    },
    0x0201: {
        "name": "ML-KEM-768",
        "type": "Pure PQC KEM",
        "standard": "NIST FIPS 203 (Security Category 3)",
        "desc": "Pure Post-Quantum Key Encapsulation (ML-KEM-768)"
    },
    0x0202: {
        "name": "ML-KEM-1024",
        "type": "Pure PQC KEM",
        "standard": "NIST FIPS 203 (Security Category 5)",
        "desc": "Pure Post-Quantum Key Encapsulation (ML-KEM-1024)"
    },
    0x639a: {
        "name": "x25519_bikel1",
        "type": "Hybrid KEM",
        "standard": "BIKE Round 4",
        "desc": "Post-Quantum Hybrid (X25519 + BIKE L1)"
    },
    0x639b: {
        "name": "x25519_hqc128",
        "type": "Hybrid KEM",
        "standard": "HQC Round 4",
        "desc": "Post-Quantum Hybrid (X25519 + HQC-128)"
    }
}

CLASSICAL_GROUPS = {
    0x001d: {"name": "x25519", "desc": "Classical Curve25519 ECDH (Non-PQC)"},
    0x0017: {"name": "secp256r1", "desc": "Classical NIST P-256 ECDH (Non-PQC)"},
    0x0018: {"name": "secp384r1", "desc": "Classical NIST P-384 ECDH (Non-PQC)"},
    0x0019: {"name": "secp521r1", "desc": "Classical NIST P-521 ECDH (Non-PQC)"},
    0x0100: {"name": "ffdhe2048", "desc": "Classical Finite Field DHE 2048-bit (Non-PQC)"},
    0x0101: {"name": "ffdhe3072", "desc": "Classical Finite Field DHE 3072-bit (Non-PQC)"}
}

CIPHER_SUITES = {
    0x1301: "TLS_AES_128_GCM_SHA256",
    0x1302: "TLS_AES_256_GCM_SHA384",
    0x1303: "TLS_CHACHA20_POLY1305_SHA256",
    0xc02f: "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
    0xc030: "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
    0xc02b: "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
    0xc02c: "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
    0xcca8: "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
    0xcca9: "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
}

# HRR magic random bytes (RFC 8446)
HRR_RANDOM = b'\xcf!\xadtno\x06\xe0\x0e\xea\x9f\x1fe\x1eQ>\x01B\x90e\x86\x85\x10\xb2\xe0\xce\xddap[\x0f\x88'

def parse_target(target: str) -> Tuple[str, int]:
    """Parse raw URL or host:port into host and port."""
    target = target.strip()
    if not target:
        raise ValueError("URL หรือ Hostname ไม่สามารถเป็นค่าว่างได้")
    
    if "://" not in target:
        target = "https://" + target
        
    parsed = urllib.parse.urlparse(target)
    host = parsed.hostname or parsed.netloc.split(":")[0]
    port = parsed.port or (80 if parsed.scheme == "http" else 443)
    
    if not host:
        raise ValueError(f"ไม่สามารถอ่าน Hostname จาก: {target}")
        
    return host, port

def build_client_hello(host: str) -> bytes:
    """Craft TLS 1.3 ClientHello with PQC groups, ALPN, PSK modes, and dual key shares."""
    client_random = os.urandom(32)
    session_id = os.urandom(32)
    
    # 1. Server Name Indication (SNI) - 0x0000
    host_bytes = host.encode('utf-8')
    sni_data = struct.pack("!HB", len(host_bytes) + 3, 0) + struct.pack("!H", len(host_bytes)) + host_bytes
    ext_sni = struct.pack("!HH", 0x0000, len(sni_data)) + sni_data
    
    # 2. Supported Versions - 0x002b (TLS 1.3 = 0x0304, TLS 1.2 = 0x0303)
    sup_versions = struct.pack("!BHH", 4, 0x0304, 0x0303)
    ext_sup_versions = struct.pack("!HH", 0x002b, len(sup_versions)) + sup_versions
    
    # 3. Supported Groups - 0x000a (Offer PQC Hybrid first, then Pure PQC, then Classical)
    groups = [
        0x11ec, # X25519MLKEM768 (NIST standard)
        0x6399, # x25519_kyber768draft00 (Cloudflare/Google Kyber)
        0x45ac, # secp256r1_kyber768draft00
        0x11eb, # SecP256r1MLKEM768
        0x0201, # ML-KEM-768
        0x0200, # ML-KEM-512
        0x0202, # ML-KEM-1024
        0x001d, # x25519
        0x0017, # secp256r1
        0x0018  # secp384r1
    ]
    groups_body = b''.join(struct.pack("!H", g) for g in groups)
    groups_data = struct.pack("!H", len(groups_body)) + groups_body
    ext_sup_groups = struct.pack("!HH", 0x000a, len(groups_data)) + groups_data
    
    # 4. ALPN (0x0010) -> h2, http/1.1 (Required by modern WAFs/Cloudflare)
    alpn_list = b'\x02h2\x08http/1.1'
    alpn_data = struct.pack("!H", len(alpn_list)) + alpn_list
    ext_alpn = struct.pack("!HH", 0x0010, len(alpn_data)) + alpn_data

    # 5. PSK Key Exchange Modes (0x002d) -> psk_dhe_ke (1)
    psk_modes = struct.pack("!BB", 1, 1)
    ext_psk_modes = struct.pack("!HH", 0x002d, len(psk_modes)) + psk_modes

    # 6. EC Point Formats (0x000b) -> uncompressed (0)
    ec_formats = struct.pack("!BB", 1, 0)
    ext_ec_formats = struct.pack("!HH", 0x000b, len(ec_formats)) + ec_formats

    # 7. Signature Algorithms - 0x000d (RSA-PSS, ECDSA, RSA-PKCS1)
    sig_algos = [0x0804, 0x0403, 0x0805, 0x0503, 0x0806, 0x0603, 0x0401, 0x0501, 0x0601]
    sig_body = b''.join(struct.pack("!H", s) for s in sig_algos)
    sig_data = struct.pack("!H", len(sig_body)) + sig_body
    ext_sig = struct.pack("!HH", 0x000d, len(sig_data)) + sig_data
    
    # 8. Key Share - 0x0033 (Dual: x25519 + secp256r1)
    x25519_pk = b'\x09' + b'\x00' * 31
    ks_001d = struct.pack("!HH", 0x001d, 32) + x25519_pk
    p256_pk = bytes.fromhex("046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c2964fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5")
    ks_0017 = struct.pack("!HH", 0x0017, 65) + p256_pk
    ks_data_body = ks_001d + ks_0017
    ks_data = struct.pack("!H", len(ks_data_body)) + ks_data_body
    ext_ks = struct.pack("!HH", 0x0033, len(ks_data)) + ks_data
    
    # Combine all extensions
    all_extensions = ext_sni + ext_sup_versions + ext_sup_groups + ext_psk_modes + ext_ec_formats + ext_sig + ext_alpn + ext_ks
    ext_total = struct.pack("!H", len(all_extensions)) + all_extensions
    
    # Cipher suites (TLS 1.3 AES-GCM & ChaCha, TLS 1.2 ECDHE)
    ciphers = [0x1301, 0x1302, 0x1303, 0xc02f, 0xc030, 0xc02b, 0xc02c, 0xcca8, 0xcca9]
    cipher_bytes = struct.pack("!H", len(ciphers) * 2) + b''.join(struct.pack("!H", c) for c in ciphers)
    
    # Compression (0 = null)
    comp = b'\x01\x00'
    
    # ClientHello body
    ch_body = (
        struct.pack("!H", 0x0303) + # Legacy version
        client_random +
        struct.pack("!B", len(session_id)) + session_id +
        cipher_bytes +
        comp +
        ext_total
    )
    
    # Handshake header (Type 1 = ClientHello)
    hs_header = struct.pack("!B", 1) + struct.pack("!I", len(ch_body))[1:]
    hs_msg = hs_header + ch_body
    
    # Record header (Type 22 = Handshake, TLS 1.0 legacy version 0x0301)
    record = struct.pack("!BHH", 22, 0x0301, len(hs_msg)) + hs_msg
    return record

def parse_server_hello(resp: bytes) -> Dict[str, Any]:
    """Parse ServerHello or HelloRetryRequest handshake message."""
    if len(resp) < 4:
        raise ValueError("Server response too short")
        
    hs_type = resp[0]
    if hs_type != 2:
        raise ValueError(f"Expected ServerHello (type 2), got type {hs_type}")
        
    if len(resp) < 38:
        raise ValueError("Truncated ServerHello header")
        
    server_random = resp[6:38]
    is_hrr = (server_random == HRR_RANDOM)
    
    idx = 38
    sess_id_len = resp[idx]
    idx += 1 + sess_id_len
    
    if len(resp) < idx + 3:
        raise ValueError("Truncated ServerHello cipher/compression")
        
    selected_cipher = struct.unpack("!H", resp[idx:idx+2])[0]
    idx += 2 + 1 # Skip cipher (2) + comp (1)
    
    selected_group = None
    supported_version = None
    
    if len(resp) >= idx + 2:
        ext_len = struct.unpack("!H", resp[idx:idx+2])[0]
        idx += 2
        ext_end = idx + ext_len
        
        while idx + 4 <= ext_end and idx + 4 <= len(resp):
            ext_type, e_len = struct.unpack("!HH", resp[idx:idx+4])
            idx += 4
            e_data = resp[idx:idx+e_len]
            idx += e_len
            
            if ext_type == 0x002b: # supported_versions
                if len(e_data) >= 2:
                    supported_version = struct.unpack("!H", e_data[:2])[0]
            elif ext_type == 0x0033: # key_share
                if len(e_data) >= 2:
                    selected_group = struct.unpack("!H", e_data[:2])[0]
                    
    return {
        "is_hrr": is_hrr,
        "selected_cipher_id": selected_cipher,
        "cipher_name": CIPHER_SUITES.get(selected_cipher, f"0x{selected_cipher:04x}"),
        "supported_version": supported_version,
        "selected_group_id": selected_group,
    }

def inspect_x509_certificate(host: str, port: int = 443, timeout: float = 4.0) -> Dict[str, Any]:
    """Retrieve and inspect X.509 server certificate."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            der_cert = ssock.getpeercert(binary_form=True)
            tls_ver = ssock.version()
            tls_cipher = ssock.cipher()
            
            cert = x509.load_der_x509_certificate(der_cert, default_backend())
            sig_algo = cert.signature_algorithm_oid._name
            pub_key = cert.public_key()
            pub_type = pub_key.__class__.__name__
            issuer = cert.issuer.rfc4514_string()
            subject = cert.subject.rfc4514_string()
            not_after = cert.not_valid_after_utc.isoformat()
            not_before = cert.not_valid_before_utc.isoformat()
            
            # Extract SANs
            sans = []
            try:
                san_ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                sans = san_ext.value.get_values_for_type(x509.DNSName)
            except Exception:
                pass
                
            # Check PQC signature
            is_pqc_sig = any(pqc in sig_algo.lower() for pqc in [
                "dilithium", "mldsa", "ml-dsa", "falcon", "sphincs", "xmss", "slh-dsa"
            ])
            
            return {
                "tls_version": tls_ver,
                "tls_cipher": tls_cipher[0] if tls_cipher else None,
                "subject": subject,
                "issuer": issuer,
                "signature_algorithm": sig_algo,
                "public_key_type": pub_type,
                "valid_from": not_before,
                "valid_until": not_after,
                "sans": sans[:5],
                "is_pqc_cert": is_pqc_sig
            }

def scan_pqc(target_url: str, timeout: float = 4.0) -> Dict[str, Any]:
    """
    Perform full PQC TLS handshake scan and certificate analysis for a target URL/domain.
    """
    start_time = time.time()
    result = {
        "url": target_url,
        "host": "",
        "port": 443,
        "passed": False,
        "grade": "F",
        "status_badge": "error",
        "status_title": "เกิดข้อผิดพลาด",
        "status_title_en": "Error",
        "reason_th": "",
        "reason_en": "",
        "key_exchange": {
            "is_pqc": False,
            "group_id": None,
            "group_hex": None,
            "group_name": "None",
            "group_type": "None",
            "group_standard": "None",
            "details": "None"
        },
        "certificate": {
            "is_pqc": False,
            "signature_algo": "Unknown",
            "public_key_type": "Unknown",
            "issuer": "Unknown",
            "subject": "Unknown",
            "valid_until": "Unknown"
        },
        "tls_info": {
            "version": "Unknown",
            "cipher_suite": "Unknown",
            "handshake_type": "Unknown"
        },
        "latency_ms": 0,
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "error": None
    }
    
    try:
        host, port = parse_target(target_url)
        result["host"] = host
        result["port"] = port
        
        # 1. Custom TLS 1.3 PQC Handshake Probe
        record = build_client_hello(host)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            sock.sendall(record)
            
            # Read TLS record header (5 bytes)
            header = sock.recv(5)
            if len(header) >= 5:
                rec_type, rec_ver, rec_len = struct.unpack("!BHH", header)
                if rec_type == 22: # Handshake
                    resp = b''
                    while len(resp) < rec_len:
                        chunk = sock.recv(min(4096, rec_len - len(resp)))
                        if not chunk:
                            break
                        resp += chunk
                        
                    sh = parse_server_hello(resp)
                    
                    grp_id = sh.get("selected_group_id")
                    if grp_id is not None:
                        result["key_exchange"]["group_id"] = grp_id
                        result["key_exchange"]["group_hex"] = f"0x{grp_id:04x}"
                        
                        if grp_id in PQC_GROUPS:
                            info = PQC_GROUPS[grp_id]
                            result["key_exchange"]["is_pqc"] = True
                            result["key_exchange"]["group_name"] = info["name"]
                            result["key_exchange"]["group_type"] = info["type"]
                            result["key_exchange"]["group_standard"] = info["standard"]
                            result["key_exchange"]["details"] = info["desc"]
                        elif grp_id in CLASSICAL_GROUPS:
                            info = CLASSICAL_GROUPS[grp_id]
                            result["key_exchange"]["is_pqc"] = False
                            result["key_exchange"]["group_name"] = info["name"]
                            result["key_exchange"]["group_type"] = "Classical ECDH"
                            result["key_exchange"]["details"] = info["desc"]
                        else:
                            result["key_exchange"]["group_name"] = f"Unknown Group (0x{grp_id:04x})"
                            result["key_exchange"]["group_type"] = "Unknown"
                            
                    result["tls_info"]["version"] = "TLS 1.3" if sh.get("supported_version") == 0x0304 else "TLS 1.2"
                    result["tls_info"]["cipher_suite"] = sh.get("cipher_name", "Unknown")
                    result["tls_info"]["handshake_type"] = "HelloRetryRequest" if sh.get("is_hrr") else "ServerHello"
        except Exception as probe_err:
            pass # Fallback to standard TLS inspect
        finally:
            sock.close()
            
        # 2. X.509 Certificate Inspection & TLS verification
        time.sleep(0.05) # Polite delay between probe and cert handshake to prevent session limit drop
        cert_info = inspect_x509_certificate(host, port, timeout=timeout)
        if "error" not in cert_info:
            result["certificate"]["signature_algo"] = cert_info.get("signature_algorithm", "Unknown")
            result["certificate"]["public_key_type"] = cert_info.get("public_key_type", "Unknown")
            result["certificate"]["issuer"] = cert_info.get("issuer", "Unknown")
            result["certificate"]["subject"] = cert_info.get("subject", "Unknown")
            result["certificate"]["valid_until"] = cert_info.get("valid_until", "Unknown")
            result["certificate"]["is_pqc"] = cert_info.get("is_pqc_cert", False)
            
            if result["tls_info"]["version"] == "Unknown":
                result["tls_info"]["version"] = cert_info.get("tls_version", "Unknown")
            if result["tls_info"]["cipher_suite"] == "Unknown":
                result["tls_info"]["cipher_suite"] = cert_info.get("tls_cipher", "Unknown")
                
        # 3. Evaluate Compliance & Grading
        # Normalize TLS version (e.g. 'TLSv1.3' -> 'TLS 1.3')
        raw_tls_ver = result["tls_info"]["version"]
        if raw_tls_ver:
            tls_ver = raw_tls_ver.replace("TLSv", "TLS ").replace("TLS 1.3", "TLS 1.3").replace("TLS 1.2", "TLS 1.2").strip()
            if "1.3" in raw_tls_ver:
                tls_ver = "TLS 1.3"
            elif "1.2" in raw_tls_ver:
                tls_ver = "TLS 1.2"
            elif "1.1" in raw_tls_ver:
                tls_ver = "TLS 1.1"
            elif "1.0" in raw_tls_ver or raw_tls_ver == "TLSv1":
                tls_ver = "TLS 1.0"
        else:
            tls_ver = "Unknown"
        result["tls_info"]["version"] = tls_ver

        is_pqc_kex = result["key_exchange"]["is_pqc"]
        is_pqc_cert = result["certificate"]["is_pqc"]
        grp_name = result["key_exchange"]["group_name"]
        
        # If group name was not captured from raw probe but TLS 1.3 was established
        if grp_name == "None" and tls_ver == "TLS 1.3":
            grp_name = "Classical ECDH (X25519/P-256)"
            result["key_exchange"]["group_name"] = grp_name
            result["key_exchange"]["group_type"] = "Classical ECDH"
            result["key_exchange"]["details"] = "Standard Classical TLS 1.3 Key Exchange (Non-PQC)"
        elif grp_name == "None" and tls_ver == "TLS 1.2":
            grp_name = "Classical ECDHE / DHE"
            result["key_exchange"]["group_name"] = grp_name
            result["key_exchange"]["group_type"] = "Classical ECDHE"
            result["key_exchange"]["details"] = "Standard TLS 1.2 Key Exchange"

        if is_pqc_kex and is_pqc_cert:
            result["passed"] = True
            result["grade"] = "A++"
            result["status_badge"] = "pqc-full"
            result["status_title"] = "ผ่าน (Full Quantum-Proof)"
            result["status_title_en"] = "PASSED (Full Quantum-Proof)"
            result["reason_th"] = (
                f"ผ่านเกณฑ์สูงสุด: รองรับทั้ง Post-Quantum Key Exchange ({grp_name}) "
                f"และ Certificate ลายมือชื่อดิจิทัลแบบ PQC ({result['certificate']['signature_algo']}) "
                f"ป้องกันการโจมตีจากคอมพิวเตอร์ควอนตัมได้สมบูรณ์"
            )
            result["reason_en"] = (
                f"Passed with highest grade: Supports both PQC Key Exchange ({grp_name}) "
                f"and PQC Digital Signature Certificate ({result['certificate']['signature_algo']})."
            )
        elif is_pqc_kex:
            result["passed"] = True
            result["grade"] = "A+"
            result["status_badge"] = "pqc-ready"
            result["status_title"] = "ผ่าน (PQC Ready - Hybrid KEM)"
            result["status_title_en"] = "PASSED (PQC Ready - Hybrid KEM)"
            result["reason_th"] = (
                f"ผ่านเกณฑ์มาตรฐาน: เซิร์ฟเวอร์รองรับ Post-Quantum Key Encapsulation (Hybrid KEM: {grp_name}) "
                f"ในโปรโตคอล {tls_ver} ช่วยปกป้องข้อมูลจากการดักฟังเพื่อถอดรหัสในอนาคต (Harvest Now, Decrypt Later - HNDL)"
            )
            result["reason_en"] = (
                f"Passed standard: Server supports Post-Quantum Key Encapsulation (Hybrid KEM: {grp_name}) "
                f"over {tls_ver}, defending against Harvest Now, Decrypt Later (HNDL) quantum threats."
            )
        elif tls_ver == "TLS 1.3":
            result["passed"] = False
            result["grade"] = "B"
            result["status_badge"] = "classical-13"
            result["status_title"] = "ยังไม่ผ่าน (Classical TLS 1.3)"
            result["status_title_en"] = "NOT PASSED (Classical TLS 1.3)"
            result["reason_th"] = (
                f"ยังไม่ผ่านเกณฑ์ PQC: เซิร์ฟเวอร์ใช้ TLS 1.3 ทันสมัยแต่ยังเลือกใช้ Key Exchange แบบดั้งเดิม ({grp_name}) "
                f"ยังไม่ได้เปิดใช้งาน Hybrid PQC (เช่น X25519MLKEM768 หรือ Kyber768)"
            )
            result["reason_en"] = (
                f"Not PQC ready: Server runs modern TLS 1.3 but selected classical key exchange ({grp_name}). "
                f"Post-Quantum KEM (e.g. X25519MLKEM768 or Kyber) is not yet active."
            )
        elif tls_ver == "TLS 1.2":
            result["passed"] = False
            result["grade"] = "C"
            result["status_badge"] = "classical-12"
            result["status_title"] = "ยังไม่ผ่าน (TLS 1.2 ดั้งเดิม)"
            result["status_title_en"] = "NOT PASSED (Legacy TLS 1.2)"
            result["reason_th"] = (
                f"ยังไม่ผ่าน: ทำงานบน TLS 1.2 ซึ่งไม่รองรับกลไก PQC KeyShare สมัยใหม่ "
                f"แนะนำให้อัปเกรดเป็น TLS 1.3 และเปิดใช้งาน PQC Hybrid KEM"
            )
            result["reason_en"] = (
                f"Not PQC ready: Operates on TLS 1.2 which lacks modern PQC KeyShare mechanisms. "
                f"Upgrade to TLS 1.3 and enable PQC Hybrid KEM."
            )
        elif tls_ver in ("TLS 1.1", "TLS 1.0"):
            result["passed"] = False
            result["grade"] = "D"
            result["status_badge"] = "insecure"
            result["status_title"] = "ไม่ผ่าน (โปรโตคอลล้าสมัย)"
            result["status_title_en"] = "FAILED (Outdated Protocol)"
            result["reason_th"] = f"ไม่ผ่าน: เวอร์ชัน TLS ({tls_ver}) ล้าสมัยและถูกยกเลิกการใช้งานแล้ว มีความเสี่ยงด้านความปลอดภัย"
            result["reason_en"] = f"Failed: TLS version ({tls_ver}) is deprecated and insecure."
        else:
            result["passed"] = False
            result["grade"] = "E"
            result["status_badge"] = "error"
            result["status_title"] = "ไม่สามารถเชื่อมต่อ TLS ได้"
            result["status_title_en"] = "TLS Connection Failed"
            result["reason_th"] = f"ไม่สามารถตรวจสอบ TLS handshake ของเซิร์ฟเวอร์ได้"
            result["reason_en"] = f"Unable to establish TLS handshake with server."
            result["reason_en"] = f"Failed: TLS version ({tls_ver}) or cipher is obsolete and insecure."

    except Exception as e:
        result["passed"] = False
        result["grade"] = "E"
        result["status_badge"] = "error"
        result["status_title"] = "เกิดข้อผิดพลาดในการสแกน"
        result["status_title_en"] = "Scan Error"
        result["error"] = str(e)
        result["reason_th"] = f"เกิดข้อผิดพลาดในการเชื่อมต่อ: {str(e)}"
        result["reason_en"] = f"Connection / Scan failed: {str(e)}"

    result["latency_ms"] = round((time.time() - start_time) * 1000, 1)
    return result
