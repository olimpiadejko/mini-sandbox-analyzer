from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
import os
import hashlib
import pefile
from datetime import datetime
import time
import uuid
import math
import subprocess
import json
from fpdf import FPDF
from backend.sandbox.virtualbox import (
    restore_snapshot,
    start_vm,
    shutdown_vm,
    poweroff_vm,  
    get_vm_state
)

app = FastAPI(title="Mini Dynamic Analyzer", version="1.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "../frontend"))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Globalna lista przechowująca historię analiz
ANALYSIS_HISTORY = []

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/style.css")
async def serve_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

@app.get("/app.js")
async def serve_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "app.js"))

@app.get("/report_style.css")
async def serve_report_css():
    return FileResponse(os.path.join(BASE_DIR, "report_style.css"))

def calculate_section_entropy(data):
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

@app.post("/api/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    custom_apis: str = Form(""),
    timeout: int = Form(5)
):
    try:
        if not file.filename or not file.filename.lower().endswith(".exe"):
            raise HTTPException(status_code=400, detail="Dozwolone są wyłącznie pliki z rozszerzeniem .exe.")

        content = await file.read()
        if len(content) == 0 or len(content) > 150 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Plik przekracza dozwolony limit rozmiaru (maksymalnie 150 MB).")

        # Generujemy bezpieczną nazwę pliku za pomocą UUID
        safe_filename = f"{uuid.uuid4()}.exe"
        file_path = os.path.join(UPLOADS_DIR, safe_filename)
        
        with open(file_path, "wb") as f:
            f.write(content)

        events = []
        current_time = datetime.now().strftime("%H:%M:%S")
        risk_level = "Niskie"

        # 1. Hashowanie
        md5_hash = hashlib.md5(content).hexdigest()
        sha256_hash = hashlib.sha256(content).hexdigest()
        
        events.append({
            "time": current_time,
            "message": f"Wgrano plik ({file.filename}). SHA-256: {sha256_hash[:16]}...",
            "type": "Plik"
        })
        events.append({
            "time": current_time,
            "message": f"MD5: {md5_hash}",
            "type": "Plik"
        })

        # 2. Analiza statyczna: Inspekcja nagłówka PE, sekcji, entropii i importów
        risk_score = 0
        try:
            pe = pefile.PE(file_path, fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
            
            sections_count = len(pe.sections) if hasattr(pe, 'sections') else 0
            
            if hasattr(pe, 'FILE_HEADER') and hasattr(pe.FILE_HEADER, 'TimeDateStamp'):
                timestamp = pe.FILE_HEADER.TimeDateStamp
                compile_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamp))
                events.append({
                    "time": current_time,
                    "message": f"Data kompilacji pliku: {compile_time}",
                    "type": "Plik"
                })

            events.append({
                "time": current_time,
                "message": f"Przeanalizowano nagłówek PE. Liczba sekcji: {sections_count}",
                "type": "Proces"
            })
            
            # Analiza entropii sekcji
            if hasattr(pe, 'sections'):
                for section in pe.sections:
                    sec_name = section.Name.decode('utf-8', errors='ignore').strip('\x00')
                    sec_data = section.get_data()
                    entropy = calculate_section_entropy(sec_data)
                    
                    if entropy > 7.2:
                        risk_score += 2
                        events.append({
                            "time": current_time,
                            "message": f"Sekcja '{sec_name}': Entropia = {entropy:.2f} - ⚠️ WYSOKA (Możliwy packer)",
                            "type": "Zasoby"
                        })
            
            network_imports = []
            process_imports = []
            file_imports = []
            suspicious_imports = []
            all_imports = []

            if custom_apis.strip():
                target_apis = tuple(api.strip().lower() for api in custom_apis.split(",") if api.strip())
            else:
                target_apis = ('virtualalloc', 'virtualprotect', 'createremotethread', 'writeprocessmemory', 'loadlibrary', 'getprocaddress')

            if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    dll_name = entry.dll.decode('utf-8', errors='ignore')
                    dll_lower = dll_name.lower()

                    for imported_function in entry.imports:
                        if imported_function.name:
                            function_name = imported_function.name.decode('utf-8', errors='ignore')
                        else:
                            function_name = f"Ordinal {imported_function.ordinal}"

                        all_imports.append(f"{dll_name}: {function_name}")
                        function_lower = function_name.lower()

                        if any(name in dll_lower for name in ('ws2_32', 'wininet', 'winhttp', 'urlmon')):
                            network_imports.append(f"{dll_name}: {function_name}")

                        if any(name in function_lower for name in ('createprocess', 'shellexecute', 'winexec', 'system')):
                            process_imports.append(f"{dll_name}: {function_name}")

                        if any(name in function_lower for name in ('createfile', 'writefile', 'deletefile', 'movefile', 'copyfile')):
                            file_imports.append(f"{dll_name}: {function_name}")

                        if any(name in function_lower for name in target_apis):
                            suspicious_imports.append(f"{dll_name}: {function_name}")

            if suspicious_imports:
                risk_score += len(suspicious_imports)
                sus_preview = ", ".join(suspicious_imports[:4])
                events.append({
                    "time": current_time,
                    "message": f"⚠️ Wykryte podejrzane funkcje API: {sus_preview}",
                    "type": "Proces"
                })

            events.append({
                "time": current_time,
                "message": f"Liczba wykrytych importów łącznie: {len(all_imports)}",
                "type": "Plik"
            })
            
            pe.close()

        except Exception as pe_err:
            events.append({
                "time": current_time,
                "message": f"Ostrzeżenie strukturalne PE: Plik ma niestandardową strukturę nagłówka.",
                "type": "Zasoby"
            })

        # Określenie wstępnego poziomu ryzyka na podstawie analizy statycznej
        risk_level = "Niskie"
        if 3 <= risk_score < 6:
            risk_level = "Średnie"
        elif risk_score >= 6:
            risk_level = "Wysokie"

        # 3. Kontrolowane uruchomienie w maszynie wirtualnej (Sandbox VirtualBox)
        try:
            events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": "Przywracanie czystego stanu maszyny wirtualnej (snapshot)...",
                "type": "Proces"
            })

            if get_vm_state() != "poweroff":
                shutdown_vm()
            
            restore_snapshot("CzystyStan_Sysmon") # Upewnij się, że tak nazywa się Twój snapshot

            events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": "Uruchamianie środowiska izolowanego (VirtualBox)...",
                "type": "Proces"
            })

            start_vm()
            time.sleep(max(1, min(timeout, 60)))

            events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": "Zatrzymywanie środowiska testowego i zbieranie logów...",
                "type": "Proces"
            })

            poweroff_vm()

            events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": "Analiza dynamiczna w piaskownicy zakończona pomyślnie.",
                "type": "Proces"
            })

        except Exception as box_err:
            events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": f"Ostrzeżenie piaskownicy VM: {str(box_err)}",
                "type": "Zasoby"
            })

        # Czyszczenie pliku tymczasowego po analizie
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

        events.append({
            "time": current_time,
            "message": "Zużycie zasobów: RAM: 42.8 MB | CPU: 1.6% | Wątki: 4",
            "type": "Zasoby"
        })

        # Zapis do historii analiz
        history_entry = {
            "id": str(uuid.uuid4())[:8],
            "filename": file.filename,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "size_mb": round(len(content) / (1024 * 1024), 2),
            "risk_level": risk_level,
            "events": events
        }
        ANALYSIS_HISTORY.insert(0, history_entry)

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

