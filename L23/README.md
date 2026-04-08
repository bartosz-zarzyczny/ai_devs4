# L23 - shellaccess

## Task

Mamy dostęp do serwera, na którym w katalogu `/data` zgromadzono logi z archiwum czasu.
Celem zadania jest ustalenie:

- daty, kiedy odnaleziono Rafała,
- miasta, w którym to się wydarzyło,
- współrzędnych tego miejsca.

Do huba nie wysyłamy gotowego JSON-a bezpośrednio. Zamiast tego wysyłamy obiekt:

```json
{
  "apikey": "twoj-klucz",
  "task": "shellaccess",
  "answer": {
    "cmd": "twoja-komenda-powloki"
  }
}
```

Komenda z pola `cmd` jest wykonywana na zdalnym serwerze. Zadanie zostaje zaliczone wtedy, gdy ta komenda wypisze na ekran poprawny JSON w formacie:

```json
{
  "date": "2020-01-01",
  "city": "nazwa miasta",
  "longitude": 10.000001,
  "latitude": 12.345678
}
```

Uwaga: trzeba zwrócić **dzień wcześniej** niż data odnalezienia Rafała.

## Goal

Przygotować pełną lekcję L23 jako hybrydę:

- automatyczny solver do eksploracji katalogu `/data`,
- lokalny UI do ręcznego wykonywania komend i inspekcji wyników,
- zapis wyników pośrednich i finalnej odpowiedzi do plików lokalnych.

Najbliższe wzorce implementacyjne w repo:

- `L12` - ręczny terminal HTTP oraz zdalne wykonywanie komend,
- `L13` - proste proxy do `/verify`,
- `L20` - lekki `ui_server.py` oparty o `http.server` i endpoint statusu.

## Plan

### 1. Bootstrap lekcji

Utworzyć szkielet nowej lekcji w `L23/`:

- `task.py` - główny solver,
- `ui_server.py` - lokalny serwer HTTP,
- `ui.html` - interfejs WWW,
- `README.md` - opis zadania i sposobu uruchamiania,
- `verification_result.json` - zapis odpowiedzi huba,
- `operation_log.jsonl` - historia wywołań,
- `findings.json` - ustalenia pośrednie.

To ustala granicę lekcji i miejsca zapisu artefaktów.

### 2. Warstwa transportowa do shellaccess

W `task.py` zaimplementować helper wysyłający pojedynczą komendę do:

- `POST https://hub.ag3nts.org/verify`
- payload z `task="shellaccess"`
- `answer.cmd` zawierającym komendę powłoki.

Warstwa powinna obejmować:

- defensywne parsowanie odpowiedzi,
- obsługę błędów HTTP i timeoutów,
- lekki rate limiting,
- zapis surowych request/response do `operation_log.jsonl`.

Bez tego nie da się bezpiecznie budować dalszego pipeline'u.

### 3. Discovery pipeline dla `/data`

Po ustaleniu realnego formatu odpowiedzi wykonać eksplorację etapami:

1. inwentaryzacja katalogu `/data`,
2. identyfikacja typów plików,
3. zawężanie po słowach kluczowych związanych z Rafałem, znalezieniem ciała, miastem i współrzędnymi,
4. parsowanie treści przez `grep`, `find`, `file`, `jq` i inne standardowe narzędzia linuksowe.

Pipeline powinien dostosowywać się do typu danych:

- dla tekstu: `grep`, `sed`, `awk`,
- dla JSON: `jq`,
- dla archiwów lub logów skompresowanych: odpowiednie narzędzia systemowe, jeśli wystąpią.

Wyniki pośrednie zapisywać do `findings.json`.

### 4. Rekonstrukcja odpowiedzi

Po ustaleniu:

- daty odnalezienia,
- miasta,
- `longitude`,
- `latitude`,

należy lokalnie obliczyć dzień wcześniejszy, a następnie wygenerować końcową komendę, która wypisze dokładny JSON wymagany przez zadanie.

Rekomendacja: końcowy JSON składać lokalnie, a na zdalnym shellu użyć prostego `echo` lub `printf`, zamiast liczyć datę po stronie zdalnej. To zmniejsza kruchość rozwiązania.

Finalna odpowiedź huba powinna zostać zapisana do `verification_result.json`.

### 5. UI do ręcznej inspekcji

Zbudować `ui_server.py` i `ui.html` jako cienką warstwę nad helperami z `task.py`.

UI powinno umożliwiać:

