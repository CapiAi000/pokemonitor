import os
import json
import time
import requests
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from bs4 import BeautifulSoup

# === Inizializza Firebase ===
firebase_cred_json = os.getenv('FIREBASE_ADMIN_CRED')
if not firebase_cred_json:
    raise ValueError("Variabile FIREBASE_ADMIN_CRED non impostata")
cred = credentials.Certificate(json.loads(firebase_cred_json))
firebase_admin.initialize_app(cred)
db = firestore.client()

def is_product_available(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        availability = soup.select_one('#availability')
        if availability and ('disponibile' in availability.text.lower() or 'in stock' in availability.text.lower()):
            return True
    except Exception as e:
        print(f"❌ Errore controllo prodotto: {e}")
    return False

def send_notification(token, title, body, url):
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=token,
        data={"link": url}
    )
    try:
        response = messaging.send(message)
        print(f"✅ Notifica inviata: {response}")
    except Exception as e:
        print(f"❌ Errore invio notifica: {e}")

def monitor():
    while True:
        print("🔁 Controllo disponibilità prodotti...")
        users = db.collection('users').stream()
        for user in users:
            user_id = user.id
            data = user.to_dict()
            token = data.get('token')
            urls = data.get('urls', [])
            notified = data.get('notified', [])
            for url in urls:
                if url in notified:
                    continue
                if is_product_available(url):
                    print(f"🛒 Disponibile → {url}")
                    send_notification(token, "Prodotto disponibile!", "Tocca per acquistare.", url)
                    notified.append(url)
            db.collection('users').document(user_id).set({'notified': notified}, merge=True)
        time.sleep(60)

if __name__ == "__main__":
    monitor()
