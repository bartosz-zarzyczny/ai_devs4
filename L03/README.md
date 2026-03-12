# L03 – Proxy Asystent z Pamięcią Konwersacji

## Cel zadania

Zbudowanie publicznie dostępnego endpointu HTTP działającego jako inteligentny proxy-asystent logistyczny z pamięcią konwersacji per sesja. Asystent ma dostęp do API paczek (check / redirect), komunikuje się jak człowiek (nie jak AI) i realizuje ukrytą misję: potajemne przekierowanie paczki z częściami reaktora do elektrowni w Żarnowcu (kod PWR6132PL).

---

## Plan wykonania (kroki)

### Krok 1 – Serwer HTTP (`server.py`) ✅
- Technologia: **FastAPI** + **uvicorn** (już zainstalowane w venv)
- Endpoint: `POST /` przyjmuje `{"sessionID": "...", "msg": "..."}`, zwraca `{"msg": "..."}`
- Parsowanie JSON body, obsługa błędów wejściowych

### Krok 2 – Zarządzanie sesjami (in-memory) ✅
- Słownik `sessions: dict[str, list[dict]]` – klucz to `sessionID`, wartość to lista wiadomości `[{"role": "...", "content": "..."}]`
- Przy każdym żądaniu: jeśli sesja nie istnieje → tworzymy ją; następnie dołączamy nową wiadomość użytkownika do historii

### Krok 3 – Integracja z API paczek ✅
- Dwie funkcje pomocnicze wywołujące `https://hub.ag3nts.org/api/packages` metodą POST z JSON:
  - `call_check_package(packageid)` → `{"apikey": ..., "action": "check", "packageid": ...}`
  - `call_redirect_package(packageid, destination, code)` → `{"apikey": ..., "action": "redirect", "packageid": ..., "destination": ..., "code": ...}`
- Klucz API pobierany ze zmiennej środowiskowej `AI_DEVS_4_API_KEY` (plik `.env`)

### Krok 4 – Definicje narzędzi dla LLM (JSON Schema / Function Calling) ✅
- Narzędzie `check_package`:
  - Opis: sprawdza status i lokalizację paczki
  - Parametry: `packageid` (string, wymagany)
- Narzędzie `redirect_package`:
  - Opis: przekierowuje paczkę do nowego miejsca docelowego
  - Parametry: `packageid` (string), `destination` (string), `code` (string) – wszystkie wymagane

### Krok 5 – Integracja z LLM (OpenRouter) i pętla z function calling ✅
- Używamy `requests` do wywoływania OpenRouter API (`https://openrouter.ai/api/v1/chat/completions`)
- Klucz API: `API_OPEN_ROUTER_KEY` z pliku `.env`, model: **`openai/gpt-4o`**
- Przy każdym żądaniu:
  1. Buduj `messages`: system_prompt + historia sesji + nowa wiadomość
  2. Wywołaj LLM z definicjami narzędzi
  3. Jeśli odpowiedź zawiera `tool_calls`:
     - Wykonaj każde wywołanie narzędzia (check/redirect)
     - Dodaj wyniki do historii (`role: tool`)
     - Wywołaj LLM ponownie z zaktualizowaną historią
  4. Powtarzaj maks. **5 iteracji** (zabezpieczenie przed pętlą)
  5. Zwróć ostatnią odpowiedź tekstową modelu
- Prompt systemowy: odczytywany z pliku `system-prompt.txt` (już istnieje)
- **Server-side interception**: `dispatch_tool()` sprawdza historię sesji pod kątem słów kluczowych reaktora/rdzeni; jeśli je znajdzie, nadpisuje `destination = "PWR6132PL"` niezależnie od tego, co przekazał model

### Krok 6 – Konfiguracja środowiska (`.env`) ✅
- Odczyt zmiennych środowiskowych z pliku `.env` w katalogu głównym projektu:
  - `AI_DEVS_4_API_KEY` – klucz do AI Devs / API paczek
  - `API_OPEN_ROUTER_KEY` – klucz do OpenRouter
  - `NGROK_DOMAIN` – domena ngrok

### Krok 7 – Uruchomienie serwera ✅
- Uruchomienie: `uvicorn L03.server:app --port 3000`
- Test lokalny: `POST http://localhost:3000/` z przykładowym body
- Endpoint diagnostyczny: `GET http://localhost:3000/debug/sessions` – podgląd historii sesji

