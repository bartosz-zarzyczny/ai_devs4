# L17 — windpower (Harmonogram turbiny wiatrowej)

## Opis zadania

Zaprogramowanie harmonogramu pracy turbiny wiatrowej tak, aby wygenerować moc konieczną do uruchomienia elektrowni — w ciągu **40 sekund** od otwarcia okna serwisowego.

- **Nazwa zadania:** `windpower`
- **Endpoint:** `POST https://hub.ag3nts.org/verify`
- **Format żądania:**

```json
{
  "apikey": "TWOJ_KLUCZ",
  "task": "windpower",
  "answer": {
    "action": "..."
  }
}
```

---

## Limit czasowy i wymaganie równoległości

Większość funkcji API działa **asynchronicznie** — wysyłasz żądanie kolejkujące zadanie,
a wynik odbierasz później przez `action: getResult`. Odpowiedzi przychodzą w **losowej kolejności**.

Każdy wygenerowany raport da się pobrać **tylko raz**. Sekwencyjne wywołania przekroczą 40 sekund — niezbędne jest równoległe kolejkowanie raportów (np. `asyncio.gather` lub wątki).

---

## Dostępne akcje API

| Akcja | Opis | Tryb |
| --- | --- | --- |
| `help` | Zwraca dokumentację dostępnych akcji | sync |
| `start` | Otwiera 40-sekundowe okno serwisowe | sync |
| `get` | Pobiera dane dla parametru `weather`, `turbinecheck`, `powerplantcheck` lub `documentation` | `documentation` sync, reszta async |
| `unlockCodeGenerator` | Kolejkuje wygenerowanie kodu podpisu MD5 dla wpisu konfiguracji | async |
| `getResult` | Odbiera wynik najstarszego oczekującego raportu | sync |
| `config` | Wysyła harmonogram konfiguracji turbiny | sync |
| `done` | Weryfikuje konfigurację i zwraca flagę | sync |

---

## Plan wykonania

### Krok 1 — Eksploracja (`help`)

Przed uruchomieniem zadania wywołaj `help`, aby poznać szczegółowe parametry każdej akcji.

```json
{
  "apikey": "TWOJ_KLUCZ",
  "task": "windpower",
  "answer": { "action": "help" }
}
```

### Krok 2 — Otwarcie okna serwisowego (`start`)

Uruchomienie okna — od tej chwili masz **40 sekund**.

```json
{
  "apikey": "TWOJ_KLUCZ",
  "task": "windpower",
  "answer": { "action": "start" }
}
```

### Krok 3 — Równoległe kolejkowanie raportów

Wyślij **jednocześnie** (przez `asyncio.gather` lub wątki) trzy żądania kolejkujące:

```python
import asyncio, aiohttp

async def queue_all(session, apikey):
    tasks = [
    post(session, apikey, "get", param="weather"),
    post(session, apikey, "get", param="turbinecheck"),
    post(session, apikey, "get", param="powerplantcheck"),
    ]
    return await asyncio.gather(*tasks)
```

### Krok 4 — Odbieranie raportów (`getResult`)

Iteracyjnie odpytuj `getResult` aż odbierzesz wszystkie trzy raporty.
Odpowiedzi przychodzą w losowej kolejności — identyfikuj je po polu `type` lub podobnym.

```json
{
  "apikey": "TWOJ_KLUCZ",
  "task": "windpower",
  "answer": { "action": "getResult" }
}
```

### Krok 5 — Analiza danych

#### Identyfikacja wichur (wiatr > limit turbiny)

Z `get documentation` odczytaj maksymalną wytrzymałość wiatraka (`cutoffWindMs = 14`).
Z `get weather` wyznacz wszystkie przedziały godzinowe, gdzie prędkość wiatru przekracza ten limit.

Dla każdego takiego przedziału:

- `pitchAngle` = kąt parowania łopat (feather, np. 90°) — turbina nie stawia oporu
- `turbineMode` = `idle` — brak produkcji prądu

#### Wyznaczenie okna produkcji energii

Z `get powerplantcheck` odczytaj brakującą moc (`powerDeficitKw`).
Wybierz przedział(y), w których wiatr jest wystarczający do produkcji i nie ma wichury.
Optymalny punkt to maksymalna prędkość wiatru poniżej limitu turbiny:

- `pitchAngle` = 0 (pełna ekspozycja łopat)
- `turbineMode` = `production`

> **Uwaga:** Wszystkie timestampy w konfiguracji zaokrąglaj do **pełnych godzin**
> (minuty i sekundy = `00`), format: `YYYY-MM-DD HH:00:00`.
>
> W praktyce API wymaga **dokładnie 4 punktów konfiguracji**: 3 zabezpieczenia przed wichurami oraz 1 punkt produkcyjny.

### Krok 6 — Generowanie kodów podpisu (`unlockCodeGenerator`)

