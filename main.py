from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, messaging
import os
import json
import threading
import time

app = FastAPI()
watchlist = {}

# Firebase config
cred_json = os.getenv("FIREBASE_CREDENTIALS")
if not cred_json:
    raise Exception("Firebase credentials not found in environment variables")
cred = credentials.Certificate(json.loads(cred_json))
firebase_admin.initialize_app(cred)

class MonitorRequest(BaseModel):
    url: str
    token: str

def check_availability(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "it-IT,it;q=0.9"
        }
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        title = soup.select_one("#productTitle")
        out_of_stock = soup.select_one("#availability span")
        if title and out_of_stock and "disponibile" in out_of_stock.get_text().lower():
            return True
    except:
        pass
    return False

def monitor_url(url, token):
    while True:
        if check_availability(url):
            messaging.send(
                messaging.Message(
                    token=token,
                    notification=messaging.Notification(
                        title="Prodotto disponibile!",
                        body=f"{url}"
                    )
                )
            )
            watchlist.pop(url, None)
            break
        time.sleep(60)  # ogni 60 secondi

@app.post("/add")
async def add_to_watchlist(req: MonitorRequest, background_tasks: BackgroundTasks):
    if req.url in watchlist:
        raise HTTPException(status_code=400, detail="URL già monitorato")
    watchlist[req.url] = req.token
    background_tasks.add_task(monitor_url, req.url, req.token)
    return {"message": "Monitoraggio avviato"}
