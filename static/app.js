let scanResults = [];
let activeFilter = 'all';
let currentTab = 'text';
let abortController = null;

const PRESET_MAP = {
    pqc: [
        "https://pq.cloudflareresearch.com",
        "https://cloudflare.com",
        "https://google.com",
        "https://facebook.com",
        "https://instagram.com"
    ],
    classical: [
        "https://github.com",
        "https://wikipedia.org",
        "https://apple.com",
        "https://amazon.com",
        "https://microsoft.com"
    ],
    thai: [
        "https://www.thaigov.go.th",
        "https://www.dga.or.th",
        "https://www.etda.or.th",
        "https://www.bot.or.th"
    ],
    mixed: [
        "https://pq.cloudflareresearch.com",
        "https://cloudflare.com",
        "https://google.com",
        "https://github.com",
        "https://wikipedia.org",
        "https://www.thaigov.go.th"
    ]
};

let currentDiscoveredSubdomains = [];

// ==========================================
// Theme Management (Light / Dark)
// ==========================================
function initTheme() {
    const saved = localStorage.getItem('pqc_theme') || 'light';
    applyTheme(saved);
}

function applyTheme(theme) {
    if (theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        const icon = document.getElementById('themeToggleIcon');
        const text = document.getElementById('themeToggleText');
        if (icon) icon.textContent = '☀️';
        if (text) text.textContent = 'โหมดสว่าง';
    } else {
        document.documentElement.removeAttribute('data-theme');
        const icon = document.getElementById('themeToggleIcon');
        const text = document.getElementById('themeToggleText');
        if (icon) icon.textContent = '🌙';
        if (text) text.textContent = 'โหมดมืด';
    }
    localStorage.setItem('pqc_theme', theme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    applyTheme(current === 'dark' ? 'light' : 'dark');
}

function switchTab(tab) {
    currentTab = tab;
    const tabText = document.getElementById('tabText');
    const tabFile = document.getElementById('tabFile');
    const tabDig = document.getElementById('tabDig');

    const textContainer = document.getElementById('textInputContainer');
    const fileContainer = document.getElementById('fileInputContainer');
    const digContainer = document.getElementById('digInputContainer');
    const presetsContainer = document.getElementById('presetsContainer');

    // Reset tabs
    [tabText, tabFile, tabDig].forEach(t => t && t.classList.remove('active'));
    if (textContainer) textContainer.style.display = 'none';
    if (fileContainer) fileContainer.style.display = 'none';
    if (digContainer) digContainer.style.display = 'none';

    if (tab === 'text') {
        if (tabText) tabText.classList.add('active');
        if (textContainer) textContainer.style.display = 'block';
        if (presetsContainer) presetsContainer.style.display = 'flex';
    } else if (tab === 'file') {
        if (tabFile) tabFile.classList.add('active');
        if (fileContainer) fileContainer.style.display = 'block';
        if (presetsContainer) presetsContainer.style.display = 'flex';
    } else if (tab === 'dig') {
        if (tabDig) tabDig.classList.add('active');
        if (digContainer) digContainer.style.display = 'block';
        if (presetsContainer) presetsContainer.style.display = 'none';
    }
}

function loadPreset(key) {
    if (PRESET_MAP[key]) {
        switchTab('text');
        document.getElementById('urlsInput').value = PRESET_MAP[key].join('\n');
    }
}

// ==========================================
// Dig Subdomain Discovery
// ==========================================
function setDigDomain(domain) {
    const input = document.getElementById('digDomainInput');
    if (input) {
        input.value = domain;
        startDigDomain();
    }
}

async function startDigDomain() {
    const input = document.getElementById('digDomainInput');
    const domain = (input.value || '').trim();
    if (!domain) {
        alert('กรุณาระบุ Root Domain ที่ต้องการค้นหา Subdomains');
        return;
    }

    const btn = document.getElementById('btnStartDig');
    const resultsBox = document.getElementById('digResultsBox');
    const presetChips = document.querySelectorAll('#digInputContainer .preset-chip');

    // Set loading state
    btn.disabled = true;
    input.disabled = true;
    presetChips.forEach(chip => chip.style.pointerEvents = 'none');
    btn.innerHTML = `<span class="dig-loading-spinner" style="width:13px;height:13px;border-width:2px;border-color:rgba(255,255,255,0.3);border-top-color:#fff;display:inline-block;vertical-align:middle;margin-right:6px;"></span> กำลังสแกนหา...`;

    // Show immediate animated loading box
    resultsBox.style.display = 'block';
    resultsBox.innerHTML = `
      <div class="dig-loading-state">
        <div class="dig-loading-spinner"></div>
        <div class="dig-loading-info">
          <h4>กำลังสแกนค้นหา Subdomains สำหรับ <span style="color:var(--color-accent-blue-soft);font-family:var(--font-mono);">${domain}</span></h4>
          <p>กำลังค้นหาจาก Certificate Transparency Logs (crt.sh), HackerTarget, RapidDNS และตรวจสอบ DNS Records ที่ตอบสนองจริง...</p>
          <div class="dig-pulse-bar"><div class="dig-pulse-bar-inner"></div></div>
        </div>
      </div>
    `;

    try {
        const resp = await fetch('/api/discover-subdomains', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain: domain, check_dns: true, max_results: 100 })
        });

        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }

        const data = await resp.json();
        currentDiscoveredSubdomains = data.subdomains || [];

        resultsBox.innerHTML = `
          <div class="dig-results-header">
            <div>
              <strong id="digFoundCount">พบ ${currentDiscoveredSubdomains.length} Subdomains</strong>
              <span id="digDomainTarget" style="color:var(--color-ink-secondary);font-size:13px;margin-left:8px;">(${data.domain}) พร้อมใช้งานจริง</span>
            </div>
            <div class="dig-actions-group">
              <button class="btn btn-secondary" onclick="importDigResultsToInput()">นำเข้าสู่ช่องสแกน</button>
              <button class="btn btn-primary" onclick="scanDigResultsImmediately()">⚡ เริ่มสแกน PQC ทันที</button>
            </div>
          </div>
          <div class="dig-list-scroll" id="digSubdomainList">
            ${currentDiscoveredSubdomains.length === 0 
              ? '<span style="color:var(--color-ink-secondary);font-size:13px;padding:8px;">ไม่พบ Subdomain สำหรับโดเมนนี้</span>' 
              : currentDiscoveredSubdomains.map(url => {
                  const clean = url.replace(/^https?:\/\//, '');
                  return `<span class="dig-subdomain-tag">${clean}</span>`;
                }).join('')
            }
          </div>
        `;
    } catch (err) {
        console.error('Dig domain failed:', err);
        resultsBox.innerHTML = `
          <div style="color:var(--color-fail);padding:14px;background:var(--color-navy-darker);border-radius:var(--radius-md);border:1px solid rgba(235,22,0,0.3);">
            ⚠️ เกิดข้อผิดพลาดในการค้นหา Subdomains: ${err.message}
          </div>
        `;
    } finally {
        btn.disabled = false;
        input.disabled = false;
        presetChips.forEach(chip => chip.style.pointerEvents = 'auto');
        btn.innerHTML = `<svg style="width:16px;height:16px;fill:currentColor;" viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 14z"/></svg> ค้นหา Subdomains`;
    }
}

