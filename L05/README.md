# Zadanie: `railway` (instrukcja krok po kroku)

Opis zadania:

Musisz aktywować trasę kolejową o nazwie `X-01` za pomocą API, do którego nie mamy dokumentacji. API jest samo-dokumentujące — zaczynamy od akcji `help`, która zwraca opis wszystkich dostępnych akcji, parametrów i wymaganej kolejności wywołań. Komunikacja odbywa się przez ten sam endpoint co poprzednie zadania: wszystkie żądania to `POST` na `https://hub.ag3nts.org/verify`, body jako raw JSON.

Przykład wywołania akcji `help`:

```json
{
  "apikey": "tutaj-twoj-klucz",
  "task": "railway",
  "answer": {
	"action": "help"
  }
}
```

Uwagi o API:

- API jest celowo przeciążone i często zwraca błędy `503`. To symulacja — kod powinien automatycznie retry'ować z backoffem.
- Nagłówki HTTP odpowiedzi informują o limitach — szukaj nagłówków typu `Retry-After`, `X-RateLimit-Reset` lub podobnych i respektuj czas resetu.
- Flaga końcowa pojawia się w treści odpowiedzi w formacie `{FLG:...}` — to sygnał zakończenia zadania.

Kroki (dokładnie):

1. Wyślij akcję `help` i dokładnie przeczytaj odpowiedź — używaj tylko nazw akcji/parametrów zwróconych przez `help`.
2. Zastosuj sekwencję akcji dokładnie według dokumentacji z `help` (kolejność i nazwy mają znaczenie).
3. Obsłuż `503` automatycznie: retry z delaya i rosnącym backoffem.
4. Monitoruj nagłówki odpowiedzi po każdym żądaniu — jeśli limity są wyczerpane, poczekaj do czasu resetu wskazanego w nagłówkach.
5. Szukaj flagi `{FLG:...}` w treści odpowiedzi. Gdy ją znajdziesz — zadanie ukończone.

Wskazówki:

- API jest samo-dokumentujące — nie szukaj dokumentacji gdzie indziej.
- Jeśli akcja zwraca błąd, czytaj treść błędu — zwykle wskazuje, co jest nie tak (zły parametr, zła kolejność).
- `503` to część zadania — implementuj retry z exponencjalnym backoffem i jitterem.
- Limity są bardzo restrykcyjne — każde niepotrzebne wywołanie może przedłużyć zadanie. Testuj lokalnie i minimalizuj liczbę żądań.
- Loguj każde wywołanie (request/response + nagłówki) dla późniejszej analizy.

Przykładowy skrypt Python (minimalny klient z retry i sprawdzaniem nagłówków):

```python
import time
import json
import requests

URL = "https://hub.ag3nts.org/verify"
APIKEY = "tutaj-twoj-klucz"
TASK = "railway"

def post_action(payload):
	headers = {"Content-Type": "application/json"}
	return requests.post(URL, headers=headers, data=json.dumps(payload))

def wait_until_reset(resp):
	# Spróbuj odczytać standardowe nagłówki
	if 'Retry-After' in resp.headers:
		delay = int(resp.headers['Retry-After'])
		time.sleep(delay + 1)
		return
	if 'X-RateLimit-Reset' in resp.headers:
		# zakładamy timestamp UNIX
		reset_ts = int(resp.headers['X-RateLimit-Reset'])
		now = int(time.time())
		delay = max(0, reset_ts - now)
		time.sleep(delay + 1)
		return
	# fallback
	time.sleep(60)

def call_help():
	payload = {"apikey": APIKEY, "task": TASK, "answer": {"action": "help"}}
	max_attempts = 8
	backoff = 1.0
	for attempt in range(1, max_attempts + 1):
		resp = post_action(payload)
		print(f"Attempt {attempt}: status={resp.status_code}")
		print("Headers:", resp.headers)
		if resp.status_code == 200:
			return resp.json()
		if resp.status_code == 503:
			wait_until_reset(resp)
			# exponencjalny backoff z jitterem
			time.sleep(backoff + (0.1 * attempt))
			backoff = min(backoff * 2, 60)
			continue
		# inne błędy — wypisz i przerwij (lub dostosuj obsługę)
		print("Error response:", resp.text)
		break
	raise RuntimeError("Nie udało się uzyskać dokumentacji help z API")

if __name__ == '__main__':
	doc = call_help()
	print(json.dumps(doc, indent=2, ensure_ascii=False))

	# Dalej: zaimplementuj wywołania opisane w 'doc' zgodnie z kolejnością
```

Przeglądanie projektu w przeglądarce (szybkie):

- Najprostszy sposób: uruchom prosty serwer statyczny w katalogu projektu.

```bash
python -m http.server 8000
# w przeglądarce otwórz: http://localhost:8000/
```

- Alternatywa (Flask) — jeśli chcesz lepszy interfejs do listowania plików, można szybko dodać prosty serwer Flask (nie dołączony tutaj, ale można stworzyć `serve.py`).

Logowanie i debug:

- Zapisuj pełne żądania i odpowiedzi (body + nagłówki) do pliku `logs/railway_requests.log`.
- Używaj trybu such-run (dry-run) przy testowaniu sekwencji akcji lokalnie, jeśli API help opisuje operacje zmieniające stan.

Szczegóły logowania:

