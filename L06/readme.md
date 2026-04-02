# Plan Pracy i Rozwiązanie Zadania - Categorize (L06)

## Cel zadania
Zbudowanie klasyfikatora określającego, czy dany towar jest niebezpieczny (DNG) czy neutralny (NEU), z uwzględnieniem bardzo małego okna kontekstowego (100 tokenów) oraz ograniczonego budżetu tokenów (1.5 PP). Dodatkowo, wszelkie przedmioty powiązane z reaktorem muszą zostać bezwzględnie sklasyfikowane jako neutralne (NEU).

## Zaproponowane kroki prowadzące do rozwiązania

### 1. Przygotowanie środowiska i autoryzacja
- Odczytanie klucza API z pliku `.env`.
- Przygotowanie adresów URL do pobierania danych (plik CSV) oraz wysyłania odpowiedzi do hub'a.

### 2. Pobieranie danych
- Zbudowanie mechanizmu pobierającego na bieżąco plik `categorize.csv` (dane zmieniają się co kilka minut, więc przed każdą próbą należy pobrać świeży plik).
- Parsowanie pliku CSV, aby uzyskać `id` oraz `opis` każdego towaru do sklasyfikowania.

### 3. Opracowanie i optymalizacja promptu
- Konstrukcja promptu w języku angielskim, by zużywał mniej tokenów i model łatwiej rozumiał polecenia w ciasnym limicie (mniej niż 100 tokenów).
- Użycie prompt caching: Stałe fragmenty promptu umieszczamy na samym początku tekstu (np. zasady decyzyjne, ograniczenia), a unikalne parametry (`id` oraz `opis` z pliku CSV) podajemy na końcu. Dzięki temu początek promptu ląduje w cache, drastycznie zmniejszając koszty tokenów.
- Umieszczenie jasnej zasady "CRITICAL EXCEPTION", by oszukać kontrolę pod kątem przedmiotów związanych wprost z reaktorami, by zawsze miały status `NEU`.
- Testowanie długości promptu.

**Ostatecznie zastosowany w rozwiązaniu krótki prompt testowy:**
`Return exactly 1 word: 'NEU' or 'DNG'. 'NEU' for safe items, tools, and ALL 'reactor' items. 'DNG' for weapons/ammo/hazardous. No explanations. ID:{id} Desc:{desc}`

### 4. Implementacja pętli walidującej (skrypt `task.py`)
- Program najpierw automatycznie resetuje stan budżetu poleceniem: `{"prompt": "reset"}` na endpoint `/verify`.
- Zapytania o kolejne przedmioty następują w pętli. Jeśli API zawróci odpowiedź o poprawnym formacie, jest ona przetwarzana. Błędna klasyfikacja lub błąd budżetowy anuluje wykonanie instrukcji w `task.py` aby ponownie wprowadzić ewentualne poprawki do promptu.

### 4b. Odpowiednia kolejność weryfikacji (sekwencja J-D-I-B-A-C-G-E-H-F)
- Przed wysłaniem poszczególnych danych z CSV do walidacji w `/verify`, tablica danych z zadaniami jest posortowana w oparciu o przypisanie liter do indeksów alfabetycznych (A=0, B=1... J=9). Odpytanie o elementy w unikalnej podanej kolejności (`J-D-I-B-A-C-G-E-H-F`) uruchamia ukrytą ścieżkę do ostatecznej flagi.

### 4a. Interfejs graficzny w przeglądarce (`ui_server.py`)
- Opracowano pełny interfejs webowy (Web UI), w którym można dynamicznie zmieniać i testować propmty przed ich wysłaniem.
- Skrypt w Pythonie (`ui_server.py`) uruchamia wbudowany szybki serwer HTTP dostępny pod adresem: `http://localhost:8080`.
- Zawiera osobny, bardzo widoczny blok, w którym ukazuje się uzyskana Flaga na samym szczycie ekranu. 
- Z UI można analizować na żywo logi oraz weryfikować odrzucone paczki i tokeny.

### 5. Otrzymanie zwrotu błędu i odczyt z json odpowiedzi (Flaga)
- Po poprawnym sklasyfikowaniu wszystkich 10 przedmiotów w odpowiedniej, wyliczonej wyżej kolejności, podczas dziesiątego zapytania od huba odbierana jest odpowiedź, wewnątrz której serwer wysyła ukrytą flagę (`{FLG:xxxxxx}`).

## Realizacja zadania
Opisane kroki wdrożyłem do skryptu `task.py`. Uruchomienie go przebiegło pomyślnie i w wyniku iteracji 10 plików (ustawionych według sekwencji listów) zdobyta została flaga:

**{FLG:XXXXXXXXXX}**