function importDigResultsToInput() {
    if (currentDiscoveredSubdomains.length === 0) {
        alert('ยังไม่มีรายการ Subdomain ที่พบ');
        return;
    }
    const currentVal = document.getElementById('urlsInput').value.trim();
    const newItems = currentDiscoveredSubdomains.join('\n');
    document.getElementById('urlsInput').value = currentVal ? `${currentVal}\n${newItems}` : newItems;
    switchTab('text');
}

function scanDigResultsImmediately() {
    if (currentDiscoveredSubdomains.length === 0) {
        alert('ยังไม่มีรายการ Subdomain ที่พบ');
        return;
    }
    document.getElementById('urlsInput').value = currentDiscoveredSubdomains.join('\n');
    switchTab('text');
    startScan();
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        const text = e.target.result;
        const lines = text.split(/\r?\n/)
            .map(line => {
                const col = line.split(',')[0].trim().replace(/^["']|["']$/g, '');
                return col;
            })
            .filter(line => line && !line.toLowerCase().startsWith('url') && !line.toLowerCase().startsWith('domain'));

        document.getElementById('urlsInput').value = lines.join('\n');
        document.getElementById('fileDropText').textContent = `โหลดไฟล์: ${file.name} (${lines.length} URLs)`;
        switchTab('text');
    };
    reader.readAsText(file);
}

// Initialization and Drag-and-drop
document.addEventListener('DOMContentLoaded', function() {
    initTheme();

    const dropzone = document.getElementById('fileInputContainer');
    if (dropzone) {
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropzone.classList.add('dragover');
            }, false);
        });
        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dropzone.classList.remove('dragover');
            }, false);
        });
        dropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length) {
                handleFileSelect({ target: { files } });
            }
        });
    }
});

