from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, messaging
import os
import uvicorn
# ==== CONFIG ====
# Firebase credentials
FIREBASE_CREDENTIALS_PATH = "firebase-admin.json"

# CORS Origins (es. app React/Vue/Flutter)
origins = ["*"]  # In produzione è meglio specificare i domini

# ==== APP SETUP ====
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==== FIREBASE INIT ====
if not firebase_admin._apps:
    if os.path.exists(FIREBASE_CREDENTIALS_PATH):
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
    else:
        raise FileNotFoundError("Il file firebase-admin.json non è stato trovato")

# ==== SCRAPING FUNCTION ====
def check_availability(url: str) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        availability = soup.select_one("#availability")
        if availability and "disponibile" in availability.text.lower():
            return True
    except Exception as e:
        print(f"Errore nello scraping: {e}")
    return False

# ==== FIREBASE NOTIFICATION ====
def send_notification(token: str, title: str, body: str) -> None:
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token,
        )
        response = messaging.send(message)
        print(f"Notifica inviata: {response}")
    except Exception as e:
        print(f"Errore nell'invio della notifica: {e}")

# ==== API ROUTES ====
@app.get("/")
async def root():
    return {"status": "Pokemonitor API Online"}

@app.post("/check/")
async def check_item(url: str, token: str):
    if not url or not token:
        raise HTTPException(status_code=400, detail="URL e token sono obbligatori")
    available = check_availability(url)
    if available:
        send_notification(token, "Disponibile!", f"Il prodotto è tornato disponibile:\n{url}")
    return {"url": url, "disponibile": available}

