# ai_devs4

Repozytorium zawiera rozwiązania zadań AI_DEVS 4. Obecnie w katalogu [L01](L01) znajduje się pipeline dla zadania `people`: filtrowanie danych z CSV, tagowanie zawodów przy użyciu OpenRouter i wysyłka odpowiedzi do endpointu weryfikacyjnego.

## Zakres katalogu L01

Przepływ pracy składa się z trzech kroków:

1. `filter_people.py` filtruje rekordy z pliku `people.csv`.
2. `tag_people_openrouter.py` przypisuje tagi zawodowe do przefiltrowanych osób.
3. `submit_people_task.py` wysyła gotowy wynik do API AI_DEVS.

## Logika filtrowania

Skrypt [L01/filter_people.py](L01/filter_people.py) wybiera osoby spełniające wszystkie warunki:

- płeć: `M`
- wiek: od `20` do `39` lat według daty referencyjnej `2026-03-09`
- miejsce urodzenia: `Grudziądz`

Wejście i wyjście:

- wejście: [L01/people.csv](L01/people.csv)
- wyjście: [L01/people_out.csv](L01/people_out.csv)

## Tagowanie zawodów

Skrypt [L01/tag_people_openrouter.py](L01/tag_people_openrouter.py) odczytuje [L01/people_out.csv](L01/people_out.csv), buduje payload dla modelu i zapisuje wynik do [L01/output.json](L01/output.json).

Dozwolone tagi:

- `IT`
- `transport`
- `edukacja`
- `medycyna`
- `praca z ludźmi`
- `praca z pojazdami`
- `praca fizyczna`

Skrypt waliduje odpowiedź modelu, usuwa duplikaty tagów i wykonuje dodatkową próbę naprawy dla rekordów bez przypisanych tagów.

Domyślny model:

- `google/gemini-2.0-flash-lite-001`

## Konfiguracja

Projekt korzysta wyłącznie ze standardowej biblioteki Pythona, więc nie wymaga instalacji zależności z `requirements.txt`.

W katalogu głównym utwórz plik `.env`:

```env
API_OPEN_ROUTER_KEY=twoj_klucz_openrouter
AI_DEVS_4_API_KEY=twoj_klucz_ai_devs
OPENROUTER_MODEL=google/gemini-2.0-flash-lite-001
```

Wymagane zmienne:

- `API_OPEN_ROUTER_KEY` do tagowania przez OpenRouter
- `AI_DEVS_4_API_KEY` do wysłania odpowiedzi do endpointu `verify`

Opcjonalna zmienna:

- `OPENROUTER_MODEL` jeśli chcesz nadpisać model domyślny

## Uruchamianie

Przykładowa sekwencja z katalogu głównego repozytorium:

```powershell
python .\L01\filter_people.py
python .\L01\tag_people_openrouter.py
python .\L01\submit_people_task.py
```

Dostępne parametry:

```powershell
python .\L01\tag_people_openrouter.py --input .\L01\people_out.csv --output .\L01\output.json --model google/gemini-2.0-flash-lite-001
python .\L01\submit_people_task.py --answer .\L01\output.json
```

## Format wyniku

Plik [L01/output.json](L01/output.json) zawiera tablicę obiektów w postaci:

```json
[
  {
    "name": "Albert",
    "surname": "Skiba",
    "gender": "M",
    "born": 1991,
    "city": "Grudziądz",
    "tags": ["IT"]
  }
]
```

## Struktura plików

- [README.md](README.md) opis projektu
- [L01/filter_people.py](L01/filter_people.py) filtrowanie rekordów wejściowych
- [L01/tag_people_openrouter.py](L01/tag_people_openrouter.py) klasyfikacja zawodów przez LLM
- [L01/submit_people_task.py](L01/submit_people_task.py) wysyłka odpowiedzi do API
- [L01/people.csv](L01/people.csv) dane wejściowe
- [L01/people_out.csv](L01/people_out.csv) dane po filtrowaniu
- [L01/output.json](L01/output.json) wynik końcowy
