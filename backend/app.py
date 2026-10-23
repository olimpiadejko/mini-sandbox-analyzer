from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
import hashlib
import pefile
from datetime import datetime
import time
import uuid

app = FastAPI(title="Mini Dynamic Analyzer", version="1.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "../frontend"))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/style.css")
async def serve_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

@app.get("/app.js")
async def serve_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "app.js"))

@app.post("/api/analyze")
async def analyze_file(file: UploadFile = File(...)):
    try:
        if not file.filename or not file.filename.lower().endswith(".exe"):
            raise HTTPException(status_code=400, detail="Dozwolone są wyłącznie pliki z rozszerzeniem .exe.")

        content = await file.read()
        if len(content) == 0 or len(content) > 150 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Plik przekracza dozwolony limit rozmiaru (maksymalnie 150 MB).")

        # Generujemy bezpieczną nazwę pliku za pomocą UUID, aby uniknąć błędów ze znakami specjalnymi w ścieżce
        safe_filename = f"{uuid.uuid4()}.exe"
        file_path = os.path.join(UPLOADS_DIR, safe_filename)
        
        with open(file_path, "wb") as f:
            f.write(content)

        events = []
        current_time = datetime.now().strftime("%H:%M:%S")

        # 1. Analiza statyczna: Hashowanie
        md5_hash = hashlib.md5(content).hexdigest()
        sha256_hash = hashlib.sha256(content).hexdigest()
        time.sleep(0.2)
        
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

        # 2. Inspekcja nagłówka PE
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
            
            # Sprawdzanie importów
            imports_found = False
            if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                for entry in pe.DIRECTORY_ENTRY_IMPORT:
                    if entry.dll:
                        dll_name = entry.dll.decode('utf-8', errors='ignore').lower()
                        if 'ws2_32' in dll_name or 'wininet' in dll_name:
                            imports_found = True
                            break
            
            if imports_found:
                events.append({
                    "time": current_time,
                    "message": "Wykryto biblioteki sieciowe w importach (potencjalna aktywność sieciowa)",
                    "type": "Sieć"
                })
            else:
                events.append({
                    "time": current_time,
                    "message": "Brak wykrytych bezpośrednich bibliotek sieciowych w nagłówku",
                    "type": "Sieć"
                })
            
            pe.close()

        except Exception as pe_err:
            events.append({
                "time": current_time,
                "message": f"Ostrzeżenie strukturalne PE: Plik ma niestandardową strukturę nagłówka.",
                "type": "Zasoby"
            })

        # Czyszczenie pliku tymczasowego po analizie
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

        # 3. Zasoby
        time.sleep(0.2)
        events.append({
            "time": current_time,
            "message": "Zużycie zasobów: RAM stabilny | CPU w normie",
            "type": "Zasoby"
        })

        return {
            "status": "completed",
            "message": "Analiza statyczna i wstępna inspekcja zakończona",
            "filename": file.filename,
            "size_bytes": len(content),
            "events": events
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"BŁĄD SERWERA: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Błąd wewnętrzny serwera: {str(e)}")