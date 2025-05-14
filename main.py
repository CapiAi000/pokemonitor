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

def is_product_available(url):
    current_time = time.time()
    if url in last_checked and current_time - last_checked[url] < 180:
        return False

    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        availability = soup.select_one('#availability')
        if availability and ('disponibile' in availability.text.lower() or 'in stock' in availability.text.lower()):
            last_checked[url] = current_time
            return True
    except Exception as e:
        print(f"❌ Errore controllo prodotto: {e}")

    last_checked[url] = current_time
    return False

def send_notification(token, title, body, url):
    msg = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=token,
        data={"link": url}
    )
    try:
        res = messaging.send(msg)
        print(f"✅ Notifica inviata: {res}")
    except Exception as e:
        print(f"❌ Errore invio notifica: {e}")

def monitor():
    while True:
        print("🔁 Monitoraggio prodotti...")
        try:
            for user in db.collection('users').stream():
                data = user.to_dict()
                token = data.get('token')
                urls = data.get('urls', [])[:3]
                notified = set(data.get('notified', []))
                updated = False

                for url in urls:
                    if url in notified: continue
                    if is_product_available(url):
                        print(f"🛒 Disponibile: {url}")
                        send_notification(token, "Prodotto disponibile!", "Tocca per acquistare ora.", url)
                        notified.add(url)
                        updated = True

                if updated:
                    db.collection('users').document(user.id).set({'notified': list(notified)}, merge=True)

            time.sleep(180)
        except Exception as e:
            print(f"❌ Errore monitoraggio: {e}")
            time.sleep(180)

@app.route('/register_token', methods=['POST'])
def register_token():
    try:
        data = request.get_json()
        uid = data.get('user_id')
        token = data.get('token')
        if not uid or not token:
            return jsonify({'error': 'user_id e token richiesti'}), 400
        db.collection('users').document(uid).set({'token': token}, merge=True)
        return jsonify({'message': 'Token registrato'})
    except Exception as e:
        print(f"❌ Errore register_token: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/add_url', methods=['POST'])
def add_url():
    try:
        data = request.get_json()
        uid = data.get('user_id')
        url = data.get('url')
        if not uid or not url:
            return jsonify({'error': 'user_id e url richiesti'}), 400

        ref = db.collection('users').document(uid)
        doc = ref.get()
        if not doc.exists:
            return jsonify({'error': 'Utente non trovato'}), 404

        info = doc.to_dict() or {}
        urls = info.get('urls', [])
        if url not in urls:
            urls.append(url)
            ref.set({'urls': urls}, merge=True)

        return jsonify({'message': 'URL aggiunto'})
    except Exception as e:
        print(f"❌ Errore add_url: {e}")
        return jsonify({'error': 'Server error'}), 500

if __name__ == '__main__':
    threading.Thread(target=monitor, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Server avviato su 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)




