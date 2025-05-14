import os
import json
import requests
import threading
import time
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from bs4 import BeautifulSoup

# === Inizializza Firebase da variabile d'ambiente ===
firebase_cred_json = os.getenv('FIREBASE_ADMIN_CRED')
if not firebase_cred_json:
    raise ValueError("Variabile d'ambiente FIREBASE_ADMIN_CRED non impostata")
cred = credentials.Certificate(json.loads(firebase_cred_json))
firebase_admin.initialize_app(cred)

# === Inizializza Firestore ===
db = firestore.client()

# === Config Flask ===
app = Flask(__name__)

# === Cache per URL già controllati ===
last_checked = {}

# === Verifica disponibilità prodotto ===
def is_product_available(url):
    current_time = time.time()
    # Evita di fare la richiesta se l'URL è stato controllato recentemente
    if url in last_checked and current_time - last_checked[url] < 180:
        return False

    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        availability = soup.select_one('#availability')
        if availability:
            text = availability.text.lower()
            if 'disponibile' in text or 'in stock' in text:
                last_checked[url] = current_time  # Aggiorna il timestamp
                return True
    except Exception as e:
        print(f"❌ Errore controllo prodotto: {e}")
    
    last_checked[url] = current_time  # Anche in caso di errore, aggiorna il timestamp
    return False

# === Invia notifica push ===
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

# === Monitoraggio prodotti ===
def monitor():
    while True:
        print("🔁 Monitoraggio attivo...")
        try:
            users = db.collection('users').stream()
            for user in users:
                user_id = user.id
                data = user.to_dict()
                token = data.get('token')
                urls = data.get('urls', [])[:3]  # Limita a max 3 URL
                notified = set(data.get('notified', []))

                updated = False
                for url in urls:
                    if url in notified:
                        continue
                    if is_product_available(url):
                        print(f"🛒 Disponibile: {url}")
                        send_notification(token, "Prodotto disponibile!", "Tocca per acquistare ora.", url)
                        notified.add(url)
                        updated = True

                if updated:
                    db.collection('users').document(user_id).set({'notified': list(notified)}, merge=True)

            time.sleep(180)  # Limita la frequenza di controllo (3 minuti)
        except Exception as e:
            print(f"❌ Errore nel monitoraggio: {e}")
            time.sleep(180)  # Riprovare dopo un po'

# === Endpoint per registrare token FCM ===
@app.route('/register_token', methods=['POST'])
def register_token():
    data = request.json
    user_id = data.get('user_id')
    token = data.get('token')
    if not user_id or not token:
        return jsonify({'error': 'user_id e token richiesti'}), 400
    db.collection('users').document(user_id).set({'token': token}, merge=True)
    return jsonify({'message': 'Token registrato con successo'})

# === Endpoint per aggiungere URL ===
@app.route('/add_url', methods=['POST'])
def add_url():
    data = request.json
    user_id = data.get('user_id')
    url = data.get('url')
    if not user_id or not url:
        return jsonify({'error': 'user_id e url richiesti'}), 400

    ref = db.collection('users').document(user_id)
    doc = ref.get()
    info = doc.to_dict() or {}
    urls = info.get('urls', [])
    if url not in urls:
        urls.append(url)
        ref.set({'urls': urls}, merge=True)
    return jsonify({'message': 'URL aggiunto con successo'})

# === Avvio monitor in background ===
if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)