function getUrlList() {
    const raw = document.getElementById('urlsInput').value;
    return raw.split(/\r?\n/)
        .map(u => u.trim())
        .filter(u => u.length > 0);
}

async function startScan() {
    const urls = getUrlList();
    if (urls.length === 0) {
        alert('กรุณากรอก URL หรือเลือก Preset ก่อนเริ่มสแกน');
        return;
    }

    const timeout = parseFloat(document.getElementById('timeoutInput').value) || 4.0;
    const concurrency = parseInt(document.getElementById('concurrencyInput').value) || 5;

    // Reset state
    scanResults = [];
    updateStats();
    updateTable();

    const btnStart = document.getElementById('btnStartScan');
    const btnCancel = document.getElementById('btnCancelScan');
    const progressWrapper = document.getElementById('progressWrapper');
    const progressBarFill = document.getElementById('progressBarFill');
    const progressStatusText = document.getElementById('progressStatusText');
    const progressPercentText = document.getElementById('progressPercentText');

    btnStart.disabled = true;
    btnCancel.style.display = 'inline-flex';
    progressWrapper.style.display = 'block';
    progressBarFill.style.width = '0%';
    progressStatusText.textContent = `กำลังเริ่มสแกน 0/${urls.length} รายการ...`;
    progressPercentText.textContent = '0%';

    abortController = new AbortController();

    try {
        const response = await fetch('/api/scan-stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls, timeout, concurrency }),
            signal: abortController.signal
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Parse NDJSON stream (newline-delimited JSON, one JSON object per line)
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Split on newlines, process complete lines
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Last element may be incomplete

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) continue;

                let payload;
                try {
                    payload = JSON.parse(trimmed);
                } catch (e) {
                    console.warn('Failed to parse NDJSON line:', trimmed, e);
                    continue;
                }

                const eventType = payload.event;

                if (eventType === 'scan_result') {
                    const item = payload.result;
                    scanResults.push(item);

                    const pct = payload.percent || 0;
                    progressBarFill.style.width = `${pct}%`;
                    progressPercentText.textContent = `${pct}%`;
                    progressStatusText.textContent = `กำลังสแกน (${payload.completed}/${payload.total}): ${item.host || item.url}`;

                    updateStats();
                    appendResultRow(item);

                } else if (eventType === 'scan_complete') {
                    progressStatusText.textContent = `การสแกนเสร็จสิ้น (รวมทั้งหมด ${payload.total} รายการ, ผ่าน ${payload.passed}, ไม่ผ่าน ${payload.failed})`;
                    progressBarFill.style.width = '100%';
                    progressPercentText.textContent = '100%';

                } else if (eventType === 'scan_start') {
                    progressStatusText.textContent = `เริ่มสแกนจำนวน ${payload.total} รายการ...`;
                }
            }
        }

    } catch (err) {
        if (err.name === 'AbortError') {
            progressStatusText.textContent = 'ยกเลิกการสแกนแล้ว';
        } else {
            console.error('Scan failed:', err);
            progressStatusText.textContent = `เกิดข้อผิดพลาด: ${err.message}`;
        }
    } finally {
        btnStart.disabled = false;
        btnCancel.style.display = 'none';
        abortController = null;
    }
}