- **Plik logu:** `logs/railway_requests.log` (preferowany format: JSON Lines / `.jsonl`).
- **Co logować:** znacznik czasu, kierunek (`out` dla wysyłanych żądań, `in` dla odpowiedzi), pełne body request/response, status HTTP, oraz nagłówki odpowiedzi (szczególnie `Retry-After`/`X-RateLimit-Reset`).
- **Zasady:** zapisuj każdy wpis w jednej linii JSON (łatwe do parsowania), dodaj rotację plików lub ograniczenie rozmiaru, aby uniknąć nieograniczonego wzrostu.

Przykładowy fragment Pythona do logowania (JSONL):

```python
import json
from datetime import datetime

LOG_PATH = 'logs/railway_requests.log'

def log_entry(direction, payload=None, resp=None):
	entry = {
		'ts': datetime.utcnow().isoformat() + 'Z',
		'direction': direction,  # 'out' or 'in'
		'payload': payload,
	}
	if resp is not None:
		entry.update({
			'status': resp.status_code,
			'headers': dict(resp.headers),
			'body': None,
		})
		try:
			entry['body'] = resp.json()
		except Exception:
			entry['body'] = resp.text

	with open(LOG_PATH, 'a', encoding='utf-8') as f:
		f.write(json.dumps(entry, ensure_ascii=False) + "\n")

# Użycie:
# log_entry('out', payload=payload)
# resp = post_action(payload)
# log_entry('in', payload=payload, resp=resp)
```

Uwagi:

- Jeśli limitów jest dużo i logi są duże, użyj rotacji (`logging.handlers.RotatingFileHandler`) lub narzędzi zewnętrznych (logrotate).
- Zachowaj ostrożność przy logowaniu kluczy (`apikey`) — rozważ maskowanie lub usuwanie wrażliwych pól przed zapisem.

Warianty plików logu (wysyłane i odbierane dane):

- Wariant 1 (jeden plik): `logs/railway_requests.log` i pole `direction` (`out`/`in`) rozróżnia wpisy.
- Wariant 2 (dwa pliki):
	- `logs/railway_out.log` dla danych wysyłanych do API,
	- `logs/railway_in.log` dla danych odbieranych z API.
- W obu wariantach zapisuj JSONL (1 wpis = 1 linia), co ułatwia filtrowanie i analizę.

Przykładowe uruchomienia z własną ścieżką logu:

```bash
python scripts/railway_client.py --apikey "TWOJ_KLUCZ" --auto --log logs/railway_requests.log
python scripts/railway_client.py --apikey "TWOJ_KLUCZ" --auto --log logs/railway_out.log
```

Uwaga: ścieżka podana w `--log` jest względna względem bieżącego katalogu, z którego uruchamiasz skrypt.

## Brakujące kroki uruchomienia (end-to-end)

Poniżej kompletna sekwencja, która działa od zera:

1. Przejdź do katalogu `L05`.
2. Upewnij się, że masz aktywne środowisko `.venv`.
3. Zainstaluj wymagania (jeśli jeszcze nie są zainstalowane).
4. Uruchom klienta automatycznie dla trasy `x-01`.
5. Sprawdź log i wyszukaj flagę.

Przykład (PowerShell):

```powershell
Set-Location D:\Repo\AI_Devs4\ai_devs4\L05
D:\Repo\AI_Devs4\ai_devs4\.venv\Scripts\python.exe -m pip install -r requirements.txt
D:\Repo\AI_Devs4\ai_devs4\.venv\Scripts\python.exe scripts\railway_client.py --apikey "TWOJ_KLUCZ" --auto --route x-01 --log logs/railway_requests.log
Select-String -Path logs\railway_requests.log -Pattern "FLG|XXXXX"
```

## UI do przeglądania logów

W projekcie jest prosty interfejs web do przeglądania logów: tabela, filtrowanie i podgląd pełnego JSON wpisu.

Uruchomienie UI:

```powershell
Set-Location D:\Repo\AI_Devs4\ai_devs4\L05
D:\Repo\AI_Devs4\ai_devs4\.venv\Scripts\python.exe scripts\serve_ui.py --port 8000
```

Następnie otwórz w przeglądarce:

- `http://localhost:8000/ui/` - UI logów
- `http://localhost:8000/logs/railway_requests.log` - surowy plik logu

W samym UI możesz:

- filtrować po `direction` (`out` / `in`),
- filtrować po klasie statusu (`2xx`, `4xx`, `5xx`),
- wyszukiwać po tekście (`FLG`, `COUNTRYROADS`, `reconfigure`, itp.),
- kliknąć wiersz, aby zobaczyć pełny JSON wpisu.

## Oczekiwany rezultat

Po poprawnym wykonaniu sekwencji powinna pojawić się flaga:

- `{FLG:COUNTRYROADS}`

## Gotowe skrypty uruchomieniowe

Dodane są dwa pomocnicze skrypty, żeby nie przepisywać komend ręcznie:

- `scripts/run_railway.ps1` (PowerShell)
- `scripts/run_railway.sh` (bash)

Przykłady:

```powershell
Set-Location D:\Repo\AI_Devs4\ai_devs4\L05
.\scripts\run_railway.ps1 -ApiKey "TWOJ_KLUCZ"
```

```bash
cd /d/Repo/AI_Devs4/ai_devs4/L05
bash scripts/run_railway.sh "TWOJ_KLUCZ"
```

Notatki końcowe:

- Zadanie wymaga cierpliwości. Szanuj limity i obsługuj `503` automatycznie.
- Flaga w treści odpowiedzi `{FLG:...}` oznacza zakończenie zadania.

Powodzenia — gdy będziesz chciał, mogę też utworzyć gotowy klient `railway_client.py` w katalogu `scripts/` i dodać prosty interfejs do przeglądania logów.
