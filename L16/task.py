#!/usr/bin/env python3
"""
L16 - OKOeditor
Zadanie: Zmień klasyfikację raportu o mieście Skolwin na "zwierzęta"
"""

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AI_DEVS_4_API_KEY")
HUB_URL = "https://hub.ag3nts.org/verify"

def main():
    # ID raportu Skolwin z UI
    skolwin_incident_id = "380792b2c86d9c5be670b3bde48e187b"
    
    # Payload do zmiany klasyfikacji
    payload = {
        "apikey": API_KEY,
        "task": "okoeditor",
        "answer": {
            "action": "update",
            "page": "incydenty",
            "id": skolwin_incident_id,
            "title": "MOVE04 Obserwacja zwierząt nieopodal miasta Skolwin",
            "content": "Czujniki zarejestrowały szybko poruszające się zwierzęta w pobliżu Skolwina. Obiekty przemieszczały się nieregularnie wzdłuż rzeki. Analiza wykazała, że obserwowano bobry i inne zwierzęta wodne. Sygnały pochodziły z naturalnych źródeł aktywności zwierząt.",
        }
    }
    
    print("Zmiana klasyfikacji raportu Skolwin...")
    print("Z: pojazdy i ludzie")
    print("Na: zwierzęta")
    print()
    
    response = requests.post(HUB_URL, json=payload)
    result = response.json()
    
    print(f"Kod: {result.get('code')}")
    print(f"Status: {result.get('status')}")
    print(f"Wiadomość: {result.get('message')}")
    
    if result.get('code') == 110:
        print("\n✓ Raport Skolwin został zmieniony na zwierzęta")
    
    # Krok 2: Oznacz zadanie Skolwin jako wykonane
    print("\n" + "="*50)
    print("Oznaczanie zadania Skolwin jako wykonane...")
    
    payload2 = {
        "apikey": API_KEY,
        "task": "okoeditor",
        "answer": {
            "action": "update",
            "page": "zadania",
            "id": skolwin_incident_id,
            "content": "Widziano bobry i inne zwierzęta w okolicach Skolwina.",
            "done": "YES"
        }
    }
    
    response2 = requests.post(HUB_URL, json=payload2)
    result2 = response2.json()
    
    print(f"Kod: {result2.get('code')}")
    print(f"Status: {result2.get('status')}")
    print(f"Wiadomość: {result2.get('message')}")
    
    if result2.get('code') == 110:
        print("\n✓ Zadanie Skolwin oznaczone jako wykonane")
    
    # Krok 3: Dodaj raport o ruchu ludzi w Komarowie
    print("\n" + "="*50)
    print("Dodawanie raportu o ruchu ludzi w Komarowie...")
    
    komarowo_incident_id = "bcdfc393f811cc05d3a189c679f50659"  # PROB01
    
    payload3 = {
        "apikey": API_KEY,
        "task": "okoeditor",
        "answer": {
            "action": "update",
            "page": "incydenty",
            "id": komarowo_incident_id,
            "title": "MOVE01 Trudne do klasyfikacji ruchy nieopodal miasta Komarowo",
            "content": "Wykryto ruch ludzi i pojazdy w okolicach miasta Komarowo."
        }
    }
    
    response3 = requests.post(HUB_URL, json=payload3)
    result3 = response3.json()
    
    print(f"Kod: {result3.get('code')}")
    print(f"Status: {result3.get('status')}")
    print(f"Wiadomość: {result3.get('message')}")
    
    if result3.get('code') == 110:
        print("\n✓ Raport Komarowo dodany")
    
    # Krok 4: Finalizacja - wysłanie akcji "done"
    print("\n" + "="*50)
    print("Finalizacja zmian...")
    
    payload_done = {
        "apikey": API_KEY,
        "task": "okoeditor",
        "answer": {
            "action": "done"
        }
    }
    
    response_done = requests.post(HUB_URL, json=payload_done)
    result_done = response_done.json()
    
    print(f"Kod: {result_done.get('code')}")
    print(f"Status: {result_done.get('status')}")
    print(f"Wiadomość: {result_done.get('message')}")
    
    if "flag" in result_done:
        print(f"\n✓ FLAGA: {result_done.get('flag')}")
    
    return result_done

if __name__ == "__main__":
    main()
