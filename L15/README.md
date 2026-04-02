# L15 — Savethem (optymalna trasa do Skolwina)

## Zadanie

Zbudować agenta, który wytyczy optymalną trasę dla posłańca z bazy do miasta Skolwin
na nieznanym terenie. Agent musi najpierw odkryć dostępne narzędzia poprzez API wyszukiwarki narzędzi,
a następnie zebrać dane o mapie, pojazdach i zasadach ruchu, by wyliczyć najlepszą trasę
przy ograniczonych zasobach: 10 porcji jedzenia i 10 jednostek paliwa.

- **Nazwa zadania:** `savethem`
- **Weryfikacja:** `POST https://hub.ag3nts.org/verify`
- **Podgląd trasy:** https://hub.ag3nts.org/savethem_preview.html
- **API wyszukiwarki narzędzi:** `POST https://hub.ag3nts.org/api/toolsearch`

## Mechanika

### Zasoby

| Zasób | Ilość |
|-------|-------|
| Jedzenie | 10 porcji |
| Paliwo | 10 jednostek |

### Pojazdy

- Do wyboru kilka pojazdów — każdy ma własne parametry spalania paliwa i zużycia jedzenia.
- Im szybszy pojazd, tym więcej paliwa zużywa na ruch; im wolniejszy, tym więcej jedzenia konsumuje posłannik.
- W każdej chwili posłannik może wysiąść i kontynuować podróż **pieszo** (brak kosztu paliwa, wyższy koszt jedzenia).

### Mapa

- Wymiary: **10 × 10 pól**.
- Zawiera przeszkody: rzeki, drzewa, kamienie, inne tereny.
- Mapa jest pobierana dynamicznie za pomocą odkrytego narzędzia.

### Ruch

Dozwolone kierunki: `up`, `down`, `left`, `right`.

### Format odpowiedzi

```json
{
  "apikey": "twoj-klucz",
  "task": "savethem",
  "answer": ["vehicle_name", "right", "right", "up", "down", "..."]
}
```

Pierwszy element tablicy to nazwa wybranego pojazdu; kolejne to kierunki ruchu.

## Odkrywanie narzędzi (toolsearch)

Wyszukiwarka narzędzi:

```json
POST https://hub.ag3nts.org/api/toolsearch
{
  "apikey": "twoj-klucz",
  "query": "I need the map of terrain"
}
```

Zwraca max. 3 najlepiej dopasowane narzędzia. Każde znalezione narzędzie obsługuje się identycznie:

```json
POST <tool_url>
{
  "apikey": "twoj-klucz",
  "query": "describe the map"
}
```

**Uwaga:** Wszystkie narzędzia porozumiewają się wyłącznie w języku **angielskim**.

### Przykładowe zapytania do toolsearch

| Cel | Przykładowe query |
|-----|------------------|
| Mapa terenu | `"map of terrain 10x10 grid"` |
| Lista pojazdów | `"available vehicles fuel consumption speed"` |
| Zasady ruchu | `"movement rules terrain costs"` |
| Parametry paliwa / jedzenia | `"fuel food resource cost per move"` |
| Start i cel | `"starting position destination Skolwin"` |

## Algorytm

### Faza 1 — Odkrywanie narzędzi

1. Wyślij do toolsearch kilka zapytań w języku angielskim pokrywających: mapę, pojazdy, zasady terenu.
2. Dla każdego zwróconego narzędzia zapamiętaj URL i opis.
3. Odpytaj każde narzędzie szczegółowymi zapytaniami, by zebrać pełne dane.
4. Zapisz mapę wraz z legendą - może być w pliku txt lub innym

### Faza 2 — Analiza danych

1. Sparsuj mapę 10×10 — zidentyfikuj pozycję startową, cel (Skolwin) i przeszkody.
2. Pobierz listę pojazdów: nazwa, koszt paliwa na ruch, koszt jedzenia na ruch (lub prędkość).
3. Ustal koszty wejścia na poszczególne typy terenu.
4. Dowiedz się ile razy można zmieniać pojazd i czy pokojuje on jakieś przeszkody (skały, drzewa, wodę)

### Faza 3 — Wyznaczanie trasy (nie musi być ona optymalna pod względem odległości ale ma mieścić się w zasobacg)



- **Stan:** `(wiersz, kolumna, paliwo_pozostałe, jedzenie_pozostałe, pojazd)`
- **Koszt:** minimalizacja długości trasy (liczba kroków), przy zachowaniu ograniczeń zasobów (paliwa i jedenia - tylko to nas limituje, nie pokonana droga)
- **Możliwa zmiana pojazdu:** w dowolnym polu posłannik może przesiąść się do chodzenia pieszo (czyli np z rakiety na chodzenie)
- **Warunki odcięcia:** paliwo < 0 lub jedzenie < 0 → ścieżka niedopuszczalna
- **Cel:** dotarcie do pola Skolwina z nieujemnymi zasobami

### Faza 4 — Wysyłka

1. Wyodrębnij sekwencję kroków z optymalnej ścieżki.
2. Zbuduj tablicę `["vehicle_name", "dir1", "dir2", ...]`.
3. Wyślij do `/verify` i zapisz odpowiedź w `verification_result.json`.

## Pliki

| Plik | Opis |
|------|------|
| `task.py` | Główny agentowy solver: odkrywanie narzędzi → analiza → Dijkstra → submit |
| `ui_server.py` | Lokalny serwer HTTP (stdlib `http.server`) do podglądu mapy i trasy |
| `ui.html` | Panel WWW: siatka 10×10 z nałożoną trasą i stanem zasobów |
| `verification_result.json` | Odpowiedź huba po zaliczeniu |
| `bonus_result.json` | Odpowiedź huba po znalezieniu bobrów |

## Bonus — Bobry (Beavers)

Na mapie ukryty jest teren bobrów w polu `(1,6)` (0-indexed) — bezpośrednio
przed ścianą wody. Aby aktywować bonus, wystarczy dotrzeć do tego pola trasą,
która nie musi osiągać celu.

**Trasa do bobrów** (9 kroków rakietą + 3 krochy pieszo):
```json
["rocket","up","up","up","up","up","up","right","right","right","dismount","right","right","right"]
```
- Paliwo: 9/10, Jedzenie: 8.4/10
- Serwer zwraca: `"You found beavers by the stream! {FLG:ABEAVER}"`

## Szybkie uruchomienie

```powershell
# Solver (odkrywa narzędzia, liczy trasę, wysyła do verify)
python L15/task.py

# Opcjonalnie — przeglądarka mapy i trasy
python L15/ui_server.py
# http://localhost:8015
```

## Konfiguracja

`.env` w katalogu głównym repozytorium:

```env
AI_DEVS_4_API_KEY=twoj_klucz
```

## Uwagi implementacyjne

- Toolsearch zwraca **max. 3 wyniki** — używaj precyzyjnych, angielskich zapytań i iteruj po różnych frazach kluczowych.
- Trasa może wymagać **zmiany pojazdu w trakcie** (np. szybki pojazd na otwartym terenie, pieszy przez las).
- Jeśli żadna trasa nie istnieje w ramach zasobów, sprawdź, czy nie pominięto narzędzia z kluczowymi danymi.
- Loguj wszystkie wywołania narzędzi i odpowiedzi — ułatwia debugowanie.

## Wyniki

| Rodzaj | Flaga | Plik |
|--------|-------|------|
| Główne zadanie | `{FLG:XXXXXXXXXXX}` | `verification_result.json` |
| Bonus — bobry | `{FLG:XXXXXXXXXX}` | `bonus_result.json` |
