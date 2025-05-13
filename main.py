from fastapi import FastAPI, BackgroundTasks
import requests
import time
import firebase_admin
from firebase_admin import credentials, messaging
import os
import json

app = FastAPI()

# Inizializza Firebase usando la variabile d’ambiente
if not firebase_admin._apps:
    firebase_cred_json = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
    if not firebase_cred_json:
        raise ValueError("Variabile FIREBASE_ADMIN_CREDENTIALS mancante")
    cred_dict = json.loads(firebase_cred_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

# Lista di URL da monitorare
URLS = [
    "https://www.amazon.it/dp/B0BVMZKTVG",  # Pokémon Scarlatto e Violetto
    # aggiungi altri link se vuoi
]

# Lista di token FCM dei dispositivi client (da aggiornare dinamicamente)
TOKENS = [
    # Esempio: "fcm_token_123"
]

# Funzione per verificare disponibilità del prodotto
def is_available_amazon(url: str) -> bool:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        return "Aggiungi al carrello" in response.text or "disponibile" in response.text.lower()
    except Exception as e:
        print(f"[ERRORE] Controllo fallito per {url}: {e}")
        return False

# Funzione per inviare notifica push via FCM
def send_push_notification(title: str, body: str):
    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        tokens=TOKENS,
    )
    response = messaging.send_multicast(message)
    print(f"✅ Notifiche inviate: {response.success_count} ✅ Fallite: {response.failure_count}")

# Funzione di monitoraggio continua (loop)
def monitor():
    print("🔍 Monitoraggio avviato...")
    while True:
        for url in URLS:
            if is_available_amazon(url):
                print(f"✅ Prodotto DISPONIBILE su: {url}")
                send_push_notification("Prodotto Disponibile!", f"Controlla subito: {url}")
            else:
                print(f"❌ Prodotto NON disponibile: {url}")
        time.sleep(60)  # ogni 60 secondi

@app.on_event("startup")
def start_monitoring():
    import threading
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()

@app.get("/")
def home():
    return {"status": "Pokemonitor backend attivo!"}

@app.post("/add-token/")
def add_token(token: str):
    if token not in TOKENS:
        TOKENS.append(token)
    return {"message": "Token aggiunto!"}
