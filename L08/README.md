# Plan wykonania zadania "failure"

Poniżej znajduje się szczegółowy plan oraz kroki, jakie podejmę, aby prawidłowo i efektywnie rozwiązać zadanie scentralizowanego zbierania i kompresji logów dla Centrali.

## Krok 1: Inicjalizacja i pobranie danych
1. **Odczytanie klucza API**: Pobiorę klucz API z pliku `.env` znajdującego się w głównym katalogu projektu (`d:\Repo\AI_Devs4\ai_devs4\.env`).
2. **Pobranie pliku logów**: Wykorzystam pobrany klucz do zbudowania URLa (`https://hub.ag3nts.org/data/{API_KEY}/failure.log`) i pobiorę pełny plik logów, zapisując go lokalnie w katalogu `L08`.

## Krok 2: Wstępna analiza pliku
1. **Rozmiar i statystyki**: Za pomocą prostych komend bash/python zbadam wielkość pliku – zliczę ilość linii oraz oszacuję całkowitą liczbę tokenów (np. narzędziem `tiktoken`).
2. **Przegląd formatu**: Pobiorę kilka pierwszych i losowych linii, by upewnić się, w jakim formacie zapisane są daty, godziny, znaczniki ważności i komponenty.

## Krok 3: Stworzenie narzędzi (Tooling)
Ponieważ plik jest za duży, żeby umieścić go w całości w kontekście modelu i każdorazowo generować duże koszty, przygotuję skrypty pomocnicze:
1. **Skrypt do przeszukiwania (Search Tool)**: Prosty skrypt w Pythonie (lub komenda `grep`), który pozwoli sub-agentowi na wyszukiwanie logów po słowach kluczowych (np. nazwach podzespołów wskazanych przez techników w feedbacku) lub po poziomie błędu (np. `WARN`, `ERRO`, `CRIT`).
2. **Kalkulator tokenów**: Funkcja włączona do procesu, która dokładnie zliczy (przy użyciu biblioteki `tiktoken`, np. modelu `cl100k_base`) bazową ilość tokenów wybranych logów, by nigdy nie przekroczyć twardego limitu 1500 tokenów.

## Krok 4: Iteracyjny proces (Agent Loop)
Zastosuję podejście agentowe, wysyłając dane i udoskonalając je w pętli na podstawie precyzyjnego feedbacku:

1. **Inicjalny zbiór zdarzeń**:
   - Przeszukam logi pod kątem incydentów krytycznych (`CRIT`, `ERRO`) systemów i podzespołów powiązanych z awarią (np. cooling, power, water pumps, oprogramowanie).
   - Sformatuję wyciągnięte linie zgodnie z wytycznymi: `YYYY-MM-DD HH:MM [POZIOM] podzespół: skrócony opis`.
   - Upewnię się za pomocą skryptu, że zestaw ten mieści się w limicie 1500 tokenów.

2. **Wysłanie do weryfikacji**:
   - Wykonam żądanie POST pod adres `https://hub.ag3nts.org/verify` z wytypowanymi logami.

3. **Przetwarzanie feedbacku i korekta**:
   - Odbiorę odpowiedź Centrali.
   - Jeżeli brakuje pewnych informacji (np. Centrala wskaże, że brakuje kontekstu dla konkretnego podzespołu), sub-agent zostanie poproszony o wylistowanie logów specyficznie dla tego podzespołu (oraz ewentualnych logów powiązanych czasowo).
   - Skompresuję istniejące już logi (np. przez parafrazę lub usunięcie najmniej istotnych) na rzecz wpisania tych nowo wymaganych, cały czas pilnując limitu tokenów.

4. **Sukces**:
   - Powtórzę iterację (Wysłanie -> Feedback -> Poprawa) aż do momentu, w którym technicy potwierdzą, że logi są kompletne i system zwróci poprawną flagę `{FLG:...}`.
   - W tym rozwiązaniu sukces został osiągnięty po pierwszym wysłaniu, a flagą jest `{FLG:XXXXXXX}`.
   - Ostatnim krokiem jest zapisanie odpowiedzi do `verification_result.json`.

## UI do kroku 1

W folderze `L08` jest prosty panel WWW w stylu podobnym do `L06` i `L07`:

- `task.py` — pobiera `failure.log`, tworzy `failure_compact.log`, wysyła dane do `/verify` i zapisuje wynik.
- `ui_server.py` — uruchamia lokalny serwer WWW z endpointami do pobierania, kompresji, weryfikacji i podglądu logu.
- `ui.html` — interfejs do pobrania pliku, odświeżania statusu, oglądania head/tail loga, wyniku weryfikacji i flagi.
- `failure_compact.log` — skrócona wersja logów, 48 linii i 1310 tokenów cl100k_base, mieści się w limicie 1500.
- `verification_result.json` — zapis odpowiedzi Centrali po wysłaniu logów do `/verify`.

## Wysłanie do weryfikacji

Po zbudowaniu `failure_compact.log` skrypt `task.py` wykonuje POST do `https://hub.ag3nts.org/verify`.
Wymagany format pola `answer` to JSON zapisany jako string, np. `{"logs": "..."}`.
Jeżeli Centrala zwróci feedback zamiast flagi, kod potrafi wyłuskać wskazane podzespoły i zbudować kolejną wersję pliku z logami, zachowując limit 1500 tokenów.
Tokeny złych odpowiedzi liczę praktycznie jako znaki, żeby szybciej ocenić, ile miejsca zajmuje feedback i kiedy trzeba jeszcze mocniej skrócić log.

## Ukryta flaga tokenowa

W zadaniu pojawia się dodatkowa zagadka: odpowiedzi błędne zwracają pole `letter`, a jego wartość jest zgodna z `chr(tokenCount)`.
To oznacza, że liczy się dokładna liczba tokenów wysyłanego tekstu, nie jego semantyka.

Kod do automatycznego odtworzenia tej flagi znajduje się w:

- [L08/hidden_flag_solver.py](hidden_flag_solver.py)

Mechanizm:

1. Wysyłane są 4 kolejne błędne odpowiedzi z dokładnymi budżetami tokenów: `70`, `76`, `65`, `71`.
2. Centrala zwraca wtedy litery `F`, `L`, `A`, `G`.
3. Po odblokowaniu mechanizmu serwer zwraca ukrytą flagę:
   `{FLG:XXXXXXX}`

Uruchomienie:

- `python L08/hidden_flag_solver.py`

Po wykonaniu skrypt zapisuje wynik do `hidden_flag_result.json`.

## UI

Panel WWW ma teraz także przycisk i sekcję dla ukrytej flagi tokenowej.
Po kliknięciu można odtworzyć sekwencję prób i zobaczyć wynik bez ręcznego wklejania odpowiedzi.

Uruchomienie:

- `python L08/task.py`
- `python L08/ui_server.py`