function cancelScan() {
    if (abortController) {
        abortController.abort();
    }
}

function updateStats() {
    const total = scanResults.length;
    const passed = scanResults.filter(r => r.passed).length;
    const classical = scanResults.filter(r => !r.passed && r.grade !== 'E' && r.grade !== 'F').length;
    const errors = scanResults.filter(r => r.grade === 'E' || r.grade === 'F').length;
    const cryptoAssets = scanResults.reduce((count, r) => count + (r.key_exchange?.group_name ? 1 : 0) + (r.tls_info?.version ? 1 : 0) + (r.certificate?.signature_algo ? 1 : 0), 0);

    document.getElementById('statTotal').textContent = total;
    document.getElementById('statPassed').textContent = passed;
    document.getElementById('statClassical').textContent = classical;
    document.getElementById('statErrors').textContent = errors;

    document.getElementById('filterCountAll').textContent = total;
    document.getElementById('filterCountPassed').textContent = passed;
    document.getElementById('filterCountClassical').textContent = classical;
    document.getElementById('filterCountError').textContent = errors;

    document.getElementById('cbomStatAssets').textContent = total + cryptoAssets;
    document.getElementById('cbomStatHighRisk').textContent = scanResults.filter(r => !r.key_exchange?.is_pqc && r.grade !== 'E' && r.grade !== 'F').length;
    document.getElementById('cbomStatPlan').textContent = classical;
    document.getElementById('cbomStatReady').textContent = scanResults.filter(r => r.key_exchange?.is_pqc).length;
}

function setFilter(filter, el) {
    activeFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    if (el) el.classList.add('active');
    updateTable();
}

function handleSearch() {
    updateTable();
}

function matchesFilter(item) {
    const search = (document.getElementById('searchInput').value || '').toLowerCase().trim();
    if (search) {
        const targetStr = (item.url + ' ' + (item.host || '') + ' ' + (item.key_exchange?.group_name || '') + ' ' + (item.reason_th || '')).toLowerCase();
        if (!targetStr.includes(search)) return false;
    }

    if (activeFilter === 'passed') return item.passed === true;
    if (activeFilter === 'classical') return !item.passed && item.grade !== 'E' && item.grade !== 'F';
    if (activeFilter === 'error') return item.grade === 'E' || item.grade === 'F';
    return true;
}


function getBadgeHtml(item) {
    if (item.verification_status === 'engine_unavailable') {
        return `<span class="badge badge-error">PQC Engine Unavailable</span>`;
    }
    if (item.verification_status !== 'verified') {
        return `<span class="badge badge-error">Unverified</span>`;
    }
    if (item.transport_pqc === true && item.key_exchange?.is_pqc === true) {
        return `<span class="badge badge-pqc-full"><img src="/static/pqc-logo.svg" alt="PQC" class="badge-pqc-icon">PQC Transport Verified</span>`;
    }
    if (item.grade === 'A+' || item.passed) {
        return `<span class="badge badge-pqc-ready"><img src="/static/pqc-logo.svg" alt="PQC" class="badge-pqc-icon">PQC Ready</span>`;
    }
    if (item.grade === 'B') {
        return `<span class="badge badge-classical">Classical TLS 1.3</span>`;
    }
    if (item.grade === 'C') {
        return `<span class="badge badge-classical-legacy">Legacy TLS 1.2</span>`;
    }
    if (item.grade === 'D') {
        return `<span class="badge badge-error">Insecure TLS</span>`;
    }
    return `<span class="badge badge-error">Error</span>`;
}

