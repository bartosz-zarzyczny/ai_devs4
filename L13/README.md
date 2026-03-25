# L13 — Reactor (sterowanie robotem transportującym)

## Zadanie

Twoim zadaniem jest doprowadzenie robota transportującego urządzenie chłodzące w pobliże reaktora.

Do sterowania robotem służy specjalnie przygotowane API, które przyjmuje polecenia: `start`, `reset`, `left`, `wait` oraz `right`. Możesz wysłać tylko jedno polecenie jednocześnie.

Zadanie uznajemy za zaliczone, jeśli robot przejdzie przez całą mapę, nie będąc przy tym zgniecionym przez elementy reaktora. Bloczki reaktora poruszają się w górę i w dół, a status ich aktualnego kierunku, podobnie jak ich pozycja, są zwracane przez API.

Napisz aplikację, która na podstawie aktualnej sytuacji na planszy będzie decydowała, jakie kroki powinien podjąć robot.

Graficzny podgląd sytuacji wewnątrz reaktora: https://hub.ag3nts.org/reactor_preview.html

**Nazwa zadania:** `reactor`

## Komendy API

Komendy dla robota wysyłasz do `/verify`:

```json
{
  "apikey": "tutaj-twoj-klucz",
  "task": "reactor",
  "answer": {
    "command": "start"
  }
}
```

Dostępne komendy: `start`, `reset`, `left`, `wait`, `right`.

## Mechanika zadania

- Plansza ma wymiary **7 na 5 pól**.
- Robot porusza się zawsze po **najniższej kondygnacji** — pozycja startowa to kolumna 1, wiersz 5.
- Punkt docelowy (instalacja modułu chłodzenia) to **kolumna 7, wiersz 5**.
- Każdy blok reaktora zajmuje dokładnie **2 pola** i porusza się cyklicznie góra/dół.
  - Gdy dojdzie do pozycji skrajnie wysokiej, zaczyna wracać na dół.
  - Gdy osiągnie pozycję najniższą, wraca do góry.
- Bloki poruszają się **tylko gdy wydajesz polecenia** — odczekanie bez wysłania komendy nie zmienia stanu planszy.
- Aby zmienić stan planszy bez poruszania robotem, wyślij komendę `wait`.

## Oznaczenia na mapie

| Symbol | Znaczenie |
|--------|-----------|
| `P`    | Pozycja startowa robota |
| `G`    | Cel (miejsce instalacji modułu chłodzenia) |
| `B`    | Bloki reaktora |
| `.`    | Puste pole |

## Algorytm

1. Zawsze zaczynaj od wysłania komendy `start`.
2. Po każdej komendzie pobierz aktualny stan planszy z odpowiedzi API.
3. Wyznacz pozycje bloków na podstawie siatki `board` (0-indeksowane, niezawodne).
4. Pobierz kierunek ruchu każdego bloku z pola `blocks` — z automatyczną detekcją offsetu (API zwraca 1-indeksowane kolumny).
5. Podejmij decyzję:
   - **`right`** — następna kolumna jest wolna **teraz** i **po następnym kroku**.
   - **`wait`** — bieżąca kolumna będzie bezpieczna po następnym kroku.
   - **`left`** — odwrót, gdy obie powyższe opcje są niebezpieczne.
6. Jeśli API zwróci 409 (robot zgnieciony) — wyślij `reset` i zacznij od nowa.
7. Powtarzaj kroki 2–6 aż robot dotrze do celu (kolumna 7, wiersz 5).

## Uwagi implementacyjne

- API zwraca kolumny i wiersze bloków **1-indeksowane**, ale siatkę `board` **0-indeksowaną**.
  Solver wykrywa offset automatycznie, porównując nakładanie się zbiorów kolumn.
- Śmierć robota zwraca HTTP 409 — solver obsługuje ją bez crashu i restartuje sesję.
- Między poleceniami dodano opóźnienie (`CMD_DELAY = 0.5s`) aby uniknąć rate-limitingu.

## Pliki

| Plik | Opis |
|------|------|
| `task.py` | Główny solver — automatyczna pętla sterowania robotem |
| `ui_server.py` | Lokalny serwer HTTP do podglądu stanu planszy |
| `ui.html` | Panel WWW z wizualizacją planszy |
| `verification_result.json` | Odpowiedź huba po zaliczeniu zadania |

## Szybkie uruchomienie

```powershell
python L13/task.py
python L13/ui_server.py
```

## Konfiguracja

Wymagana zmienna środowiskowa w `.env` (katalogu głównym):

```env
AI_DEVS_4_API_KEY=twoj_klucz_ai_devs
```

## Wyniki

- Flaga: `{FLG:XXXXXXXX}`
- Robot dotarł do celu w **11 krokach** (bez żadnej śmierci).
- Wynik zapisany w `verification_result.json`.
