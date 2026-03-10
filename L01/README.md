# Lekcja 01 - people

W tej lekcji znajduje się pipeline dla zadania `people`: filtrowanie danych z CSV, tagowanie zawodów przy użyciu OpenRouter i wysyłka odpowiedzi do endpointu weryfikacyjnego.

## Przepływ pracy

1. `filter_people.py` filtruje rekordy z `people.csv`.
2. `tag_people_openrouter.py` przypisuje tagi zawodowe do przefiltrowanych osób.
3. `submit_people_task.py` wysyła gotowy wynik do API AI_DEVS.

## Logika filtrowania

Skrypt [filter_people.py](filter_people.py) wybiera osoby spełniające wszystkie warunki:

- płeć: `M`
- wiek: od `20` do `39` lat według daty referencyjnej `2026-03-09`
- miejsce urodzenia: `Grudziądz`

Wejście i wyjście:

- wejście: [people.csv](people.csv)
- wyjście: [people_out.csv](people_out.csv)

## Tagowanie zawodów

Skrypt [tag_people_openrouter.py](tag_people_openrouter.py) odczytuje [people_out.csv](people_out.csv), buduje payload dla modelu i zapisuje wynik do [output.json](output.json).

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

Plik [output.json](output.json) zawiera tablicę obiektów, np.:

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

## Pliki

- [filter_people.py](filter_people.py)
- [tag_people_openrouter.py](tag_people_openrouter.py)
- [submit_people_task.py](submit_people_task.py)
- [people.csv](people.csv)
- [people_out.csv](people_out.csv)
- [output.json](output.json)