function appendResultRow(item) {
    const tbody = document.getElementById('resultsTableBody');
    const emptyRow = document.getElementById('emptyRow');
    if (emptyRow) emptyRow.remove();

    if (!matchesFilter(item)) return;

    const tr = document.createElement('tr');
    tr.innerHTML = renderRowContent(item, scanResults.length - 1);
    tbody.appendChild(tr);
}

function renderRowContent(item, idx) {
    const isPqc = item.key_exchange?.is_pqc;
    const kexName = item.key_exchange?.group_name || 'None';
    const kexClass = isPqc ? 'kex-tag pqc' : 'kex-tag';
    const cleanUrl = item.url.replace(/^https?:\/\//, '');

    return `
        <td>
            <div class="url-cell">
                <a href="${item.url}" target="_blank" rel="noopener noreferrer">${cleanUrl}</a>
            </div>
        </td>
        <td>${getBadgeHtml(item)}</td>
        <td>
            <span class="${kexClass}">${kexName}</span>
        </td>
        <td>
            <span style="font-family:var(--font-mono);">${item.tls_info?.version || 'N/A'}</span>
        </td>
        <td>
            <div class="reason-text">${item.reason_th || item.reason_en || 'ไม่มีข้อมูล'}</div>
        </td>
        <td>
            <span class="latency-tag">${item.latency_ms} ms</span>
        </td>
        <td>
            <button class="btn-inspect" onclick="openModal(${idx})">เจาะลึก</button>
        </td>
    `;
}

function updateTable() {
    const tbody = document.getElementById('resultsTableBody');
    tbody.innerHTML = '';

    const filtered = scanResults.filter(matchesFilter);

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr id="emptyRow">
                <td colspan="7">
                    <div class="empty-state">
                        <p>${scanResults.length === 0 ? 'ยังไม่มีข้อมูลผลการสแกน' : 'ไม่พบรายการที่ตรงกับเงื่อนไขการค้นหา'}</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    filtered.forEach((item) => {
        const originalIndex = scanResults.indexOf(item);
        const tr = document.createElement('tr');
        tr.innerHTML = renderRowContent(item, originalIndex);
        tbody.appendChild(tr);
    });
}

function openModal(index) {
    const item = scanResults[index];
    if (!item) return;

    const modal = document.getElementById('detailModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');

    modalTitle.textContent = `TLS Handshake Detail: ${item.host || item.url}`;

    const kex = item.key_exchange || {};
    const cert = item.certificate || {};
    const tls = item.tls_info || {};

    modalBody.innerHTML = `
        <div class="modal-section">
            <div class="modal-section-title">สรุปผลการประเมิน PQC</div>
            <div class="detail-row">
                <span class="detail-label">สถานะ:</span>
                <span class="detail-value">${getBadgeHtml(item)} (${item.status_title})</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">เหตุผลภาษาไทย:</span>
                <span class="detail-value" style="color:var(--color-primary);text-align:left;font-family:var(--font-text);">${item.reason_th}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">เหตุผลภาษาอังกฤษ:</span>
                <span class="detail-value" style="color:var(--color-ink-muted-48);text-align:left;font-family:var(--font-text);">${item.reason_en}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Verification Status:</span>
                <span class="detail-value">${item.verification_status || 'unknown'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">OpenSSL Engine:</span>
                <span class="detail-value">${item.evidence?.engine_version || 'Unavailable'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">PQC Transport:</span>
                <span class="detail-value">${item.transport_pqc === true ? 'Verified' : item.transport_pqc === false ? 'Not detected' : 'Unknown'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Certificate Trust:</span>
                <span class="detail-value">${item.certificate_trusted ? 'Trusted' : 'Not verified'}</span>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">การแลกเปลี่ยนกุญแจ (Key Exchange / KEM)</div>
            <div class="detail-row">
                <span class="detail-label">PQC Key Exchange:</span>
                <span class="detail-value" style="color:${kex.is_pqc ? 'var(--color-pass-dark)' : 'var(--color-warn-dark)'};font-weight:600;">${kex.is_pqc ? 'YES — รองรับ Post-Quantum' : 'NO — Classical Only'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Selected Group:</span>
                <span class="detail-value">${kex.group_name} (${kex.group_hex || 'N/A'})</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Group Type:</span>
                <span class="detail-value">${kex.group_type || 'N/A'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">มาตรฐานที่อ้างอิง:</span>
                <span class="detail-value">${kex.group_standard || 'N/A'}</span>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">ใบรับรองดิจิทัล (X.509 Certificate)</div>
            <div class="detail-row">
                <span class="detail-label">ลายมือชื่อ PQC:</span>
                <span class="detail-value">${cert.is_pqc ? 'YES (PQC Signature)' : 'NO (Classical Signature)'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Signature Algorithm:</span>
                <span class="detail-value">${cert.signature_algo || 'N/A'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Public Key Type:</span>
                <span class="detail-value">${cert.public_key_type || 'N/A'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">ผู้ออกใบรับรอง (Issuer):</span>
                <span class="detail-value" style="font-size:0.75rem;">${cert.issuer || 'N/A'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">วันหมดอายุ:</span>
                <span class="detail-value">${cert.valid_until || 'N/A'}</span>
            </div>
        </div>

        <div class="modal-section">
            <div class="modal-section-title">ข้อมูลโปรโตคอล TLS & Latency</div>
            <div class="detail-row">
                <span class="detail-label">TLS Version:</span>
                <span class="detail-value">${tls.version || 'N/A'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Cipher Suite:</span>
                <span class="detail-value">${tls.cipher_suite || 'N/A'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Handshake Latency:</span>
                <span class="detail-value">${item.latency_ms} ms</span>
            </div>
        </div>

        <div class="modal-section" style="border:1px dashed var(--color-hairline);">
            <div class="modal-section-title" style="color:var(--color-primary);display:flex;justify-content:space-between;align-items:center;">
                <span>🛡️ CycloneDX 1.6 CBOM Mapping</span>
                <span style="font-size:10px;font-weight:400;text-transform:none;color:var(--color-ink-muted-48);">cryptoProperties Spec</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Asset Type:</span>
                <span class="detail-value">algorithm (KEM) + protocol (TLS)</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">NIST Quantum Level:</span>
                <span class="detail-value" style="font-weight:600;color:${kex.is_pqc ? 'var(--color-pass-dark)' : 'var(--color-warn-dark)'};">
                    ${kex.is_pqc ? 'Category 3 (AES-192 / ML-KEM-768)' : 'Category 0 (Quantum Vulnerable)'}
                </span>
            </div>
            <div class="detail-row">
                <span class="detail-label">CBOM Component Ref:</span>
                <span class="detail-value" style="font-size:11px;">crypto-kex-${item.host || 'unknown'}</span>
            </div>
        </div>
    `;

    modal.classList.add('active');
}

function closeModal() {
    document.getElementById('detailModal').classList.remove('active');
}

window.addEventListener('click', (e) => {
    const modal = document.getElementById('detailModal');
    if (e.target === modal) {
        closeModal();
    }
});

function exportResults(format) {
    if (scanResults.length === 0) {
        alert('ไม่มีข้อมูลสำหรับ Export กรุณาสแกนก่อน');
        return;
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);

    if (format === 'cbom') {
        fetch('/api/export-cbom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ results: scanResults })
        })
        .then(res => res.json())
        .then(cbomData => {
            const jsonStr = JSON.stringify(cbomData, null, 2);
            downloadFile(jsonStr, `pqc_cbom_cyclonedx_1.6_${timestamp}.json`, 'application/json');
        })
        .catch(err => {
            console.error('CBOM export failed:', err);
            alert(`เกิดข้อผิดพลาดในการสร้าง CBOM: ${err.message}`);
        });
    } else if (format === 'json') {
        const jsonStr = JSON.stringify(scanResults, null, 2);
        downloadFile(jsonStr, `pqc_scan_report_${timestamp}.json`, 'application/json');
    } else if (format === 'csv') {
        const headers = [
            'URL', 'Host', 'Status', 'Grade', 'PQC_Key_Exchange',
            'KEM_Group', 'Group_Hex', 'TLS_Version', 'Cipher_Suite',
            'PQC_Certificate', 'Cert_Signature_Algo', 'Reason_TH', 'Reason_EN', 'Latency_ms'
        ];

        const rows = scanResults.map(r => [
            `"${(r.url || '').replace(/"/g, '""')}"`,
            `"${(r.host || '').replace(/"/g, '""')}"`,
            `"${(r.status_title || '').replace(/"/g, '""')}"`,
            `"${r.grade || ''}"`,
            r.key_exchange?.is_pqc ? 'YES' : 'NO',
            `"${(r.key_exchange?.group_name || '').replace(/"/g, '""')}"`,
            `"${r.key_exchange?.group_hex || ''}"`,
            `"${r.tls_info?.version || ''}"`,
            `"${(r.tls_info?.cipher_suite || '').replace(/"/g, '""')}"`,
            r.certificate?.is_pqc ? 'YES' : 'NO',
            `"${(r.certificate?.signature_algo || '').replace(/"/g, '""')}"`,
            `"${(r.reason_th || '').replace(/"/g, '""')}"`,
            `"${(r.reason_en || '').replace(/"/g, '""')}"`,
            r.latency_ms || 0
        ]);

        const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(e => e.join(','))].join('\r\n');
        downloadFile(csvContent, `pqc_scan_report_${timestamp}.csv`, 'text/csv;charset=utf-8;');
    }
}

