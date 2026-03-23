# L11 - Evaluation (anomalie w odczytach sensorow)

## Cel zadania

Znalezienie anomalii w odczytach 10 000 sensorow elektrowni i przeslanie do Centrali
identyfikatorow plikow zawierajacych przeklamane dane lub niepoprawna notatke operatora.

- **Nazwa zadania:** `evaluation`
- **Dane:** `https://hub.ag3nts.org/dane/sensors.zip`

## Format danych (pojedynczy plik JSON)

```json
{
  "sensor_type": "temperature/voltage",
  "timestamp": 1774064280,
  "temperature_K": 612,
  "pressure_bar": 0,
  "water_level_meters": 0,
  "voltage_supply_v": 230.4,
  "humidity_percent": 0,
  "operator_notes": "Readings look stable and within expected range."
}
```

### Aktywne sensory i zakresy poprawnych wartosci

| Typ pomiaru       | Pole JSON            | Min    | Max    |
| ----------------- | -------------------- | ------ | ------ |
| `temperature`     | `temperature_K`      | 553    | 873    |
| `pressure`        | `pressure_bar`       | 60     | 160    |
| `water`           | `water_level_meters` | 5.0    | 15.0   |
| `voltage`         | `voltage_supply_v`   | 229.0  | 231.0  |
| `humidity`        | `humidity_percent`   | 40.0   | 80.0   |

Nieaktywne pola **musza** miec wartosc `0`. Czujnik zlozony (`voltage/temperature`)
aktywuje oba pola.

## Definicja anomalii

1. Wartosc pomiaru poza zakresem normy.
2. Czujnik zwraca dane, ktorych nie powinien zwracac (pole nieaktywne != 0).
3. Operator pisze, ze wszystko OK, a dane sa niepoprawne.
4. Operator pisze, ze sa bledy, a dane sa poprawne.

## Strategia rozwiazania

### Etap 1 — Pobranie i rozpakowywanie danych

- `GET https://hub.ag3nts.org/dane/sensors.zip`
- Rozpakowanie do `sensors/`

### Etap 2 — Detekcja programistyczna (bezplatna, szybka)

Dla kazdego pliku:
- Parsuj `sensor_type` (rozdzielony `/`)
- Sprawdz, czy aktywne pola sa w zakresie i nie sa zerem
- Sprawdz, czy nieaktywne pola sa rowne `0`
- Zebrane: anomalie typow 1 i 2  
- Te pliki trafiaja bezposrednio na liste wynikow — NIE potrzebuja sprawdzenia LLM

### Etap 3 — Klasyfikacja notatek operatorow przez LLM (koszt-efektywna)

Trafiaja tu tylko pliki, ktore PRZESZLY kontrole programistyczna:
- Zbierz unikalne `operator_notes` (wiele plikow moze dzielec identyczna notatke)
- Zgrupuj duze batche notatek w jeden prompt
- Zapytaj LLM: "ktore z ponizszych notatek wskazuja na problem/anomalie?"
- Minimalizuj output: model zwraca tylko indeksy/ID z problemem
- Cache: jesli zamiast 1000 identycznych notatek mamy 1 unikalny tekst — wywolujemy LLM raz

Anomalie z tego etapu: pliki, gdzie dane sa poprawne, ale notatka zglosila problem (typ 4).

> Uwaga: Pliki z anomaliami programistycznymi + notatka "OK" (typ 3) juz sa na liscie
> z etapu 2 — nie trzeba ich ponownie sprawdzac przez LLM (sa juz anomaliami z innego powodu).
> Jednak mozna tez je sprawdzac — typ 3 jest dodatkowym potwierdzeniem anomalii.

### Etap 4 — Wyslanie odpowiedzi

```json
POST https://hub.ag3nts.org/verify
{
  "apikey": "...",
  "task": "evaluation",
  "answer": {
    "recheck": ["0001", "0042", "1337"]
  }
}
```

## Optymalizacja kosztow LLM

1. **Etap programistyczny za darmo** — typy 1 i 2 nie wymagaja LLM.
2. **Deduplikacja notatek** — jesli 500 plikow ma ta sama notatke, wywolanie LLM tylko raz.
3. **Batching** — wiele notatek w jednym prompcie.
4. **Minimalizacja output** — model zwraca tylko indeksy anomalii, nie cale notatki.
5. **Tani model** — np. `google/gemini-flash-1.5` lub `openai/gpt-4o-mini`.

## Pliki

| Plik               | Opis                                            |
| ------------------ | ----------------------------------------------- |
| `task.py`          | Gowny solver — detekcja, LLM, submit            |
| `ui_server.py`     | Lokalny serwer HTTP do przegladu wynikow        |
| `ui.html`          | Frontend do inspekcji anomalii                  |
| `sensors/`         | Wypakowane dane z sensors.zip (generowane)      |
| `anomalies.json`   | Lista wykrytych anomalii (generowane)           |
| `verification_result.json` | Odpowiedz z Centrali (generowane)       |

## Bonus – ukryta flaga

### Krok po kroku

1. **Wyslan ID z tytulu bonusu** do `/verify`:
   ```
   {"recheck": ["9132","1522","2306","1048","2119"]}
   ```
   Hub zwraca: `https://hub.ag3nts.org/dane/decode.txt`

2. **decode.txt** — skrypt AWK:
   ```awk
   BEGIN { FS = "\"" }
   NR==3 { a = substr($2, 1, 4) }
   NR==9 { s = $4; b = substr(s,44,1) substr(s,60,1) substr(s,66,1) substr(s,74,1) substr(s,76,1) }
   END   { printf "{FLG:%s%s}\n", toupper(a), toupper(b) }
   ```

3. **Podejrzany JSON** — plik `2137.json`:
   - Notatka: `"The report looks completely normal. I will go to check status of all other devices."`
   - Unikalna struktura wsrod 9999 plikow (nie konczy sie szablonowym zwrotem)
   - Dane: prawidlowe (nie jest w liscie anomalii)

4. **Dekodowanie** (AWK):
   - `a` = `substr("timestamp",1,4)` = `TIME`
   - `b` = znaki na pozycjach 44,60,66,74,76 notatki: `g`,`u`,`a`,`r`,`d` → `GUARD`
   - **Flaga: `{FLG:TIMEGUARD}`**

```python
# bonus_solver.py
python L11/bonus_solver.py
```

## Zweryfikowany wynik

- **9 999** plikow JSON przeskanowanych
- **46** anomalii programistycznych (wartosci poza zakresem / nieaktywne pola != 0)
- **6** anomalii z notatek (dane OK, operator zglasza problem)
- **52** anomalie lacznie wyslane do Centrali
- Odpowiedz: `{"code": 0, "message": "{FLG:BUGGYSYSTEM}"}`

## Uruchomienie

```powershell
# Aktywuj venv
& .venv\Scripts\Activate.ps1

# Uruchom pelny pipeline (pobierz, analizuj, wyslij)
python L11/task.py

# Opcjonalnie — UI do inspekcji
python L11/ui_server.py
# Otworz http://localhost:8080
```
