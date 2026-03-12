# README — L04 `sendit`

## Cel

Przesłanie poprawnie wypełnionej deklaracji transportu SPK do Centrali (`/verify`).  
Trasa: Gdańsk → Żarnowiec, nadawca `450202122`, ładunek 2800 kg, kategoria A.



---

## Pliki

| Plik | Opis |
|---|---|
| `prompts` | Oryginalne polecenie zadania |
| `payload_to_send.json` | Gotowy payload (puste `apikey` — podaj przez `--apikey`) |
| `send_payload.py` | Główny skrypt wysyłający |
| `test_routes.py` | Skrypt do hurtowego testowania kodów tras |
| `validate_declaration.py` | Lokalny walidator formatu deklaracji (bez sieci) |

Pliki generowane w trakcie działania (`.gitignore`-owane):

| Plik | Opis |
|---|---|
| `send_log.txt` | Ogólny log: request + response, tryb append |
| `response_log.jsonl` | Osobny log odpowiedzi API — jedna linia JSON na wywołanie |

---

## Rozwiązanie

| Pole | Wartość | Uzasadnienie |
|---|---|---|
| KATEGORIA | `A` | Strategiczna — opłacana przez System (0 PP), jedyna kategoria dopuszczona na trasie Żarnowiec (Dyrektywa 7.7) |
| TRASA | `X-01` | Trasa wyłączona z użytku, ale dozwolona dla kat. A/B do Żarnowca |
| WDP | `4` | Standardowy skład: 2 × 500 kg = 1000 kg. Na 2800 kg potrzeba 4 dodatkowych wagonów (po 500 kg). Dla kat. A opłata zeralna. |
| KWOTA | `0` | Kat. A zwolniona z opłat |

---

## Użycie skryptów

### Wysyłka deklaracji

```bash
python L04/send_payload.py --apikey "TWÓJ_KLUCZ"
```

Logi trafiają do dwóch plików:
- `send_log.txt` — pełny request (zredagowany) + odpowiedź, czytelny format tekstowy
- `response_log.json` — jedna linia JSON na wywołanie, łatwa do parsowania

Przykładowa linia z `response_log.json`:
```json
{"timestamp": "2026-03-12T20:54:00Z", "status_code": 200, "response": {"code": 0, "message": "{FLG:XXXXXX}"}, "route": null, "wdp": null}
```

#### Opcje CLI

| Argument | Opis |
|---|---|
| `--apikey KEY` | Klucz API (nadpisuje wartość z pliku) |
| `--route KOD` | Nadpisuje pole `TRASA` w deklaracji |
| `--wdp N` | Nadpisuje pole `WDP` w deklaracji |
| `--log PLIK` | Ścieżka do ogólnego logu (domyślnie `send_log.txt`) |
| `--response-log PLIK` | Ścieżka do logu odpowiedzi (domyślnie `response_log.json`) |
| `--dry-run` | Nie wysyła requestu, tylko loguje payload |
| `--url URL` | Nadpisuje docelowy URL |

### Testowanie wielu kodów tras

```bash
python L04/test_routes.py --apikey "TWÓJ_KLUCZ"
```

Własna lista tras:

```bash
python L04/test_routes.py --apikey "TWÓJ_KLUCZ" --routes X-01 X-02 X-03 --wdp 4
```

Wyniki w tabeli ASCII + zapis do `route_test_results.json`.

### Walidacja lokalna (bez sieci)

```bash
python L04/validate_declaration.py
```

---

## Dokumentacja SPK

- Główna: `https://hub.ag3nts.org/dane/doc/index.md`
- Wzór deklaracji: `zalacznik-E.md`
- Mapa sieci: `zalacznik-F.md`
- Trasy wyłączone: `trasy-wylaczone.png` (obraz)
- Historia zmian: `zalacznik-H.md`
- Opłaty za dodatkowe wagony: `dodatkowe-wagony.md`

