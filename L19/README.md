# L19 - filesystem

## Opis zadania

Logiczne uporzadkowanie notatek Natana w wirtualnym systemie plikow.
Nalezy ustalic, ktore miasta braly udzial w handlu, jakie osoby odpowiadaly
za handel w konkretnych miastach oraz ktore towary byly przez kogo sprzedawane.

- Nazwa zadania: `filesystem`
- Endpoint: `POST https://hub.ag3nts.org/verify`
- Podglad systemu plikow: https://hub.ag3nts.org/filesystem_preview.html
- Notatki Natana: https://hub.ag3nts.org/dane/natan_notes.zip

Format dostepnych operacji (przyklad):

```json
{
  "apikey": "TWOJ_KLUCZ",
  "task": "filesystem",
  "answer": {
    "action": "createFile",
    "path": "/plik1",
    "content": "Test1"
  }
}
```

Tryb batch (wiele operacji w jednym requeście):

```json
{
  "apikey": "TWOJ_KLUCZ",
  "task": "filesystem",
  "answer": [
    { "action": "createFile", "path": "/plik1", "content": "Test1" },
    { "action": "createFile", "path": "/plik2", "content": "Test2" }
  ]
}
```

---

## Wymagana struktura filesystemu

### `/miasta/<miasto>`
Plik JSON z towarami, jakie potrzebuje dane miasto i ich iloscia (bez jednostek):

```json
{ "wegiel": 500, "ropa": 200 }
```

### `/osoby/<Imie_Nazwisko>`
Imie i nazwisko osoby oraz link markdown do miasta, ktorym zarzadza:

```
Jan Kowalski
[Warszawa](/miasta/Warszawa)
```

### `/towary/<towar>`
Link markdown do miasta oferujacego ten towar (nazwa w mianowniku l.poj.):

```
[Warszawa](/miasta/Warszawa)
```

**Uwaga:** W nazwach plikow i tresci JSON nie uzywamy polskich znakow.

---

## Plan wykonania

### Faza 1 - Setup

1. Utworz `L19/task.py` z zaladowaniem `.env`, funkcja pomocnicza `post_answer()`
   i transliteratorem polskich znakow (a->a, c->c, e->e, l->l, n->n, o->o, s->s, z/z->z).
2. Opcjonalnie: `L19/ui_server.py` + `L19/ui.html` do podgladu wyekstrahowanych danych.

### Faza 2 - Pobranie danych

3. Pobierz `https://hub.ag3nts.org/dane/natan_notes.zip` przez `requests.get()` (binarny ZIP).
4. Wyodrebnij zawartosc w pamieci (`zipfile.ZipFile`) i odczytaj wszystkie pliki tekstowe.
5. Wyolaj akcje `help` przez API, zeby potwierdzic dostepne akcje i format odpowiedzi.

### Faza 3 - Parsowanie LLM

6. Wyslij tresc notatek do modelu (OpenRouter) z ustrukturyzowanym promptem, ktory wyodrebnia:
   - **Miasta** -> wymagane towary z ilosciami (forma mianownikowa, bez jednostek)
   - **Osoby** -> imie + nazwisko oraz miasto, ktorym zarzadzaja
   - **Towary na sprzedaz** -> nazwa w mianowniku l.p. + miasto oferujace towar
7. Zapisz wyodrebnione dane do `L19/natan_data.json` (checkpoint).

### Faza 4 - Budowa filesystemu (batch_mode)

8. Przygotuj liste operacji w **jednym** requeście:
   - `reset` - wyczys istniejaca strukture
   - `createDir /miasta`, `createDir /osoby`, `createDir /towary`
   - `createFile /miasta/<miasto_ascii>` - tresc: JSON `{"towar_ascii": ilosc, ...}`
   - `createFile /osoby/<Imie_Nazwisko>` - tresc: `"Imie Nazwisko\n[Miasto](/miasta/miasto_ascii)"`
   - `createFile /towary/<towar_ascii>` - tresc: `"[Miasto](/miasta/miasto_ascii)"`
9. Wyslij batch i zaloguj odpowiedz.

### Faza 5 - Weryfikacja

10. Wyolaj akcje `done`.
11. Zapisz odpowiedz do `L19/verification_result.json`.

---

## Pliki

| Plik                           | Opis                                              |
|-------------------------------|---------------------------------------------------|
| `task.py`                     | Glowny solver: pobieranie ZIP, LLM, build FS, submit |
| `natan_data.json`             | Dane wyodrebnione przez LLM (checkpoint)          |
| `verification_result.json`    | Odpowiedz huba po wywolaniu `done`                |
| `ui_server.py` / `ui.html`   | Opcjonalny podglad w przegladarce                 |

---

## Uruchomienie

```powershell
# Pelnny run: parse + build + done -> flaga w konsoli i w verification_result.json
python L19/task.py

# Tylko help API
python L19/task.py --help-api

# Tylko parsowanie LLM (zapisuje natan_data.json)
python L19/task.py --parse

# Tylko budowa filesystemu (wymaga natan_data.json)
python L19/task.py --build
```

---

## Kluczowe ograniczenia

- Brak polskich znakow w nazwach plikow i tresci JSON
- Nazwy miast i towarow w **mianowniku**
- Nazwy plikow w `/osoby/` uzywaja podkreslenia zamiast spacji: `Jan_Kowalski`
- Format linku markdown: `[Nazwa Miasta](/miasta/nazwa_miasta)`
- Ilosci towarow jako liczby **bez jednostek** w JSON
