# L16 — OKOeditor

## Zadanie

Twoim celem jest wprowadzenie zmian w Centrum Operacyjnym OKO wyłącznie przez API Centrali. Nie wolno wykonywac zadnych recznych zmian w panelu operatora.

- **Nazwa zadania:** `okoeditor`
- **Panel operatora:** https://oko.ag3nts.org/
- **Login:** `Zofia`
- **Haslo:** `Zofia2026!`
- **Weryfikacja:** `POST https://hub.ag3nts.org/verify`

## Start

Najpierw sprawdz dostepne akcje API Centrali przez endpoint `/verify`:

```json
{
  "apikey": "twoj_klucz",
  "task": "okoeditor",
  "answer": { "action": "help" }
}
```

Odpowiedz powinna opisac dostepne akcje, formaty danych i ewentualne ograniczenia.
## Przygotowanie
1. Zaloguj się na stornę https://oko.ag3nts.org/
2. Zapisz do pliku zawartości Incydentów, Notatek, Zadań
3. Uzyj tych wiadomości w kolejnych zadaniach

## Cel operacyjny

Wykonaj wszystkie zmiany w tej kolejnosci:

1. Zmien klasyfikacje raportu o miescie Skolwin tak, aby nie byl to raport o widzianych pojazdach i ludziach, tylko o zwierzetach.
2. Na liscie zadan znajdz zadanie zwiazane ze Skolwin i oznacz je jako wykonane. W tresci wpisz, ze widziano tam zwierzeta, na przyklad bobry.
3. Dodaj raport o wykryciu ruchu ludzi w okolicach miasta Komarowo na liste incydentow, aby odciagnac uwage operatorow.
4. Po potwierdzeniu zmian wywolaj akcje `done`.

## Zalecany przebieg

1. Uwierzytelnij sie w panelu operatora, jesli chcesz porownac dane widoczne w UI z tym, co zwraca API.
2. Pobierz opis API przez `action: help` i ustal, jakie pola sa wymagane do edycji raportow, zadan i incydentow.
3. Wykonuj tylko operacje backendowe przez Centrala `/verify`; panel webowy traktuj jako miejsce podgladu stanu.
4. Po kazdej zmianie sprawdz, czy API zwraca sukces i czy rekord rzeczywiscie zostal zaktualizowany.
5. Gdy wszystkie trzy zmiany beda gotowe, wyslij `action: done`.

## Przykladowy schemat pracy

```json
{
  "apikey": "twoj_klucz",
  "task": "okoeditor",
  "answer": {
    "action": "update_report",
    "target": "Skolwin",
    "classification": "animals"
  }
}
```

```json
{
  "apikey": "twoj_klucz",
  "task": "okoeditor",
  "answer": {
    "action": "update_task",
    "target": "Skolwin",
    "done": true,
    "note": "Widziano bobry i inne zwierzeta."
  }
}
```

```json
{
  "apikey": "twoj_klucz",
  "task": "okoeditor",
  "answer": {
    "action": "add_incident",
    "city": "Komarowo",
    "description": "Wykryto ruch ludzi w okolicach miasta."
  }
}
```

```json
{
  "apikey": "twoj_klucz",
  "task": "okoeditor",
  "answer": { "action": "done" }
}
```

## Uruchomienie

### Rozwiązanie (automatyczne wykonanie)
```powershell
python L16/task.py
```

### Lokalny UI do inspekcji kroku po kroku
```powershell
python L16/ui_server.py
```

Następnie otwórz przeglądarkę na `http://localhost:8080` — UI pozwoli Ci na:
- Wizualizację każdego kroku operacji
- Wykonanie operacji pojedynczo z przyciskami
- Podgląd odpowiedzi API w formacie JSON
- Potwierdzenie flagi po ukończeniu
- Sondowanie ukrytych wpisów użytkowników przez `sha256(candidate)`

### Szukanie ukrytych wpisów po SHA-256
```powershell
python L16/hidden_probe.py Mickiewicz Miłosz Milosz
```

Skrypt:
- loguje się do panelu OKO jako `Zofia`
- wylicza `sha256` dla każdego kandydata
- pobiera wpisy z `/uzytkownicy/<hash>`
- zwraca znalezione fragmenty i złożony wynik

## Pliki

- `task.py` — solver wykonujący wszystkie operacje sekwencyjnie
- `hidden_probe.py` — skrypt do szukania ukrytych wpisów po `sha256(candidate)`
- `ui_server.py` — lokalny serwer HTTP do inspekcji stanu (stdlib `http.server`)
- `ui.html` — interfejs przeglądarki do monitorowania operacji
- `api_help.json` — dokumentacja API
- `fetch_help.py` — skrypt do pobierania dokumentacji API

## Uwagi

- Nie wprowadzaj zmian recznie w panelu `https://oko.ag3nts.org/`.
- Najpierw zapytaj API o `help`, bo to ono definiuje wlasciwy format akcji.
- Jesli Centrala zwraca blad walidacji, popraw payload zamiast probowac obejsc ograniczenia w UI.