from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os

app = FastAPI(title="Mini Dynamic Analyzer", version="1.0")

# Ustalamy ścieżkę bezpośrednio do folderu frontend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "../frontend"))

# Główna strona aplikacji
@app.get("/")
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Nie znaleziono pliku index.html"}

# Bezpośrednie serwowanie pliku style.css 
@app.get("/style.css")
async def serve_css():
    css_path = os.path.join(FRONTEND_DIR, "style.css")
    if os.path.exists(css_path):
        return FileResponse(css_path)
    return {"error": "Nie znaleziono pliku style.css"}

@app.get("/app.js")
async def serve_js():
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    if os.path.exists(js_path):
        return FileResponse(js_path)
    return {"error": "Nie znaleziono pliku app.js"}

# Endpoint testowy
@app.get("/api/status")
async def get_status():
    return {"status": "online", "message": "Mini Dynamic Analyzer działa poprawnie!"}


@app.get("/api/demo-analysis")
async def demo_analysis():
    from datetime import datetime

    current_time = datetime.now().strftime("%H:%M:%S")

    return {
        "status": "completed",
        "message": "Analiza demonstracyjna zakończona",
        "events": [
            {
                "time": current_time,
                "message": "Rozpoczęto analizę demonstracyjną",
                "type": "Status"
            },
            {
                "time": current_time,
                "message": "Sprawdzono podstawowe informacje o pliku",
                "type": "Plik"
            },
            {
                "time": current_time,
                "message": "Zakończono symulację analizy",
                "type": "Status"
            }
        ]    
    }


@app.post("/api/analyze")
async def analyze_file(file: UploadFile = File(...)):
    # Sprawdzamy, czy przesłany plik ma nazwę.
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Nie podano nazwy pliku."
        )

    # Akceptujemy wyłącznie nazwy z rozszerzeniem .exe.
    if not file.filename.lower().endswith(".exe"):
        raise HTTPException(
            status_code=400,
            detail="Dozwolone są wyłącznie pliki z rozszerzeniem .exe."
        )

    # Odczytujemy plik w pamięci, ale go nie uruchamiamy.
    content = await file.read()

    # Ograniczamy rozmiar do 20 MiB.
    max_size = 20 * 1024 * 1024

    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail="Plik przekracza limit 20 MiB."
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Przesłany plik jest pusty."
        )

    return {
        "status": "received",
        "message": "Plik odebrano. Nie został uruchomiony.",
        "filename": os.path.basename(file.filename),
        "size_bytes": len(content)
    }