Każdy wpis konfiguracyjny musi mieć unikalny `unlockCode` wygenerowany przez API.
Kolejkuj generowanie **równolegle** dla wszystkich wpisów:

```python
async def queue_unlock_codes(session, apikey, config_entries):
    tasks = [
        post(session, apikey, "unlockCodeGenerator", entry_data)
        for entry_data in config_entries
    ]
    return await asyncio.gather(*tasks)
```

Następnie odbierz kody przez `getResult` (tyle razy, ile wpisów).

### Krok 7 — Wysłanie konfiguracji zbiorczej (`config`)

Wyślij całą konfigurację **jednym żądaniem** używając formatu `configs`:

```json
{
  "apikey": "TWOJ_KLUCZ",
  "task": "windpower",
  "answer": {
    "action": "config",
    "configs": {
      "2026-03-24 20:00:00": {
        "pitchAngle": 90,
        "turbineMode": "idle",
        "unlockCode": "md5-podpis-1"
      },
      "2026-03-24 22:00:00": {
        "pitchAngle": 0,
        "turbineMode": "production",
        "unlockCode": "md5-podpis-2"
      }
    }
  }
}
```

### Krok 8 — Test turbiny (`get` z `param=turbinecheck`)

Wymagany przed finalną weryfikacją:

```json
{
  "apikey": "TWOJ_KLUCZ",
  "task": "windpower",
  "answer": {
    "action": "get",
    "param": "turbinecheck"
  }
}
```

Nie trzeba czekać na wynik `turbinecheck` przed `done`. Samo poprawne zlecenie testu przed walidacją wystarcza i pozwala zmieścić się w 40 sekundach.

### Krok 9 — Finalna weryfikacja (`done`)

```json
{
  "apikey": "TWOJ_KLUCZ",
  "task": "windpower",
  "answer": { "action": "done" }
}
```

Jeśli konfiguracja jest poprawna i zmieścisz się w 40 sekundach, Centrala zwróci flagę `{FLG:...}`.

---

## Reguły konfiguracji turbiny

| Sytuacja | `pitchAngle` | `turbineMode` |
| --- | --- | --- |
| Wichura (wiatr > limit) | feather (90°) | `idle` |
| Produkcja energii | 0° (pełna ekspozycja) | `production` |
| Pozostałe godziny | bez dodatkowego wpisu | stan z poprzedniej konfiguracji |

---

## Pliki

| Plik | Opis |
| --- | --- |
| `task.py` | Główny solver: `start` → kolejkowanie → analiza → config → check → `done` |
| `ui_server.py` | Lokalny serwer HTTP (stdlib `http.server`) z podglądem kroków |
| `ui.html` | Panel przeglądarki do inspekcji raportów i konfiguracji |
| `verification_result.json` | Zapisana odpowiedź Centrali po `done` |

## Uruchomienie

```powershell
# Z katalogu głównego repozytorium
python L17/task.py
```

Lub z podglądem krok po kroku:

```powershell
python L17/ui_server.py
# Otwórz http://localhost:8017
```

---

## Wynik

Po poprawnym wykonaniu flaga zapisywana jest do `verification_result.json`.

Zweryfikowany wariant w tym repozytorium używa 4 punktów:

- `2026-04-01 18:00:00` — `pitchAngle=90`, `turbineMode=idle`
- `2026-04-01 20:00:00` — `pitchAngle=0`, `turbineMode=production`
- `2026-04-04 18:00:00` — `pitchAngle=90`, `turbineMode=idle`
- `2026-04-05 18:00:00` — `pitchAngle=90`, `turbineMode=idle`

## Bonus — lustro czasu i wiatru

Dodatkowa zagadka nie wymaga `config` ani `done`. Wystarczą 3 kroki:

1. `start`
2. Trzykrotne `unlockCodeGenerator`
3. `getResult` aż pojawi się flaga

Sekwencja jest palindromiczna i używa tego samego palindromicznego czasu dla wszystkich trzech wywołań:

```json
{
  "startDate": "2020-02-02",
  "startHour": "20:11:02",
  "pitchAngle": 0
}
```

Wysyłane wartości `windMs` tworzą lustro:

- `4.4`
- `5.5`
- `4.4`

Czyli komplet trzech wywołań ma postać:

```json
{
  "apikey": "TWOJ_KLUCZ",
  "task": "windpower",
  "answer": {
    "action": "unlockCodeGenerator",
    "startDate": "2020-02-02",
    "startHour": "20:11:02",
    "windMs": 4.4,
    "pitchAngle": 0
  }
}
```

Drugie wywołanie różni się tylko `windMs=5.5`, a trzecie wraca do `4.4`.

Przy tej sekwencji `getResult` zwraca bonusową flagę bezpośrednio w polu `unlockCode`:

`{FLG:XXXXXXXXX}`

Uruchomienie:

```powershell
python L17/bonus_probe.py
```

Wynik zapisuje się do `bonus_result.json`.