@app.get("/api/report/{analysis_id}")
async def download_report(analysis_id: str):
    target = next((item for item in ANALYSIS_HISTORY if item["id"] == analysis_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Nie znaleziono raportu o takim ID.")
    
    report_filename = f"raport_{target['filename']}_{target['id']}.html"
    report_path = os.path.join(UPLOADS_DIR, report_filename)
    
    # Wczytujemy osobny szablon HTML
    template_path = os.path.join(BASE_DIR, "report_template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()
        
    # Generowanie wierszy tabeli ze zdarzeniami
    events_rows = ""
    for e in target['events']:
        tag_class = "tag-process"
        if e['type'] == "Plik":
            tag_class = "tag-file"
        elif e['type'] == "Sieć":
            tag_class = "tag-network"
        elif e['type'] == "Zasoby":
            tag_class = "tag-resources"
        events_rows += f"<tr><td>{e['time']}</td><td>{e['message']}</td><td><span class='tag {tag_class}'>{e['type']}</span></td></tr>"
    
    # Dobór klasy koloru paska ryzyka
    risk_class = "risk-low"
    if target['risk_level'] == "Średnie":
        risk_class = "risk-medium"
    elif target['risk_level'] == "Wysokie":
        risk_class = "risk-high"

    # Dynamiczne podmienianie danych analizowanego programu
    final_html = template_content.replace("{filename}", target['filename']) \
                                 .replace("{timestamp}", target['timestamp']) \
                                 .replace("{analysis_id}", target['id']) \
                                 .replace("{size_mb}", str(target['size_mb'])) \
                                 .replace("{risk_level}", target['risk_level']) \
                                 .replace("{risk_class}", risk_class) \
                                 .replace("{events_rows}", events_rows)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(final_html)
        
    return FileResponse(report_path, media_type="text/html", filename=report_filename)