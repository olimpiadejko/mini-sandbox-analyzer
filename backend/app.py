from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, Response
import html
import os
import hashlib
import pefile
from datetime import datetime
import time
import uuid
import math
import json
import shutil
import re
from backend.sandbox.virtualbox import (
    restore_snapshot,
    start_vm,
    poweroff_vm,
    get_vm_state,
    copy_file_to_guest,
    run_sample_in_guest,
    export_and_fetch_sysmon_json
)
from starlette.concurrency import run_in_threadpool
from playwright.sync_api import sync_playwright

def render_pdf_sync(html_content: str) -> bytes:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="load")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "15mm", "right": "15mm", "bottom": "15mm", "left": "15mm"}
        )
        browser.close()
        return pdf_bytes

app = FastAPI(title="Mini Dynamic Analyzer", version="1.2")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "../frontend"))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
os.makedirs(UPLOADS_DIR, exist_ok=True)


def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history_list: list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_list[:50], f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Błąd zapisu historii: {e}")


ANALYSIS_HISTORY = load_history()


@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/style.css")
async def serve_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))


@app.get("/app.js")
async def serve_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "app.js"))


def calculate_section_entropy(data: bytes) -> float:
    """Oblicza entropię Shannona dla danych sekcji pliku PE (zakres 0.0 - 8.0)."""
    if not data:
        return 0.0
    entropy = 0.0
    data_len = len(data)
    for x in range(256):
        p_x = data.count(bytes([x])) / data_len
        if p_x > 0:
            entropy += -p_x * math.log2(p_x)
    return entropy


def extract_iocs_from_binary(data: bytes) -> dict:
    """Wyciąga z pliku binarnego zakodowane adresy URL, IP oraz podejrzane polecenia/klucze."""
    urls = set(re.findall(rb"https?://[a-zA-Z0-9.\-_:/?#\[\]@!$&'()*+,;=]{5,120}", data))
    ips = set(re.findall(rb"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", data))
    valid_ips = [
        ip.decode("ascii", errors="ignore")
        for ip in ips
        if not ip.startswith((b"0.", b"127.", b"255.")) and ip != b"1.0.0.0"
    ]
    decoded_urls = [u.decode("ascii", errors="ignore") for u in urls]

    suspicious_patterns = {
        "vssadmin": "Próba usunięcia kopii zapasowych (Ransomware)",
        "wbadmin": "Modyfikacja kopii zapasowych systemu",
        "bcdedit": "Modyfikacja rozruchu Windows",
        "currentversion\\run": "Ścieżka autostartu w rejestrze",
        "powershell": "Odwołanie do PowerShell",
        "-encodedcommand": "Ukryta komenda PowerShell Base64",
        "cmd.exe /c": "Uruchamianie powłoki CMD",
        "isdebuggerpresent": "Wykrywanie debuggera (Anti-Debug)",
        "vboxguest": "Wykrywanie VirtualBox (Anti-VM)",
        "vmware": "Wykrywanie VMware (Anti-VM)"
    }
    lower_data = data.lower()
    found_behaviors = []
    for pattern, desc in suspicious_patterns.items():
        ascii_pat = pattern.encode("ascii")
        utf16_pat = pattern.encode("utf-16le")
        if ascii_pat in lower_data or utf16_pat in lower_data:
            found_behaviors.append(f"{pattern} ({desc})")

    return {
        "urls": sorted(list(set(decoded_urls)))[:10],
        "ips": sorted(list(set(valid_ips)))[:10],
        "behaviors": found_behaviors
    }


def calculate_risk_level(score: int) -> str:
    if score >= 6:
        return "Wysokie"
    elif score >= 3:
        return "Średnie"
    return "Niskie"


