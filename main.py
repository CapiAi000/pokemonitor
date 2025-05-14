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

# === Funzione per verificare disponibilità prodotto ===
def is_product_available(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        availability = soup.select_one('#availability')
        if availability and ('disponibile' in availability.text.lower() or 'in stock' in availability.text.lower()):
            return True
    except Exception as e:
        print(f"❌ Errore durante il controllo del prodotto: {e}")
    return False

# === Funzione per inviare notifica push ===
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

# === Funzione di monitoraggio ===
def monitor():
    while True:
        print("🔁 Controllo prodotti in corso...")
        users = db.collection('users').stream()

        for user in users:
            user_id = user.id
            user_data = user.to_dict()
            token = user_data.get('token')
            urls = user_data.get('urls', [])
            notified = user_data.get('notified', [])

            for url in urls:
                if url in notified:
                    continue
                if is_product_available(url):
                    print(f"🛒 Prodotto disponibile per {user_id}: {url}")
                    send_notification(token, "Prodotto disponibile!", "Tocca per acquistare ora.", url)
                    notified.append(url)

            db.collection('users').document(user_id).set({'notified': notified}, merge=True)

        time.sleep(60)

# === Endpoint per registrare token FCM ===
@app.route('/register_token', methods=['POST'])
def register_token():
    data = request.json
    user_id = data.get('user_id')
    token = data.get('token')

    if not user_id or not token:
        return jsonify({'error': 'user_id e token sono richiesti'}), 400

    db.collection('users').document(user_id).set({'token': token}, merge=True)
    print(f"📥 Token registrato per {user_id}")
    return jsonify({'message': 'Token registrato con successo'})

# === Endpoint per aggiungere URL da monitorare ===
@app.route('/add_url', methods=['POST'])
def add_url():
    data = request.json
    user_id = data.get('user_id')
    url = data.get('url')

    if not user_id or not url:
        return jsonify({'error': 'user_id e url sono richiesti'}), 400

    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get()
    user_data = user_doc.to_dict() or {}

    urls = user_data.get('urls', [])
    if url not in urls:
        urls.append(url)

    user_ref.set({'urls': urls}, merge=True)
    print(f"🔗 URL aggiunto per {user_id}: {url}")
    return jsonify({'message': 'URL aggiunto con successo'})

# === Endpoint base con visualizzazione HTML semplice ===
@app.route('/')
def home():
    users = db.collection('users').stream()
    html = "<h1>✅ Pokemonitor backend attivo!</h1><h2>Utenti registrati:</h2><ul>"
    for user in users:
        data = user.to_dict()
        html += f"<li><strong>{user.id}</strong><br>Token: {data.get('token', '-')[:20]}...<br>Link: <ul>"
        for url in data.get('urls', []):
            html += f"<li>{url}</li>"
        html += "</ul></li>"
    html += "</ul>"
    return html

# === Avvio thread di monitoraggio ===
if __name__ == '__main__':
    if os.environ.get('RUN_MONITOR') == '1':  # lancia solo se RUN_MONITOR è settata
        threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)



