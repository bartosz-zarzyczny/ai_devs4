# Lekcja 02 - location, accesslevel, findhim

Ta lekcja obejmuje zadania oparte na endpointach:

- `/api/location`
- `/api/accesslevel`
- `verify` dla zadania `findhim`

## Skrypty

- [download_plant_locations.py](download_plant_locations.py) - pobiera listę elektrowni i kodów do [plant.json](plant.json)
- [fetch_people_locations.py](fetch_people_locations.py) - pobiera lokalizacje osób z CSV do [locations.json](locations.json)
- [fetch_access_levels.py](fetch_access_levels.py) - pobiera access level osób do [access_levels.json](access_levels.json)
- [solve_findhim.py](solve_findhim.py) - wykonuje proces end-to-end i może wysłać wynik do verify
- [verify_findhim_candidates.py](verify_findhim_candidates.py) - pomocnicza weryfikacja kandydatów
- [run_findhim_pipeline.ps1](run_findhim_pipeline.ps1) - uruchamia cały pipeline jednym poleceniem

## Wejście

- [people_out.csv](people_out.csv)

## Typowy przepływ

1. Pobierz listę elektrowni i kodów.
2. Pobierz listy lokalizacji dla każdej osoby.
3. Pobierz poziomy dostępu.
4. Porównaj koordynaty lokalizacji osób z koordynatami miast elektrowni.
5. Wybierz kandydata i wyślij odpowiedź do `verify` dla task `findhim`.

## Uruchamianie

Cały pipeline:

```powershell
powershell -ExecutionPolicy Bypass -File .\L02\run_findhim_pipeline.ps1
```

Albo ręcznie:

```powershell
python .\L02\download_plant_locations.py --output .\L02\plant.json
python .\L02\fetch_people_locations.py --input .\L02\people_out.csv --output .\L02\locations.json
python .\L02\fetch_access_levels.py --input .\L02\people_out.csv --output .\L02\access_levels.json
python .\L02\solve_findhim.py --input .\L02\people_out.csv --plants .\L02\plant.json --report .\L02\findhim_report.json --candidates .\L02\findhim_candidates.json --max-distance-km 2.0 --verify
```

## Wyniki

- kandydaci i metryki dopasowania: [findhim_candidates.json](findhim_candidates.json)
- raport końcowy: [findhim_report.json](findhim_report.json)

Zweryfikowany wynik `findhim`:

- `name`: `Wojciech`
- `surname`: `Bielik`
- `accessLevel`: `7`
- `powerPlant`: `PWR2758PL`

---

## Zagadka: "Gość na poziomie stworzył Wallyego i Waldo"

Zagadka polegała na zidentyfikowaniu twórcy słynnego "Gdzie jest Wally?" (**Martin Handford**) oraz odnalezieniu go w systemie pod odpowiednim "poziomem".

**Rozwiązanie:**
Odpytanie endpointu `/api/accesslevel` o osobę:
- Imię: **Martin**
- Nazwisko: **Handford**
- Rok urodzenia: **1987**

Zwraca ono flagę bonusową:
`{FLG:XXXXXXXXXXX}`