@app.post("/api/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    custom_apis: str = Form(""),
    timeout: int = Form(5),
    autodelete: str = Form("true")
):
    analysis_start_time = time.monotonic()
    safe_filename = f"{uuid.uuid4()}.exe"
    file_path = os.path.join(UPLOADS_DIR, safe_filename)
    temp_sysmon_dir = os.path.join(UPLOADS_DIR, f"sysmon_{uuid.uuid4()}")

    try:
        if not file.filename or not file.filename.lower().endswith(".exe"):
            raise HTTPException(status_code=400, detail="Dozwolone są wyłącznie pliki z rozszerzeniem .exe.")

        content = await file.read()
        if len(content) == 0 or len(content) > 150 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Plik przekracza dozwolony limit rozmiaru (maksymalnie 150 MB).")

        with open(file_path, "wb") as f:
            f.write(content)

        events = []
        current_time = datetime.now().strftime("%H:%M:%S")
        risk_score = 0

        # 1. Hashowanie
        md5_hash = hashlib.md5(content).hexdigest()
        sha256_hash = hashlib.sha256(content).hexdigest()

        events.append({
            "time": current_time,
            "message": f"Wgrano plik ({file.filename}). SHA-256: {sha256_hash}",
            "type": "Plik"
        })
        events.append({
            "time": current_time,
            "message": f"MD5: {md5_hash}",
            "type": "Plik"
        })

        # 2. Analiza statyczna PE + ekstrakcja IOC (Strings)
        iocs = extract_iocs_from_binary(content)
        if iocs["urls"]:
            risk_score += 2
            events.append({
                "time": current_time,
                "message": f"🔍 Wykryte adresy URL w pliku ({len(iocs['urls'])}): {', '.join(iocs['urls'][:3])}",
                "type": "Sieć"
            })
        if iocs["ips"]:
            risk_score += 1
            events.append({
                "time": current_time,
                "message": f"🔍 Wykryte adresy IP w pliku ({len(iocs['ips'])}): {', '.join(iocs['ips'][:5])}",
                "type": "Sieć"
            })
        if iocs["behaviors"]:
            risk_score += min(4, len(iocs["behaviors"]) * 2)
            events.append({
                "time": current_time,
                "message": f"🚨 Podejrzane ciągi znaków w pliku: {', '.join(iocs['behaviors'][:4])}",
                "type": "Proces"
            })

        try:
            pe = pefile.PE(file_path, fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])

            sections_count = len(pe.sections) if hasattr(pe, 'sections') else 0

            # Sprawdzenie anomalii daty kompilacji (Timestomping)
            if hasattr(pe, 'FILE_HEADER') and hasattr(pe.FILE_HEADER, 'TimeDateStamp'):
                ts = pe.FILE_HEADER.TimeDateStamp
                current_ts = int(time.time())
                if ts > current_ts + 86400 or ts < 631152000:
                    risk_score += 2
                    events.append({
                        "time": current_time,
                        "message": "⚠️ Podejrzana data kompilacji (Timestomping — data z przyszłości lub przed 1990 r.)",
                        "type": "Plik"
                    })

            # Sprawdzenie podpisu cyfrowego (Authenticode)
            sec_dir = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_SECURITY']]
            if sec_dir.VirtualAddress > 0 and sec_dir.Size > 0:
                risk_score = max(0, risk_score - 1)
                events.append({
                    "time": current_time,
                    "message": "✅ Plik zawiera certyfikat podpisu cyfrowego (Authenticode).",
                    "type": "Plik"
                })
            else:
                events.append({
                    "time": current_time,
                    "message": "ℹ️ Brak podpisu cyfrowego w nagłówku PE.",
                    "type": "Plik"
                })

            events.append({
                "time": current_time,
                "message": f"Przeanalizowano nagłówek PE. Liczba sekcji: {sections_count}",
                "type": "Proces"
            })

            # Jedna połączona pętla analizy sekcji PE (entropia + rozbieżność rozmiarów)
            if hasattr(pe, 'sections'):
                for section in pe.sections:
                    sec_name = section.Name.decode('utf-8', errors='ignore').strip('\x00')
                    if section.SizeOfRawData == 0 and section.Misc_VirtualSize > 0:
                        risk_score += 2
                        events.append({
                            "time": current_time,
                            "message": f"⚠️ Sekcja '{sec_name}' ma 0 bajtów na dysku, ale {section.Misc_VirtualSize} B w RAM (typowe dla packerów)",
                            "type": "Zasoby"
                        })

                    sec_data = section.get_data()
                    entropy = calculate_section_entropy(sec_data)
                    if entropy > 7.2:
                        risk_score += 2
                        events.append({
                            "time": current_time,
                            "message": f"Sekcja '{sec_name}': Entropia = {entropy:.2f} - ⚠️ WYSOKA (Możliwy packer/szyfrowanie)",
                            "type": "Zasoby"
                        })

            suspicious_imports = []
            all_imports = []

            if custom_apis.strip():
                target_apis = tuple(api.strip().lower() for api in custom_apis.split(",") if api.strip())
            else:
                target_apis = (
                    'virtualalloc', 'virtualprotect', 'createremotethread',
                    'writeprocessmemory', 'loadlibrary', 'getprocaddress',
                    'urldownloadtofile', 'regsetvalue', 'shellexecute'
                )

            if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    dll_name = entry.dll.decode('utf-8', errors='ignore')
                    for imported_function in entry.imports:
                        function_name = (
                            imported_function.name.decode('utf-8', errors='ignore')
                            if imported_function.name else f"Ordinal {imported_function.ordinal}"
                        )
                        all_imports.append(f"{dll_name}: {function_name}")
                        if any(api in function_name.lower() for api in target_apis):
                            suspicious_imports.append(f"{dll_name}: {function_name}")

            if suspicious_imports:
                risk_score += min(4, len(suspicious_imports))
                sus_preview = ", ".join(suspicious_imports[:5])
                events.append({
                    "time": current_time,
                    "message": f"⚠️ Wykryte podejrzane funkcje API ({len(suspicious_imports)}): {sus_preview}",
                    "type": "Proces"
                })

            events.append({
                "time": current_time,
                "message": f"Liczba wykrytych importów łącznie: {len(all_imports)}",
                "type": "Plik"
            })
            pe.close()
        except Exception:
            events.append({
                "time": current_time,
                "message": "Ostrzeżenie strukturalne PE: Plik ma niestandardową strukturę nagłówka.",
                "type": "Zasoby"
            })

        # 3. Analiza dynamiczna w piaskownicy VirtualBox
        try:
            events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": "Przywracanie czystego stanu maszyny wirtualnej (snapshot 'CzystyStan_Sysmon')...",
                "type": "Proces"
            })

            if get_vm_state() != "poweroff":
                poweroff_vm()

            restore_snapshot("CzystyStan_Sysmon")
            start_vm()

            guest_exe = f"C:\\Temp\\{safe_filename}"
            copy_file_to_guest(file_path, "C:\\Temp\\")

            events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": f"Uruchamianie próbki {file.filename} w izolowanej piaskownicy (czas obserwacji: {timeout}s)...",
                "type": "Proces"
            })
            run_sample_in_guest(guest_exe)

            time.sleep(max(1, min(timeout, 60)))

            downloaded_json_path = export_and_fetch_sysmon_json(temp_sysmon_dir)

            if os.path.exists(downloaded_json_path):
                with open(downloaded_json_path, "r", encoding="utf-8-sig") as jf:
                    sysmon_events = json.load(jf)
                    if isinstance(sysmon_events, dict):
                        sysmon_events = [sysmon_events]

                tracked_guids = set()
                for ev in sysmon_events:
                    ev_data = ev.get("EventData", {})
                    image = str(ev_data.get("Image", ""))
                    parent_image = str(ev_data.get("ParentImage", ""))
                    proc_guid = ev_data.get("ProcessGuid")
                    parent_guid = ev_data.get("ParentProcessGuid")

                    if safe_filename.lower() in image.lower() or safe_filename.lower() in parent_image.lower():
                        if proc_guid:
                            tracked_guids.add(proc_guid)
                        if parent_guid and safe_filename.lower() in parent_image.lower():
                            tracked_guids.add(parent_guid)

                for _ in range(2):
                    for ev in sysmon_events:
                        ev_data = ev.get("EventData", {})
                        if ev_data.get("ParentProcessGuid") in tracked_guids and ev_data.get("ProcessGuid"):
                            tracked_guids.add(ev_data.get("ProcessGuid"))

                for ev in sysmon_events:
                    ev_id = int(ev.get("EventId", 0))
                    ev_data = ev.get("EventData", {})
                    image = str(ev_data.get("Image", ""))
                    parent = str(ev_data.get("ParentImage", ""))
                    proc_guid = ev_data.get("ProcessGuid")
                    source_guid = ev_data.get("SourceProcessGuid")

                    is_related = (
                        safe_filename.lower() in image.lower()
                        or safe_filename.lower() in parent.lower()
                        or (proc_guid and proc_guid in tracked_guids)
                        or (source_guid and source_guid in tracked_guids)
                    )
                    if not is_related:
                        continue

                    now_s = datetime.now().strftime("%H:%M:%S")
                    proc_name = os.path.basename(image) if image else "Nieznany proces"

                    if ev_id == 1:
                        cmd_line = ev_data.get("CommandLine", "")
                        if any(lolbin in proc_name.lower() for lolbin in ("powershell.exe", "cmd.exe", "mshta.exe", "rundll32.exe", "regsvr32.exe")):
                            risk_score += 2
                        events.append({
                            "time": now_s,
                            "message": f"[Sysmon] Uruchomiono proces: {proc_name} | Polecenie: {cmd_line[:140]}",
                            "type": "Proces"
                        })

                    elif ev_id == 5:
                        events.append({
                            "time": now_s,
                            "message": f"[Sysmon] Proces zakończył działanie: {proc_name}",
                            "type": "Proces"
                        })

                    elif ev_id == 8:
                        risk_score += 4
                        target_img = os.path.basename(str(ev_data.get("TargetImage", "")))
                        events.append({
                            "time": now_s,
                            "message": f"🚨 [Sysmon] WSTRZYKNIĘCIE WĄTKU (CreateRemoteThread): {proc_name} -> {target_img}",
                            "type": "Proces"
                        })

                    elif ev_id == 10:
                        target_img = os.path.basename(str(ev_data.get("TargetImage", "")))
                        if "lsass.exe" in target_img.lower():
                            risk_score += 5
                            events.append({
                                "time": now_s,
                                "message": f"🚨 [Sysmon] Krytyczny dostęp do pamięci procesu LSASS przez {proc_name}!",
                                "type": "Proces"
                            })

                    elif ev_id == 11:
                        target_file = str(ev_data.get("TargetFilename", ""))
                        if any(ext in target_file.lower() for ext in (".exe", ".dll", ".bat", ".ps1", ".vbs")):
                            risk_score += 2
                        events.append({
                            "time": now_s,
                            "message": f"[Sysmon] Utworzono plik: {target_file}",
                            "type": "Plik"
                        })

                    elif ev_id in (12, 13, 14):
                        target_obj = str(ev_data.get("TargetObject", ""))
                        details = str(ev_data.get("Details", ""))
                        if any(key in target_obj.lower() for key in ("\\run", "winlogon", "services", "windows defender")):
                            risk_score += 3
                        msg_details = f" = {details[:80]}" if details else ""
                        events.append({
                            "time": now_s,
                            "message": f"[Sysmon] Zmiana w rejestrze: {target_obj}{msg_details}",
                            "type": "Zasoby"
                        })

                    elif ev_id == 22:
                        risk_score += 1
                        query_name = ev_data.get("QueryName", "")
                        events.append({
                            "time": now_s,
                            "message": f"[Sysmon] Zapytanie DNS ({proc_name}): {query_name}",
                            "type": "Sieć"
                        })

                    elif ev_id in (23, 26):
                        target_file = str(ev_data.get("TargetFilename", ""))
                        events.append({
                            "time": now_s,
                            "message": f"[Sysmon] Usunięto plik: {target_file}",
                            "type": "Plik"
                        })

            events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": f"Analiza dynamiczna zakończona. Śledzone procesy w drzewie: {max(1, len(tracked_guids))}.",
                "type": "Proces"
            })

        except Exception as box_err:
            events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": f"Ostrzeżenie piaskownicy VM: {str(box_err)}",
                "type": "Zasoby"
            })
        finally:
            try:
                if get_vm_state() != "poweroff":
                    poweroff_vm()
            except Exception:
                pass

            if os.path.exists(temp_sysmon_dir):
                shutil.rmtree(temp_sysmon_dir, ignore_errors=True)

        if autodelete.lower() == "true" and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

        elapsed_sec = round(time.monotonic() - analysis_start_time, 1)
        events.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": f"Podsumowanie sesji: Całkowity czas analizy: {elapsed_sec}s | Punkty ryzyka: {risk_score}",
            "type": "Zasoby"
        })

        risk_level = calculate_risk_level(risk_score)

        history_entry = {
            "id": str(uuid.uuid4())[:8],
            "filename": file.filename,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "size_mb": round(len(content) / (1024 * 1024), 2),
            "risk_level": risk_level,
            "events": events
        }
        ANALYSIS_HISTORY.insert(0, history_entry)
        save_history(ANALYSIS_HISTORY)

        return {
            "status": "completed",
            "message": "Analiza hybrydowa zakończona pomyślnie",
            "id": history_entry["id"],
            "risk_level": risk_level,
            "filename": file.filename,
            "size_bytes": len(content),
            "events": events
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"BŁĄD SERWERA: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Błąd wewnętrzny serwera: {str(e)}")