function downloadFile(content, fileName, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }, 100);
}

// ==========================================
// CBOM Inspector Modal
// ==========================================
async function openCbomModal() {
    if (scanResults.length === 0) {
        alert('ไม่มีข้อมูลสำหรับแสดง CBOM กรุณาสแกนก่อน');
        return;
    }

    const modal = document.getElementById('cbomModal');
    const modalBody = document.getElementById('cbomModalBody');
    modalBody.innerHTML = `<div style="text-align:center;padding:40px;color:var(--color-ink-muted-48);">⏳ กำลังสร้างโครงสร้าง CycloneDX 1.6 CBOM...</div>`;
    modal.classList.add('active');

    try {
        const resp = await fetch('/api/export-cbom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ results: scanResults })
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const cbom = await resp.json();

        const components = cbom.components || [];
        const services = components.filter(c => c.type === 'service');
        const cryptoAssets = components.filter(c => c.type === 'cryptographic-asset');
        const kemAssets = cryptoAssets.filter(c => c.cryptoProperties?.assetType === 'algorithm');
        const pqcKems = kemAssets.filter(c => c.cryptoProperties?.algorithmProperties?.primitive === 'kem');

        modalBody.innerHTML = `
          <div class="cbom-readable-toolbar">
            <input id="cbomSearchInput" class="cbom-search" placeholder="ค้นหา asset หรือ domain..." oninput="filterCbomRows()">
            <div class="cbom-filter-group">
              <button class="cbom-filter active" onclick="setCbomFilter('all', this)">ทั้งหมด</button>
              <button class="cbom-filter" onclick="setCbomFilter('risk', this)">เสี่ยงสูง</button>
              <button class="cbom-filter" onclick="setCbomFilter('pqc', this)">PQC Ready</button>
            </div>
          </div>
          <div class="cbom-table-wrap"><table class="cbom-readable-table"><thead><tr><th>สินทรัพย์ / Domain</th><th>ประเภท</th><th>ความเสี่ยง</th><th>สถานะ PQC</th><th>คำแนะนำ</th></tr></thead><tbody id="cbomReadableBody"></tbody></table></div>
          <div class="cbom-detail-note">กดปุ่ม “เจาะลึก” ในตารางผลสแกน เพื่อดู TLS, KEX และ Certificate เต็มรายการ</div>
          <div class="cbom-modal-actions"><button class="btn btn-secondary" onclick="exportResults('cbom')">↓ ดาวน์โหลด CBOM JSON</button><button class="btn btn-primary" onclick="closeCbomModal()">ปิดหน้าต่าง</button></div>
        `;
        renderCbomRows();
    } catch (err) {
        console.error('Failed to render CBOM modal:', err);
        modalBody.innerHTML = `<div style="color:var(--color-fail);padding:20px;">เกิดข้อผิดพลาดในการโหลด CBOM: ${err.message}</div>`;
    }
}

function renderCbomRows() {
    const body = document.getElementById('cbomReadableBody');
    if (!body) return;
    const search = (document.getElementById('cbomSearchInput')?.value || '').toLowerCase();
    const filter = window.cbomFilter || 'all';
    body.innerHTML = scanResults.filter(r => {
        const text = `${r.host || r.url} ${r.key_exchange?.group_name || ''} ${r.tls_info?.version || ''}`.toLowerCase();
        return (!search || text.includes(search)) && (filter === 'all' || filter === 'pqc' && r.key_exchange?.is_pqc || filter === 'risk' && !r.key_exchange?.is_pqc && r.grade !== 'E' && r.grade !== 'F');
    }).map(r => {
        const pqc = r.key_exchange?.is_pqc;
        const risk = r.grade === 'E' || r.grade === 'F' ? 'ตรวจไม่ได้' : pqc ? 'ต่ำ' : 'สูง';
        return `<tr><td><strong>${r.host || r.url}</strong><small>${r.url}</small></td><td>${r.key_exchange?.group_name || 'ไม่พบ KEX'}<small>${r.tls_info?.version || 'TLS N/A'}</small></td><td><span class="cbom-risk cbom-risk--${risk === 'สูง' ? 'high' : risk === 'ต่ำ' ? 'low' : 'unknown'}">${risk}</span></td><td><span class="cbom-status ${pqc ? 'cbom-status--ready' : ''}">${pqc ? '<img src="/static/pqc-logo.svg" alt="PQC" class="badge-pqc-icon" style="width:13px;height:13px;margin-right:4px;">PQC Ready' : 'Classical'}</span></td><td>${pqc ? 'ติดตามมาตรฐานต่อ' : 'วางแผนเปลี่ยนเป็น PQC'}</td></tr>`;
    }).join('') || '<tr><td colspan="5" class="cbom-empty">ไม่พบรายการ</td></tr>';
}
function filterCbomRows() { renderCbomRows(); }
function setCbomFilter(filter, el) {
    window.cbomFilter = filter;
    document.querySelectorAll('.cbom-filter').forEach(btn => btn.classList.remove('active'));
    el?.classList.add('active');
    renderCbomRows();
}

function closeCbomModal() {
    document.getElementById('cbomModal').classList.remove('active');
}

window.addEventListener('click', (e) => {
    const modal = document.getElementById('detailModal');
    const cbomModal = document.getElementById('cbomModal');
    if (e.target === modal) closeModal();
    if (e.target === cbomModal) closeCbomModal();
});

// Initialize theme on load
initTheme();
document.addEventListener('DOMContentLoaded', initTheme);
