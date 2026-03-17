# ai_devs4

Repozytorium zawiera rozwiązania zadań AI_DEVS 4.

## Lekcje

- [L01/README.md](L01/README.md) - zadanie `people` (filtrowanie, tagowanie, wysyłka do verify)
- [L02/README.md](L02/README.md) - zadania `location`, `accesslevel`, `findhim` (analiza i verify)
 - [L03/README.md](L03/README.md) - lokalny serwer i narzędzia do submit (debug endpoints)
 - [L04/README.md](L04/README.md) - zadanie `sendit` (deklaracja transportowa, test tras, logowanie odpowiedzi)
 - [L05/README.md](L05/README.md) - narzędzia typu "railway" do wykonywania sekwencji akcji, bezpieczne logowanie i prosty UI do przeglądu logów
 - [L06/readme.md](L06/readme.md) - zadanie `categorize` (klasyfikator DNG/NEU, optymalizacja promptów, prompt caching) oraz interfejs graficzny UI (`ui_server.py`)
 - [L07/README.md](L07/README.md) - zadanie `electricity` (pobieranie obrazu, analiza 3x3, automatyczny solver, lokalny UI oraz parsowanie meta-flag w PNG)

## Konfiguracja

Projekt korzysta ze standardowej biblioteki Pythona. W katalogu głównym utwórz plik `.env`:

```env
API_OPEN_ROUTER_KEY=twoj_klucz_openrouter
AI_DEVS_4_API_KEY=twoj_klucz_ai_devs
```

Wymagane zmienne:

- `API_OPEN_ROUTER_KEY` dla skryptów używających OpenRouter (L01)
- `AI_DEVS_4_API_KEY` dla endpointów hub.ag3nts.org (L01, L02)
 - `AI_DEVS_4_API_KEY` jest również używana przez skrypty w `L04` (send_payload/test_routes)

## Ostatnie zmiany (skrót)

- L03: dodano lokalny serwer i narzędzia pomocnicze; folder `L03` zawiera logi i endpointy debugujące (sprawdź L03/logs).
- L04: komplet rozwiązań dla zadania `sendit` — `send_payload.py` (opcje `--route`, `--wdp`, `--response-log`), `test_routes.py` do batch-testów, `validate_declaration.py` do lokalnej walidacji. Usunięto pliki tymczasowe i dodano oddzielny `response_log.jsonl` dla maszynowego przetwarzania odpowiedzi.
- Rezultat L04: poprawne wypełnienie deklaracji i otrzymanie potwierdzenia zwrotnego (szczegóły w [L04/README.md](L04/README.md)).

## L05 — Railway (automatyczny executor)

- Lokalizacja: `L05/`
- Cel: narzędzia do automatycznego wykonania sekwencji akcji opisanej przez endpoint `help`, bezpieczne logowanie żądań/odpowiedzi oraz prosty interfejs przeglądu logów w przeglądarce.

- Najważniejsze pliki:
	- `L05/scripts/railway_client.py` — CLI klient wykonujący: pobranie `help`, zbudowanie bezpiecznej sekwencji (np. `reconfigure` → `setstatus` → `save` → `getstatus`), retry/backoff i logowanie JSONL.
	- `L05/logs/railway_requests.log` — plik JSONL z zapisem wszystkich żądań i odpowiedzi (maskowanie pól wrażliwych).
	- `L05/ui/index.html` — prosty frontend do filtrowania i podglądu wpisów z pliku logów.
	- `L05/scripts/serve_ui.py` — skrypt uruchamiający serwer HTTP i otwierający UI w przeglądarce.
	- `L05/scripts/run_railway.ps1` / `L05/scripts/run_railway.sh` — wygodne wrappery uruchamiające przepływ i wyciągające znalezione flagi.
	- `L05/requirements.txt` — zależności (minimalnie: `requests`).

- Szybkie uruchomienie (w katalogu repozytorium, w aktywowanym virtualenv):

```powershell
python -m pip install -r L05/requirements.txt
python L05/scripts/railway_client.py --apikey "<AI_DEVS_4_API_KEY>" --auto --route x-01
```

- Przydatne opcje klienta:
	- `--dry-run` — pokazuje sekwencję bez wysyłania żądań.
	- `--confirm` — interaktywne potwierdzenie przed wykonaniem kolejnych kroków.
	- `--log L05/logs/railway_requests.log` — nadpisanie ścieżki do pliku logów.

- Uruchomienie interfejsu przeglądu logów:

```powershell
python L05/scripts/serve_ui.py --port 8000
# otwórz http://localhost:8000/ui/ w przeglądarce
```

- Notatki:
	- Klient obsługuje nagłówki rate-limit (`Retry-After`, `X-RateLimit-Reset`) oraz kody 429/503 z eksponencjalnym backoffem i jitterem.
	- Wynikowe flagi i pełne odpowiedzi zapisywane są w `L05/logs/railway_requests.log` (nie umieszczamy flag w README).
	- Do uruchomienia skryptów wymagany jest klucz środowiskowy `AI_DEVS_4_API_KEY` (zobacz sekcję "Konfiguracja" wyżej).
	 - Do uruchomienia skryptów wymagany jest klucz środowiskowy `AI_DEVS_4_API_KEY` (zobacz sekcję "Konfiguracja" wyżej).

	## L07 — Electricity (puzzle + UI + solver)

	Krótki opis:
	- Cel: automatyczne rozwiązanie zadania "electricity" (pobranie obrazu, analiza 3x3, plan rotacji, wykonanie ruchów na hubie) oraz odkrycie ukrytej meta-informacji w pliku PNG.

	Najważniejsze pliki:
	- `L07/get_electricity.py` — pobiera aktualny obraz zadania z hubu (korzysta z `AI_DEVS_4_API_KEY` z pliku `.env`).
	- `L07/electricity_solver.py` — analiza obrazu, tworzenie planu rotacji, parsowanie chunków PNG (tEXt) oraz funkcje pomocnicze do zastosowania planu.
	- `L07/ui_server.py` — prosty serwer HTTP udostępniający UI i REST API (`/api/analyze`, `/api/apply-plan`, `/api/meta-flag`).
	- `L07/ui.html` — interfejs przeglądarkowy: podgląd planszy, analiza kafelków, przyciski sterujące i przycisk "Odkryj meta-flagę".
	- `L07/readme.md` — szczegółowe instrukcje i notatki dotyczące rozwiązania (lokalne).

	Szybkie uruchomienie (virtualenv aktywowane):

	```powershell
	python -m pip install requests pillow python-dotenv
	python L07/get_electricity.py    # pobiera current electricity.png i solved_electricity.png
	python L07/ui_server.py          # uruchamia UI; domyślnie próbuje port 8080 i wybiera następny wolny
	# otwórz w przeglądarce: http://127.0.0.1:8080/ (port może się różnić)
	```

	Uwaga:
	- Serwery hub wymagają nagłówka/klucza API — skonfiguruj `AI_DEVS_4_API_KEY` w pliku `.env` w katalogu repo.
	- UI udostępnia endpoint `GET /api/meta-flag`, który parsuje chunk tEXt wewnątrz pobranego PNG i dekoduje ewentualną ukrytą treść. README w `L07` zawiera więcej szczegółów technicznych.