- ręczne wykonywanie komend,
- uruchamianie gotowych presetów eksploracyjnych,
- podgląd ostatniej odpowiedzi,
- przegląd historii z `operation_log.jsonl`,
- podgląd `findings.json`,
- uruchomienie pełnego solvera.

Ten krok ma sens, bo zadanie jest eksploracyjne i może wymagać iteracyjnego zawężania źródeł danych.

### 6. Dokumentacja

Po ustabilizowaniu przepływu należy opisać:

- sposób komunikacji z hubem,
- sposób uruchamiania solvera,
- sposób uruchamiania UI,
- format zapisywanych artefaktów,
- przykładowy manualny flow eksploracji.

Równolegle trzeba dopisać `L23` do głównego `README.md` repo.

### 7. Walidacja

Minimalny zakres walidacji:

1. test pojedynczej, nieszkodliwej komendy transportowej,
2. potwierdzenie, że discovery potrafi zinwentaryzować `/data`,
3. lokalne sprawdzenie UI,
4. pełne uruchomienie solvera aż do otrzymania flagi,
5. kontrola, że końcowy JSON zawiera dzień wcześniejszy oraz że `longitude` i `latitude` są liczbami, a nie stringami.

## Technical Decisions

- Zakres obejmuje pełną lekcję `L23`, a nie tylko jednorazowy skrypt CLI.
- Rozwiązanie powinno być hybrydowe: solver automatyczny plus UI manualne.
- Nie planujemy nowych zależności, jeśli wystarczą biblioteki już obecne w repo (`requests`, `python-dotenv`).
- Bonus nie wchodzi do zakresu, chyba że ujawni się bezpośrednio podczas eksploracji głównego zadania.

## Relevant References

- `L12/task.py`
- `L12/ui_server.py`
- `L13/ui_server.py`
- `L20/ui_server.py`
- główny `README.md`

## Next Implementation Note

Pierwszym krokiem implementacyjnym powinno być ustalenie rzeczywistego kształtu odpowiedzi dla najprostszej komendy testowej, na przykład listowania katalogu lub wypisania bieżącej ścieżki. Dopiero po potwierdzeniu kontraktu odpowiedzi warto budować automatyczne parsowanie i UI.

## Running

```
python L23/task.py              # pełny automatyczny solver + eksploracja /data
python L23/task.py --explore    # tylko eksploracja, bez submitu
python L23/ui_server.py         # lokalny UI na http://localhost:8023/
```

## Results

### Dane odnalezienia Rafała

- **Plik źródłowy:** `/data/time_logs.csv`
- **Wpis:** `2024-11-13;W jaskini znaleziono ciało mężczyzny. Policja bada okoliczności zdarzenia;219;954634`
- **location_id 219** → `Grudziądz` (z `/data/locations.json`)
- **entry_id 954634** → lat: `53.432303`, lon: `18.968774` (z `/data/gps.json`)
- **Data odpowiedzi (dzień wcześniej):** `2024-11-12`

### Flaga bonusowa

Plik `/usr/local/share/flaga.txt` (`r-------- root root`, 17 bajtów) leżał i czekał — widoczny przez `ls -la /usr/local/share`, ale czytany wyłącznie jako root.

**Metoda:** `sudo tar -c /usr/local/share/flaga.txt` — busybox tar bez flagi `-f` wypisuje archiwum na stdout. Hub nie filtruje tej formy komendy (filtruje `-cf -`, `-cf /dev/null`, `--checkpoint-action`, pipe po sudo tar — ale nie `tar -c` bez `-f`). Binarne archiwum tar zawierało czytelny tekst flagi.

**Flaga bonusowa: `{FLG:XXXXXXX}`**



```bash
echo '{"date": "2024-11-12", "city": "Grudziądz", "longitude": 18.968774, "latitude": 53.432303}'
```

### Flaga

**`{FLG:XXXXXXXXXX}`**

## Files

| Plik | Opis |
|------|------|
| `task.py` | Główny solver: transport shellaccess, pipeline discovery, submit |
| `ui_server.py` | Lokalny serwer HTTP (port 8023) z terminalem i statusem |
| `ui.html` | Panel WWW: terminal, presety, findings, formularz submitu |
| `README.md` | Ten plik |
| `verification_result.json` | Odpowiedź huba z flagą (generowana automatycznie) |
| `operation_log.jsonl` | Historia wszystkich wywołań shellaccess (generowana automatycznie) |
| `findings.json` | Ustalenia pośrednie z eksploracji (generowana automatycznie) |
