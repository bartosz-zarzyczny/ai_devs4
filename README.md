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
- [L08/README.md](L08/README.md) - zadanie `failure` (kompresja logów, UI WWW, pętla weryfikacji i finalna flaga)
- [L09/README.md](L09/README.md) - zadanie `mailbox` (wyszukiwanie poczty w zmail, UI WWW, główna flaga z `/verify` oraz bonusowa flaga z załącznika)
- [L10/README.md](L10/README.md) - zadanie `drone` (analiza mapy, UI WWW, lot drona i weryfikacja na `/verify`)
- [L11/README.md](L11/README.md) - zadanie `evaluation` (detekcja anomalii w 10 000 odczytach sensorów, klasyfikacja LLM notatek operatorów, bonusowa flaga z AWK)
- [L12/README.md](L12/README.md) - zadanie `firmware` (agentowa pętla na VM, uruchomienie cooler.bin, weryfikacja ECCS; bonus: zagadka z `/bin/flaggengenerator schmetterling`)
- [L13/README.md](L13/README.md) - zadanie `reactor` (autonomiczny robot na planszy 7×5, omijanie bloków reaktora, UI WWW z trybem AUTO-PLAY)
- [L15/README.md](L15/README.md) - zadanie `savethem` (optimal routing agent, toolsearch discovery, fuel+food constraints, Dijkstra pathfinding, UI WWW z wizualizacją mapy 10×10)
- [L16/README.md](L16/README.md) - zadanie `okoeditor` (edycja Centrum Operacyjnego OKO wyłącznie przez API, bez ręcznych zmian w panelu)

## Konfiguracja

Projekt korzysta głównie ze standardowej biblioteki Pythona, ale kilka lekcji wymaga dodatkowych paczek z `requirements.txt`. W katalogu głównym utwórz plik `.env`:

```env
API_OPEN_ROUTER_KEY=twoj_klucz_openrouter
AI_DEVS_4_API_KEY=twoj_klucz_ai_devs
```

Wymagane zmienne:

- `API_OPEN_ROUTER_KEY` dla skryptów używających OpenRouter (L01)
- `AI_DEVS_4_API_KEY` dla endpointów hub.ag3nts.org (L01, L02)
- `AI_DEVS_4_API_KEY` jest również używana przez skrypty w `L04` (send_payload/test_routes)

Instalacja zależności:

```powershell
python -m pip install -r requirements.txt
```

`requirements.txt` obejmuje wspólne paczki używane w repozytorium: `requests`, `tiktoken`, `fastapi`, `pydantic`, `python-dotenv`, `Pillow` i `uvicorn`.

## Ostatnie zmiany (skrót)

- L13: autonomiczny solver zadania `reactor`; robot przeszedł całą mapę 7×5 w 11 krokach bez kolizji; flaga `{FLG:INSTALLED}`; UI WWW z trybem AUTO-PLAY na porcie 8013.
- L12: agentowa pętla na VM z `cooler.bin`; flaga główna `{FLG:XXXXXXXX}` z `/verify`; bonusowa zagadka `/bin/flaggengenerator schmetterling` → `{FLG:XXXXXXXX}`; UI z kartą bonusu i przyciskiem.
- L11: detekcja anomalii w 10 000 plikach JSON (46 programistycznych + 6 z notatek); flaga `{FLG:XXXXXXX}`; bonus AWK `{FLG:XXXXXXXX}`.
- L03: dodano lokalny serwer i narzędzia pomocnicze; folder `L03` zawiera logi i endpointy debugujące (sprawdź L03/logs).
- L04: komplet rozwiązań dla zadania `sendit` — `send_payload.py` (opcje `--route`, `--wdp`, `--response-log`), `test_routes.py` do batch-testów, `validate_declaration.py` do lokalnej walidacji. Usunięto pliki tymczasowe i dodano oddzielny `response_log.jsonl` dla maszynowego przetwarzania odpowiedzi.
- Rezultat L04: poprawne wypełnienie deklaracji i otrzymanie potwierdzenia zwrotnego (szczegóły w [L04/README.md](L04/README.md)).
- L08: dodano UI WWW, kompresję `failure.log` do `failure_compact.log` (48 linii, 1310 tokenów cl100k_base), weryfikację na `/verify` i zapis odpowiedzi do `verification_result.json`.
- L09: dodano UI WWW do `zmail`, osobny tor dla głównej flagi i bonusowy solver załącznika; wyniki zapisują się do `verification_result.json` oraz `bonus_flag_result.json`.
- L10: dodano UI WWW dla zadania `drone`, solver z analizą mapy przez vision, weryfikację lotu i zapis odpowiedzi do `verification_result.json`.