@app.get("/api/history")
async def get_history():
    summary_history = [
        {
            "id": item["id"],
            "filename": item["filename"],
            "timestamp": item["timestamp"],
            "size_mb": item["size_mb"],
            "risk_level": item["risk_level"]
        }
        for item in ANALYSIS_HISTORY
    ]
    return {"history": summary_history}


@app.delete("/api/history")
async def clear_history():
    ANALYSIS_HISTORY.clear()
    save_history(ANALYSIS_HISTORY)
    return {"status": "cleared"}

@app.get("/api/report/{analysis_id}")
async def download_report(analysis_id: str):
    target = next((item for item in ANALYSIS_HISTORY if item["id"] == analysis_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Nie znaleziono raportu o takim ID.")

    template_path = os.path.join(BASE_DIR, "report_template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    events_rows = ""
    for e in target['events']:
        tag_class = "tag-process"
        if e['type'] == "Plik":
            tag_class = "tag-file"
        elif e['type'] == "Sieć":
            tag_class = "tag-network"
        elif e['type'] == "Zasoby":
            tag_class = "tag-resources"

        safe_msg = html.escape(str(e['message']))
        events_rows += (
            f"<tr>"
            f"<td>{html.escape(str(e['time']))}</td>"
            f"<td>{safe_msg}</td>"
            f"<td><span class='tag {tag_class}'>{html.escape(str(e['type']))}</span></td>"
            f"</tr>"
        )

    risk_class = "risk-low"
    if target['risk_level'] == "Średnie":
        risk_class = "risk-medium"
    elif target['risk_level'] == "Wysokie":
        risk_class = "risk-high"

    final_html = (
        template_content
        .replace("{filename}", html.escape(target['filename']))
        .replace("{timestamp}", html.escape(target['timestamp']))
        .replace("{analysis_id}", html.escape(target['id']))
        .replace("{size_mb}", str(target['size_mb']))
        .replace("{risk_level}", html.escape(target['risk_level']))
        .replace("{risk_class}", risk_class)
        .replace("{events_rows}", events_rows)
    )

    # Konwersja HTML -> PDF z zachowaniem 100% wyglądu CSS
    pdf_bytes = await run_in_threadpool(render_pdf_sync, final_html)

    safe_pdf_name = f"raport_{os.path.splitext(target['filename'])[0]}_{target['id']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_pdf_name}"'}
    )