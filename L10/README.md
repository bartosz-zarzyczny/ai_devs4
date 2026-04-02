# L10 - Drone (bombardowanie tamy i bonus Radom)

## Cel zadania

Zaprogramowac przejety dron z ladunkiem wybuchowym tak, aby polecial na misje dla elektrowni w Zarnowcu, ale finalny zrzut dotarl na tamy w sektorze oznaczonym jako `2,4`.

Po wykonaniu glownej czesci warto sprawdzic bonus. Podpowiedz "Fuksja widziała balon w Radomiu" prowadzi do lotu do Radomia z fuksjowym LED-em i wykonania zdjecia przy balonie.

- **Kod identyfikacyjny elektrowni:** `PWR6132PL`
- **Nazwa zadania:** `drone`

## Zrodla danych

| Zasob | URL |
| --- | --- |
| Dokumentacja API drona (HTML) | [https://hub.ag3nts.org/dane/drone.html](https://hub.ag3nts.org/dane/drone.html) |
| Mapa pogladowa terenu | [https://hub.ag3nts.org/data/{API_KEY}/drone.png](https://hub.ag3nts.org/data/{API_KEY}/drone.png) |

Mapa jest podzielona siatka na sektory. W tej lekcji sektor tamy to `2,4`.

## Zweryfikowany przebieg

Weryfikacja, ktora potwierdzilem w hubie, to:

```json
{
  "apikey": "{API_KEY}",
  "task": "drone",
  "answer": {
    "instructions": [
      "hardReset",
      "setDestinationObject(PWR6132PL)",
      "set(2,4)",
      "set(8m)",
      "set(engineON)",
      "set(100%)",
      "set(destroy)",
      "set(return)",
      "flyToLocation"
    ]
  }
}
```

Ta sekwencja zwraca kod `0` i flage `{FLG:XXXXXXX}`.

### Bonus Radom

Z dodatkowymi podpowiedziami sprawdzony przebieg to:

```json
{
  "apikey": "{API_KEY}",
  "task": "drone",
  "answer": {
    "instructions": [
      "hardReset",
      "setDestinationObject(PWR8406PL)",
      "set(3,1)",
      "setLed(#FF00FF)",
      "set(8m)",
      "set(engineON)",
      "set(100%)",
      "set(image)",
      "set(return)",
      "flyToLocation"
    ]
  }
}
```

Ta trasa zwraca kod `876` i komunikat o balonie w Radomiu. W zrzucie zdjecia znalazlem bonusowa flage `{FLG:XXXXXXXXXXX}`.

## Co trzeba zrobic

### 1. Przeanalizowac mape (vision)

- Wyslac URL mapy (`drone.png`) do modelu vision.
- Policzac kolumny i wiersze siatki.
- Zlokalizowac sektor z tama.
- Zanotowac numer kolumny i wiersza sektora tamy (indeksowanie od 1).

> W tej lekcji sektor tamy zostal potwierdzony jako `2,4`.

### 2. Przeczytac dokumentacje API drona

- Pobierac/przeanalizowac HTML z [https://hub.ag3nts.org/dane/drone.html](https://hub.ag3nts.org/dane/drone.html).
- Zidentyfikowac wymagane instrukcje do sterowania dronem.

> Dokumentacja ma wiele kolidujacych nazw funkcji, wiec warto ograniczyc sie do polecen rzeczywiscie potrzebnych: `setDestinationObject`, `set(x,y)`, `set(xm)`, `set(mode)`, `set(power)`, `setLed(color)`, `set(image|video)`, `set(return)` i `flyToLocation`.

### 3. Przygotowac sekwencje instrukcji

- Zbudowac tablice instrukcji kierujacych dron na wlasciwy sektor.
- Dla tego zadania sprawdzony zestaw to:
  - `hardReset`
  - `setDestinationObject(PWR6132PL)`
  - `set(2,4)`
  - `set(8m)`
  - `set(engineON)`
  - `set(100%)`
  - `set(image)`
  - `set(return)`
  - `flyToLocation`

- Dla bonusu Radom sprawdzony zestaw to:
  - `hardReset`
  - `setDestinationObject(PWR8406PL)`
  - `set(3,1)`
  - `setLed(#FF00FF)`
  - `set(8m)`
  - `set(engineON)`
  - `set(100%)`
  - `set(image)`
  - `set(return)`
  - `flyToLocation`

### 4. Wyslac instrukcje do `/verify`

- Wyslac payload z instrukcjami na endpoint.
- Przeczytac odpowiedz API.

### 5. Iterowac na podstawie feedbacku

- Jesli API zwroci blad, przeczytac komunikat, dostosowac instrukcje i wyslac ponownie.
- To zadanie dobrze reaguje na iteracyjny tryb pracy.

### 6. Reset

- Jesli konfiguracja drona zostala rozjechana przez poprzednie proby, uzyc `hardReset`.

## Wskazowki

- **Dwuetapowe podejscie:** najpierw vision do analizy mapy, potem petla agentowa z tekstowym dopinaniem payloadu.
- **Minimalny zestaw instrukcji:** nie dodawac nic ponad wymagane kroki.
- **Wysokosc lotu:** ponizej `8m` teren jest zbyt nisko i wyzwala blad kolizji z drzewami.
- **Powrot jest wymagany:** bez `set(return)` dron nie przechodzi calej sciezki.
- **Bonus Radom:** fuksjowy LED (`#FF00FF`) jest istotny dla podpowiedzi o balonie w Radomiu.

## Pliki

- [L10/task.py](task.py) - glowny solver i submit.
- [L10/drone_solver.py](drone_solver.py) - logika analizy mapy, budowy instrukcji i weryfikacji.
- [L10/ui_server.py](ui_server.py) - lokalny serwer HTTP.
- [L10/ui.html](ui.html) - panel WWW.
- [L10/verification_result.json](verification_result.json) - ostatnia odpowiedz z huba.

## Uruchomienie

```bash
python L10/task.py
python L10/ui_server.py
```
