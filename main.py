import os
import json
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore

# === Inizializza Firebase ===
firebase_cred_json = os.getenv('FIREBASE_ADMIN_CRED')
if not firebase_cred_json:
    raise ValueError("Variabile FIREBASE_ADMIN_CRED non impostata")
cred = credentials.Certificate(json.loads(firebase_cred_json))
firebase_admin.initialize_app(cred)
db = firestore.client()

# === Flask App ===
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Pokemonitor backend attivo!"

@app.route('/register_token', methods=['POST'])
def register_token():
    data = request.json
    user_id = data.get('user_id')
    token = data.get('token')
    if not user_id or not token:
        return jsonify({'error': 'user_id e token sono richiesti'}), 400
    db.collection('users').document(user_id).set({'token': token}, merge=True)
    return jsonify({'message': 'Token registrato'})

@app.route('/add_url', methods=['POST'])
def add_url():
    data = request.json
    user_id = data.get('user_id')
    url = data.get('url')
    if not user_id or not url:
        return jsonify({'error': 'user_id e url sono richiesti'}), 400

    user_ref = db.collection('users').document(user_id)
    user_doc = user_ref.get().to_dict() or {}
    urls = user_doc.get('urls', [])
    if url not in urls:
        urls.append(url)
    user_ref.set({'urls': urls}, merge=True)
    return jsonify({'message': 'URL aggiunto'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)



