from fastapi import FastAPI
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