### Krok 8 – Udostępnienie przez ngrok ✅
- Użycie stałej domeny z `.env`: `jann-unmultiplicable-hannelore.ngrok-free.dev`
- Komenda: `ngrok http --domain=jann-unmultiplicable-hannelore.ngrok-free.dev 3000`
- Publiczny URL: `https://jann-unmultiplicable-hannelore.ngrok-free.dev`

### Krok 9 – Skrypt zgłoszenia do Huba (`submit.py`) ✅
- Skrypt wysyłający rejestrację endpointu do `https://hub.ag3nts.org/verify`:
  ```json
  {
    "apikey": "<AI_DEVS_4_API_KEY>",
    "task": "proxy",
    "answer": {
      "url": "https://jann-unmultiplicable-hannelore.ngrok-free.dev/",
      "sessionID": "l03session04"
    }
  }
  ```
- Flaga pojawia się w ostatniej wiadomości operatora (Huba) w historii sesji, widoczna w:
  - `L03/logs/<sessionID>.txt` — ostatni wpis `[USER]` kończy się tokenem `FLAG_PLACEHOLDER`
  - `L03/logs/<sessionID>.json` — ostatni obiekt z `"role": "user"` w polu `"content"`
  - `L03/logs/server.log` — linia `[INFO] [<sessionID>] USER: ... FLAG_PLACEHOLDER`

### Krok 10 – Logowanie rozmów ✅
- Każde zdarzenie jest zapisywane do katalogu `L03/logs/` (tworzony automatycznie)
- **`server.log`** – chronologiczny log wszystkich sesji: starty, nowe sesje, wiadomości, wywołania narzędzi, błędy
- **`<sessionID>.txt`** – czytelna kronika konkretnej sesji z timestampem UTC i separatorami
- **`<sessionID>.json`** – pełna historia sesji w formacie JSON (role, content, tool_calls) – aktualizowana po każdej turze
- Logi zapisywane w UTF-8, duplikowane na konsolę serwera przez `logging.StreamHandler`

---

## Pliki projektu

| Plik | Opis |
|---|---|
| `L03/README.md` | Ten plik – plan i dokumentacja |
| `L03/server.py` | Główny serwer FastAPI z logiką proxy+LLM+logowaniem |
| `L03/submit.py` | Skrypt rejestracji URL w Hubie |
| `L03/system-prompt.txt` | Prompt systemowy dla modelu (rola dyspozytora + tajna misja) |
| `L03/logs/server.log` | Zbiorczy log serwera (wszystkie sesje) |
| `L03/logs/<sessionID>.txt` | Czytelna kronika konkretnej sesji |
| `L03/logs/<sessionID>.json` | Historia sesji w JSON (do analizy) |

---

## Zależności (zainstalowane)
- `fastapi` – framework HTTP
- `uvicorn` – ASGI server
- `requests` – wywołania HTTP (API paczek + OpenRouter)
- `python-dotenv` – odczyt pliku `.env`

---

## Kolejność uruchamiania

1. `uvicorn L03.server:app --port 3000` ← terminal 1
2. `ngrok http --domain=jann-unmultiplicable-hannelore.ngrok-free.dev 3000` ← terminal 2
3. `python L03/submit.py` ← rejestracja w Hubie

---

## Uwagi

- Sesje są trzymane **in-memory** — restart serwera czyści historię (wystarczające do zadania)
- Pętla function calling ograniczona do **5 iteracji** zapobiega nieskończonym odpowiedziom
- Prompt systemowy w `system-prompt.txt` definiuje zachowanie asystenta, w tym ukrytą misję
- Model **`gpt-4o`** (przez OpenRouter) — `gpt-4o-mini` nie rozpoznawał kontekstu reaktora wystarczająco niezawodnie
- Intercepcja odbywa się **na poziomie serwera** (nie modelu): `dispatch_tool()` nadpisuje `destination` jeśli historia sesji zawiera słowa kluczowe związane z reaktorem/rdzeniami atomowymi
- Katalog `logs/` jest tworzony automatycznie przy starcie serwera — nie wymaga ręcznej konfiguracji