## L13 — Reactor (autonomiczny robot)

Krótki opis:
- Cel: przeprowadzenie robota transportującego przez planszę 7×5, omijając pionowo poruszające się bloki reaktora, aż do kolumny 7 wiersz 5.

Najważniejsze pliki:
- [L13/task.py](L13/task.py) — autonomiczny solver: pętla `start → decide → right/wait/left`, obsługa 409 (reset i restart), zapis do `verification_result.json`.
- [L13/ui_server.py](L13/ui_server.py) — serwer HTTP (port 8013) z endpointami `/api/state` i `/api/command`.
- [L13/ui.html](L13/ui.html) — panel WWW: wizualizacja planszy 7×5, przyciski komend, tryb AUTO-PLAY.
- [L13/verification_result.json](L13/verification_result.json) — odpowiedź huba po zaliczeniu zadania.

Szybkie uruchomienie:

```powershell
python L13/task.py
python L13/ui_server.py
```

Wyniki:
- Flaga: `{FLG:XXXXX}` — robot dotarł do celu w 11 krokach.

## L12 — Firmware (agentowy solver + bonus flaggengenerator)

Krótki opis:
- Cel: agentowa pętla (claude-sonnet) łączy się z ograniczoną maszyną wirtualną przez Shell API, konfiguruje `settings.ini`, usuwa lock-plik i uruchamia `cooler.bin`, a następnie wysyła kod `ECCS-...` do `/verify`.
- Bonus: zagadka „Uruchom mnie z niemieckim motylem" — uruchomienie `/bin/flaggengenerator schmetterling` zwraca base64 → `{FLG:XXXXXXXXXX}`.

Najważniejsze pliki:
- [L12/task.py](L12/task.py) — agentowy solver: narzędzia `shell_cmd` + `submit_answer`, pętla LLM, flag `--reboot`.
- [L12/bonus_probe.py](L12/bonus_probe.py) — jednorazowy probe kandydatów hasła dla `flaggengenerator`.
- [L12/ui_server.py](L12/ui_server.py) — serwer HTTP z endpointami `/api/status`, `/api/shell`, `/api/bonus/run`, `/api/reboot`.
- [L12/ui.html](L12/ui.html) — panel WWW: karty flag (główna + bonus), log agenta, ręczny terminal, przycisk reboot.
- [L12/verification_result.json](L12/verification_result.json) — odpowiedź huba po poprawnym submit.

Szybkie uruchomienie:

```powershell
python L12/task.py
python L12/ui_server.py
```

Wyniki:
- Flaga główna: `{FLG:XXXXXXXXX}`
- Flaga bonusowa: `{FLG:XXXXXXXX}` (`/bin/flaggengenerator schmetterling` → base64)

## L11 — Evaluation (anomalie w odczytach sensorów)

Krótki opis:
- Cel: znalezienie anomalii w 10 000 plikach JSON z odczytami sensorów elektrowni (wartości poza zakresem, nieaktywne pola ≠ 0, rozbieżności notatek operatorów) i wysłanie listy ID do `/verify`.

Najważniejsze pliki:
- [L11/task.py](L11/task.py) — pobiera `sensors.zip`, wykrywa anomalie programistycznie i przez LLM, wysyła do `/verify`.
- [L11/bonus_solver.py](L11/bonus_solver.py) — dekoduje bonusową flagę przez skrypt AWK z `decode.txt`.
- [L11/ui_server.py](L11/ui_server.py) — serwer HTTP do inspekcji wykrytych anomalii.
- [L11/ui.html](L11/ui.html) — panel WWW z listą anomalii.
- [L11/verification_result.json](L11/verification_result.json) — odpowiedź huba.

Szybkie uruchomienie:

```powershell
python L11/task.py
python L11/bonus_solver.py
python L11/ui_server.py
```

Wyniki:
- 52 anomalie (46 programistycznych + 6 z notatek), flaga: `{FLG:XXXXXXXXXXX}`
- Bonus AWK: `{FLG:XXXXXXXXXXX}`

## L10 — Drone

Krótki opis:
- Cel: przeprowadzenie drona przez misje weryfikacyjną na hubie, z analizą mapy do sektora tamy i uruchomieniem lotu z potwierdzonymi parametrami.

