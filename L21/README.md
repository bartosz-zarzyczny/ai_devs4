# L21 — radiomonitoring

## Cel

Przechwycić i przeanalizować materiały z radiowego nasłuchu, a następnie przesłać do Centrali końcowy raport zawierający dane o mieście nazywanym "Syjon".

Odpowiedź wysyłamy na: `POST https://hub.ag3nts.org/verify`

## Wynik

```
FLAG: {FLG:XXXXXXXXXX}
```

## Bonus

Bonus prowadzi przez ukryta strone `https://hub.ag3nts.org/deeper`, do ktorej naprowadza sygnal Morse'a:

```text
MUSISZ SPRAWDZIC / DEEPER
```

Automatyczny solver bonusu:
- znajduje wskazowke w transkrypcjach Morse'a,
- otwiera `/deeper`,
- brute-force'uje haslo znak po znaku przez `/encoder_deeper`, korzystajac z pola `correct`,
- zapisuje wynik do `bonus_result.json`.

Wynik bonusu:

```json
{
  "password": "DIWBU",
  "encodedTarget": "FLAGA",
  "flag": "{FLG:XXXXXXXXXX}"
}
```

Poprawna odpowiedź:
```json
{
  "action": "transmit",
  "cityName": "Skarszewy",
  "cityArea": "10.73",
  "warehousesCount": 11,
  "phoneNumber": "644122092"
}
```

Kluczowe wnioski z danych:
- **Syjon = Skarszewy** — signal_011 wprost opisuje Skarszewy: bydło własne, nad rzeką, oczyszczają wodę, trudni w handlu
- **cityArea** z signal_031.json: `occupiedArea: 10.7284` → zaokrąglone do "10.73"
- **phoneNumber** z signal_001.png (zdjęcie karteczki): "Jacek Kramer... 644-122-092"
- **warehousesCount** z signal_009.mp3 (audio Skarszewy): "Planujemy na wiosnę wybudować 11 magazyn" (Whisper base/small myli "jedenaście" z "12" — poprawna wartość to 11)

Końcowy payload:
```json
{
  "apikey": "...",
  "task": "radiomonitoring",
  "answer": {
    "action": "transmit",
    "cityName": "NazwaMiasta",
    "cityArea": "12.34",
    "warehousesCount": 321,
    "phoneNumber": "123456789"
  }
}
```

---

## Plan implementacji

### Phase 0 — Bootstrap L21

- Folder `L21/` (pusty — nic do re-użycia)
- Tworzone pliki: `task.py`, `README.md`, `ui_server.py`, `ui.html`
- UI server sluzy do inspekcji sygnalow, uruchamiania glownego pipeline oraz wyszukiwania bonusu

---

### Phase 1 — Sesja + pętla nasłuchu

1. `start_session()` — POST `{"action": "start"}`, loguje odpowiedź
2. `listen_loop()` — POST `{"action": "listen"}` w pętli:
   - Kontynuuj dopóki `response["code"] == 100`
   - Przerwij przy innym kodzie lub gdy `message` zawiera "no more" / "enough data"
   - Każdą surową odpowiedź dopisuj do `L21/session_raw.jsonl` (sesja nie musi być powtarzana!)
   - Sleep ~1 s między wywołaniami
   - Limit bezpieczeństwa: 200 iteracji

---

### Phase 2 — Router (programistyczny, zero kosztu LLM)

**Pobieranie, zapisywanie i wykrywanie typu danych odbywa się wyłącznie kodem Pythona — bez udziału modelu językowego.**

Każdy odebrany sygnał jest:
1. **Pobierany** przez `requests` i zapisywany do `L21/dane/` (surowe bajty lub JSON) zanim cokolwiek trafi do LLM
2. **Klasyfikowany** programistycznie na podstawie kluczy w odpowiedzi JSON i wartości pola `meta`
3. Dopiero po klasyfikacji rozsyłany dalej

Dla każdej odpowiedzi z pętli:

| Warunek | Akcja (Python) |
|---|---|
| `transcription` present | zbierz string → `gathered_texts[]` |
| `attachment` + `meta == "application/json"` | `base64.b64decode()` → `json.loads()` → zapisz do `L21/dane/` → `gathered_json[]` |
| `attachment` + `meta` zaczyna się od `text/` | `base64.b64decode()` → `.decode("utf-8")` → zapisz do `L21/dane/` → `gathered_texts[]` |
| `attachment` + `meta` zaczyna się od `image/` | `base64.b64decode()` → zapisz plik `L21/dane/img_N.ext` → dodaj ścieżkę do `pending_images[]` |
| `attachment` + `meta` zaczyna się od `audio/` | `base64.b64decode()` → zapisz plik `L21/dane/audio_N.*`, **pomiń LLM** (zbyt drogi) |
| brak obu kluczy | szum radiowy — tylko log, pomiń |

