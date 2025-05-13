import os
import json
import time
import threading
import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, messaging, db

# === SETUP FIREBASE ===
cred = credentials.Certificate('firebase_admin.json')  # Assicurati che sia nel progetto o usa variabili d’ambiente
firebase_admin.initialize_app(cred, {
    'databaseURL': os.getenv('FIREBASE_DB_URL')  # Inserisci questo su Render come variabile ambiente
})

# === FLASK APP ===
app = Flask(__name__)

# === MONITORING LOGIC ===
def extract_availability(html):
    soup = BeautifulSoup(html, 'html.parser')
    unavailable_texts = [
        "Non disponibile", "Currently unavailable",
        "Non è al momento disponibile", "We don't know when"
    ]
    return not any(text.lower() in soup.text.lower() for text in unavailable_texts)

def check_and_notify(user_id, url):
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if extract_availability(response.text):
            # Invia notifica se disponibile
            message = messaging.Message(
                notification=messaging.Notification(
                    title='Prodotto disponibile!',
                    body='Clicca per andare al checkout 🔥',
                ),
                data={"url": url},
                topic=user_id
            )
            messaging.send(message)
    except Exception as e:
        print(f"Errore su {url}: {e}")

def monitoring_loop():
    while True:
        users_ref = db.reference('users')
        users_data = users_ref.get()
        if users_data:
            for user_id, data in users_data.items():
                urls = data.get('urls', [])
                for url in urls:
                    check_and_notify(user_id, url)
        time.sleep(60)  # Intervallo tra i controlli

threading.Thread(target=monitoring_loop, daemon=True).start()

# === API ENDPOINTS ===

@app.route('/add_url', methods=['POST'])
def add_url():
    data = request.json
    user_id = data.get('user_id')
    url = data.get('url')
    if not user_id or not url:
        return jsonify({'error': 'user_id and url are required'}), 400

    user_ref = db.reference(f'users/{user_id}/urls')
    current_urls = user_ref.get() or []
    if url not in current_urls:
        current_urls.append(url)
    user_ref.set(current_urls)
    return jsonify({'message': 'URL aggiunto con successo'})

@app.route('/remove_url', methods=['POST'])
def remove_url():
    data = request.json
    user_id = data.get('user_id')
    url = data.get('url')
    if not user_id or not url:
        return jsonify({'error': 'user_id and url are required'}), 400

    user_ref = db.reference(f'users/{user_id}/urls')
    current_urls = user_ref.get() or []
    if url in current_urls:
        current_urls.remove(url)
        user_ref.set(current_urls)
    return jsonify({'message': 'URL rimosso con successo'})

@app.route('/')
def home():
    return 'Pokemonitor backend attivo!'

# === AVVIO ===
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