Najważniejsze pliki:
- [L10/task.py](L10/task.py) — uruchamia analizę mapy i wysyła instrukcje do `/verify`.
- [L10/drone_solver.py](L10/drone_solver.py) — wspólna logika vision, budowy instrukcji, resetu i zapisu wyników.
- [L10/ui_server.py](L10/ui_server.py) — lokalny serwer HTTP z endpointami statusu, analizy, resetu i uruchomienia misji.
- [L10/ui.html](L10/ui.html) — panel WWW do krokowego sprawdzania stanu i uruchamiania misji.
- [L10/verification_result.json](L10/verification_result.json) — ostatnia odpowiedz z huba po poprawnym locie.

Szybkie uruchomienie:

```powershell
python L10/ui_server.py
python L10/task.py
```

Uwaga:
- W tej lekcji nie byly potrzebne nowe zaleznosci poza paczkami obecnymi juz w root `requirements.txt`.
- Zweryfikowany sektor tamy to `2,4`, a sensowna wysokosc lotu to `8m` lub wyzsza.

## L09 — Mailbox

Krótki opis:
- Cel: przeszukanie skrzynki operatora przez API `zmail`, pobranie pełnych treści wiadomości i wysłanie odpowiedzi do `/verify`.
- Dodatkowo: bonusowy tor wyszukuje wiadomość z załącznikiem `dokumenty.zip`, rozpakowuje archiwum i dekoduje dodatkową flagę.

Najważniejsze pliki:
- [L09/task.py](L09/task.py) — uruchamia wysłanie odpowiedzi do `/verify` i zapisuje wynik do `verification_result.json`.
- [L09/mailbox_client.py](L09/mailbox_client.py) — wspólne wywołania `zmail`, weryfikacja głównej flagi oraz logika bonusu.
- [L09/bonus_solver.py](L09/bonus_solver.py) — osobny skrypt do odszukania i dekodowania bonusowej flagi.
- [L09/ui_server.py](L09/ui_server.py) — lokalny serwer HTTP z endpointami dla statusu, `help`, `search`, `getThread`, `getMessages`, `verify` i bonusu.
- [L09/ui.html](L09/ui.html) — panel WWW z przyciskami do kolejnych kroków i widokiem wyników.
- [L09/verification_result.json](L09/verification_result.json) — odpowiedź huba po poprawnym wysłaniu głównej flagi.
- [L09/bonus_flag_result.json](L09/bonus_flag_result.json) — wynik bonusowego solvera.

Szybkie uruchomienie:

```powershell
python L09/ui_server.py
python L09/task.py
python L09/bonus_solver.py
```

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
- [L07/get_electricity.py](L07/get_electricity.py) — pobiera aktualny obraz zadania z hubu (korzysta z `AI_DEVS_4_API_KEY` z pliku .env).
- [L07/electricity_solver.py](L07/electricity_solver.py) — analiza obrazu, tworzenie planu rotacji, parsowanie chunków PNG (tEXt) oraz funkcje pomocnicze do zastosowania planu.
- [L07/ui_server.py](L07/ui_server.py) — prosty serwer HTTP udostępniający UI i REST API (`/api/analyze`, `/api/apply-plan`, `/api/meta-flag`).
- [L07/ui.html](L07/ui.html) — interfejs przeglądarkowy: podgląd planszy, analiza kafelków, przyciski sterujące i przycisk "Odkryj meta-flagę".
- [L07/README.md](L07/README.md) — szczegółowe instrukcje i notatki dotyczące rozwiązania.

## L08 — Failure (kompresja logów + UI + weryfikacja)

Krótki opis:
- Cel: pobranie `failure.log`, skrócenie go do limitu 1500 tokenów, wysłanie do `/verify` i zapisanie wyniku.

Najważniejsze pliki:
- [L08/task.py](L08/task.py) — pobiera log, buduje `failure_compact.log`, wysyła weryfikację i zapisuje odpowiedź.
- [L08/failure_fetch.py](L08/failure_fetch.py) — logika pobierania, kompresji, wyboru linii i obsługi feedbacku.
- [L08/ui_server.py](L08/ui_server.py) — lokalny serwer HTTP z endpointami do pobierania, kompresji i weryfikacji.
- [L08/ui.html](L08/ui.html) — interfejs WWW z podglądem surowego logu, skróconego logu, weryfikacji i flagi.
- [L08/verification_result.json](L08/verification_result.json) — zapis odpowiedzi Centrali, zawiera `{FLG:XXXXXXX}`.

Szybkie uruchomienie (virtualenv aktywowane):

```powershell
python L08/task.py
python L08/ui_server.py
```

Uwaga:
- `failure_compact.log` ma 48 linii i 1310 tokenów cl100k_base.
- Weryfikacja działa przez POST na `https://hub.ag3nts.org/verify` z polem `answer` jako string JSON: `{"logs": "..."}`.

