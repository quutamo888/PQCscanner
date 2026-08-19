# PQC Compliance Scanner — Use Case Diagram

## ภาพรวม

ระบบ **PQC Compliance Scanner** ใช้ตรวจสอบความพร้อมด้าน Post-Quantum Cryptography (PQC) ของเว็บไซต์ วิเคราะห์ TLS handshake, key exchange และ X.509 certificate จากนั้นแสดงผลการประเมินและสร้าง Cryptography Bill of Materials (CBOM)

## Use Case Diagram

> ใช้ Mermaid flowchart แทน UML use-case notation เพื่อให้แสดงผลได้ใน Markdown viewer ทั่วไป

```mermaid
flowchart LR
    user[ผู้ใช้ระบบ]
    target[เว็บไซต์เป้าหมาย]
    crt[crt.sh]
    hacker[HackerTarget API]
    browser[Browser / File System]

    subgraph system[ระบบ PQC Compliance Scanner]
        direction TB

        input((กรอก URL / Hostname))
        upload((อัปโหลดไฟล์ TXT / CSV))
        preset((เลือก Preset))
        discover((ค้นหา Subdomain))
        import_sub((นำเข้า Subdomain เข้ารายการสแกน))
        scan_single((สแกนเว็บไซต์เดี่ยว))
        scan_batch((สแกนหลายเว็บไซต์แบบ Batch))
        cancel((ยกเลิกการสแกน))
        handshake((ตรวจสอบ TLS Handshake))
        cert((ตรวจสอบ X.509 Certificate))
        evaluate((ประเมิน PQC Compliance และ Grade))
        view_result((ดูผลการสแกน))
        filter((กรอง / ค้นหาผลลัพธ์))
        detail((ดูรายละเอียด TLS Handshake))
        cbom_view((ดู Cryptographic Asset / CBOM))
        export_csv((Export CSV))
        export_json((Export JSON))
        export_cbom((Export CycloneDX CBOM))
        theme((เปลี่ยน Dark / Light Theme))
    end

    user --> input
    user --> upload
    user --> preset
    user --> discover
    user --> import_sub
    user --> scan_single
    user --> scan_batch
    user --> cancel
    user --> view_result
    user --> filter
    user --> detail
    user --> cbom_view
    user --> export_csv
    user --> export_json
    user --> export_cbom
    user --> theme

    browser --> upload
    export_csv --> browser
    export_json --> browser
    export_cbom --> browser

    discover --> crt
    discover --> hacker
    discover -->|ตรวจสอบ DNS| target
    import_sub -.-> scan_batch

    scan_single --> target
    scan_batch --> target
    scan_single -.-> handshake
    scan_batch -.-> handshake
    handshake --> target
    handshake -.-> evaluate
    cert --> target
    scan_single -.-> cert
    scan_batch -.-> cert
    evaluate -.-> view_result
    view_result -.-> filter
    view_result -.-> detail
    view_result -.-> cbom_view
    cbom_view -.-> export_cbom

    classDef actor fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#172554
    classDef external fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#451a03
    classDef systemUse fill:#ecfdf5,stroke:#059669,stroke-width:1.5px,color:#064e3b
    class user actor
    class target,crt,hacker,browser external
    class input,upload,preset,discover,import_sub,scan_single,scan_batch,cancel,handshake,cert,evaluate,view_result,filter,detail,cbom_view,export_csv,export_json,export_cbom,theme systemUse
```

## Actors

| Actor | บทบาท |
|---|---|
| **ผู้ใช้ระบบ** | ป้อนเป้าหมาย สั่งสแกน ตรวจสอบผล และ Export รายงาน |
| **เว็บไซต์เป้าหมาย** | ให้บริการ TLS handshake และ X.509 certificate สำหรับตรวจสอบ |
| **crt.sh** | แหล่งข้อมูล Certificate Transparency สำหรับค้นหา subdomain |
| **HackerTarget API** | แหล่งข้อมูล passive subdomain discovery |
| **Browser / File System** | รับไฟล์นำเข้าและไฟล์รายงานที่ผู้ใช้ดาวน์โหลด |

## ความสัมพันธ์ของ Use Case สำคัญ

- **สแกนเว็บไซต์เดี่ยว** และ **สแกนหลายเว็บไซต์แบบ Batch** ใช้การตรวจสอบ **TLS Handshake** และ **X.509 Certificate**
- **TLS Handshake** ใช้ข้อมูลจากเว็บไซต์เป้าหมาย เพื่อระบุ TLS version, cipher suite และ key exchange group
- **ประเมิน PQC Compliance และ Grade** ใช้ผล key exchange, certificate และ TLS version เพื่อจัดเกรด เช่น `A++`, `A+`, `B`, `C`, `D`, `E`
- **ค้นหา Subdomain** เรียกใช้ `crt.sh`, `HackerTarget API` และตรวจสอบ DNS ได้
- **นำเข้า Subdomain เข้ารายการสแกน** ส่งผลลัพธ์ต่อไปยังการสแกนแบบ Batch
- **Export CycloneDX CBOM** ใช้ผลการสแกนเพื่อสร้างรายการ service, key exchange, TLS protocol และ certificate ตาม CycloneDX 1.6
- **ยกเลิกการสแกน** เป็นทางเลือกขณะ batch scan กำลังทำงาน

## ขอบเขตระบบ

ระบบครอบคลุมการรับรายการ URL, passive subdomain discovery, PQC/TLS analysis, certificate inspection, compliance grading, result filtering และ report export โดยไม่แก้ไข configuration ของเว็บไซต์เป้าหมาย