---

### Phase 3 — Ekstrakcja przez LLM

5. Wszystkie `gathered_texts[]` + zseriializowane `gathered_json[]` → **jeden prompt** do **`openai/gpt-oss-120b:free`** przez OpenRouter  
   Wymagany JSON odpowiedzi:
   ```json
   {
     "cityName": "...",
     "cityArea": 12.34,
     "warehousesCount": 321,
     "phoneNumber": "..."
   }
   ```
  6. Jeśli `pending_images[]` niepusty → dodatkowe wywołanie `google/gemma-3-27b-it:free` (vision) per obraz; scalaj znalezione pola
7. Formatowanie `cityArea`: `f"{round(float(v), 2):.2f}"` — gwarantuje dokładnie 2 miejsca po przecinku i prawdziwe zaokrąglenie

  ### Phase 5 — Bonus /deeper

  10. Zlokalizuj wskazowke Morse'a: `MUSISZ SPRAWDZIC / DEEPER`
  11. Otworz ukryta strone `https://hub.ag3nts.org/deeper`
  12. Odpytuj `POST https://hub.ag3nts.org/encoder_deeper` z kolejnymi prefiksami hasla
  13. Dla kazdej pozycji wybieraj litere, dla ktorej backend zwraca index w polu `correct`
  14. Zapisz wynik do `bonus_result.json`

---

### Phase 4 — Wysłanie raportu końcowego

8. POST `{"action": "transmit", "cityName": …, "cityArea": "12.34", "warehousesCount": N, "phoneNumber": "…"}`
9. Zapisz odpowiedź → `L21/verification_result.json`

---

## Uruchamianie

```powershell
# Pierwsza sesja (zbiera dane, przetwarza, wysyla raport)
python L21/task.py

# Replay z zapisanej sesji (bez nowych wywolan API)
python L21/task.py --replay

# Bonus: ukryta strona /deeper
python L21/task.py --bonus

# UI — przegladarka do inspekcji sygnalow i wynikow
python L21/ui_server.py
# otworz http://localhost:8082/ui.html

# opcjonalnie wymus konkretny port
$env:PORT = "8083"
python L21/ui_server.py
```

W UI dostepne sa trzy akcje:
- `Replay (z pliku)`
- `Nowa sesja (live)`
- `Szukaj bonusu`

Jesli `8082` jest zajety, serwer automatycznie przejdzie na kolejny wolny port i wypisze docelowy adres w konsoli.

Pliki wyjsciowe:

| Plik | Zawartosc |
|---|---|
| `session_raw.jsonl` | surowe odpowiedzi z petli nasluchowej |
| `dane/` | zdekodowane pliki (obrazy, audio, JSON, CSV, XML) |
| `dane/64/` | surowe dane base64 |
| `verification_result.json` | odpowiedz huba po `transmit` |
| `bonus_result.json` | wynik bonusu z `/deeper` |

---

## Zaleznosci

Brak nowych pakietow — wystarczaja istniejace z `requirements.txt`:
`requests`, `python-dotenv`, `Pillow`

---

## Uwagi implementacyjne

- **Sygnał końca danych**: kod inny niż 100 lub słowo kluczowe w `message`. Sprawdzić przy pierwszym uruchomieniu.
- **warehousesCount**: wysyłany jako `int`.
- **Audio**: pomijane domyślnie; jeśli 4 pola nie dadzą się ustalić bez audio, można użyć lokalnego STT bez żadnego zewnętrznego API:
  - `openai-whisper` — `pip install openai-whisper` — uruchamia Whisper lokalnie (CPU/GPU), model `base` (~150 MB) wystarcza dla języka polskiego
  - `faster-whisper` — `pip install faster-whisper` — szybsza wersja na bazie CTranslate2, mniejsze zużycie RAM
  - Przykład użycia:
    ```python
    import whisper
    model = whisper.load_model("base")
    result = model.transcribe("L21/dane/signal_009.mp3", language="pl")
    print(result["text"])
    ```
  - Alternatywnie: bezpośrednie API OpenAI (`POST https://api.openai.com/v1/audio/transcriptions`) za $0.006/minutę — wymaga klucza OpenAI (nie OpenRouter)
- **Szyfry i kodowanie**: sygnały mogą być zakodowane alfabetem Morse'a lub innym szyfrem (np. ROT13, Base64 w treści tekstowej, kod NATO). W takim przypadku konieczne jest dodanie etapu dekodowania przed przekazaniem danych do LLM — albo programistycznie (alphabet Morse'a, Base64 w tekście), albo przez prompt dla modelu z informacją o użytym szyfrze.
- **Tryb replay**: odczytuje `session_raw.jsonl` zamiast ponownie startować sesję — przydatne przy iterowaniu promptu bez dodatkowych kosztów API.
