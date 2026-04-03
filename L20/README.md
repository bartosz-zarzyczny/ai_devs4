# L20 — foodwarehouse

Zadanie polega na uporządkowaniu pracy magazynu zywnosci i narzedzi tak, aby przygotowac poprawny komplet zamowien dla wszystkich miast wskazanych w danych wejsciowych. Rozwiazanie korzysta z API magazynu, generatora podpisow SHA1 oraz bazy SQLite dostepnej wylacznie w trybie odczytu.

Nazwa zadania: `foodwarehouse`
Endpoint verify: `https://hub.ag3nts.org/verify`
Plik zapotrzebowania miast: `https://hub.ag3nts.org/dane/food4cities.json`

## Cel

Najpierw trzeba poznac strukture danych i zaleznosci w API, potem ustalic pelne zapotrzebowanie miast oraz dane autoryzacyjne, a dopiero na koncu utworzyc poprawne zamowienia i przeprowadzic finalna weryfikacje przez `done`.

Opis zadania zawiera jedno sformulowanie o "jednym poprawnym zamowieniu", ale dalsza specyfikacja jednoznacznie wymaga przygotowania osobnych zamowien dla kazdego miasta z pliku JSON. To wymaganie nalezy traktowac jako operacyjne zrodlo prawdy.

## Wynik

- Flaga glowna: `{FLG:JUSTEATIT}`
- Bonusowa odpowiedz na zagadke "Nie jestem za stary na VibeCodera?": `{FLG:VIBEAGENT}`

Finalna odpowiedz huba jest zapisana w `verification_result.json`, a odpowiedz bonusowa w `bonus_result.json`.

## Fakty ustalone podczas discovery

### Tabele w bazie

- `destinations`
- `roles`
- `users`

### Poprawny tworca zamowien

- `creatorID`: `2`
- `login`: `tgajewski`
- `birthday`: `1991-04-06`
- `role`: `Obsluga transportow`

### Mapowanie miast na destination

| Miasto | destination |
|---|---:|
| Opalino | `991828` |
| Domatowo | `761834` |
| Brudzewo | `234434` |
| Darzlubie | `676323` |
| Celbowo | `741906` |
| Mechowo | `695992` |
| Puck | `140606` |
| Karlinkowo | `707536` |

### Podpisy

Podpis nie jest staly dla uzytkownika. Trzeba go generowac osobno dla kazdego `destination` przez:

```json
{
   "tool": "signatureGenerator",
   "action": "generate",
   "login": "tgajewski",
   "birthday": "1991-04-06",
   "destination": 991828
}
```

## Bonus

Bonusowa zagadka nie wymaga dodatkowego endpointu. Odpowiedz byla ukryta w rekordach `users` z rola `Vibe Coder`.

Praktyczna metoda:

1. Pobierz rekordy `users where role = 6 order by birthday desc`.
2. Sklej pole `name_surname` ze wszystkich rekordow.
3. Zdekoduj wynik jako `base64`, a potem `gzip`.

Wynik daje komunikat z flaga `{FLG:VIBEAGENT}`.

## Glowne zasady

- Nie zgadywac wartosci `destination`, `creatorID` ani danych do podpisu.
- Najpierw wykonac discovery: `help`, analiza JSON, analiza bazy SQLite.
- Tworzyc tylko tyle zamowien, ile miast znajduje sie w `food4cities.json`.
- Kazde zamowienie musi miec poprawne `creatorID`, `destination` i `signature`.
- Towary musza zostac dopisane bez brakow i bez nadmiarow.
- W razie uszkodzenia stanu nalezy uzyc `reset`.

## API zadania

Kazde wywolanie jest wysylane do `/verify` w polu `answer` jako obiekt z polem `tool`.

Minimalny payload:

```json
{
   "apikey": "tutaj-twoj-klucz",
   "task": "foodwarehouse",
   "answer": {
      "tool": "help"
   }
}
```

### Dostepne narzedzia

- `help` — zwraca dokumentacje API i szczegoly pracy narzedzi.
- `orders` — odczyt, tworzenie, uzupelnianie i usuwanie zamowien.
- `signatureGenerator` — generowanie podpisu SHA1 na podstawie danych uzytkownika z bazy SQLite.
- `database` — odczyt tabel i danych z bazy SQLite.
- `reset` — przywrocenie poczatkowego stanu zamowien.
- `done` — koncowa weryfikacja rozwiazania.

## Przyklady wywolan

### Help

```json
{
   "apikey": "tutaj-twoj-klucz",
   "task": "foodwarehouse",
   "answer": {
      "tool": "help"
   }
}
```

### Reset

```json
{
   "apikey": "tutaj-twoj-klucz",
   "task": "foodwarehouse",
   "answer": {
      "tool": "reset"
   }
}
```

### Pobranie listy zamowien

```json
{
   "apikey": "tutaj-twoj-klucz",
   "task": "foodwarehouse",
   "answer": {
      "tool": "orders",
      "action": "get"
   }
}
```

### Utworzenie zamowienia

```json
{
   "apikey": "tutaj-twoj-klucz",
   "task": "foodwarehouse",
   "answer": {
      "tool": "orders",
      "action": "create",
      "title": "Dostawa dla Torunia",
      "creatorID": 2,
      "destination": "1234",
      "signature": "tutaj-podpis-sha1"
   }
}
```

### Dopisanie pojedynczego towaru

```json
{
   "apikey": "tutaj-twoj-klucz",
   "task": "foodwarehouse",
   "answer": {
      "tool": "orders",
      "action": "append",
      "id": "tutaj-id-zamowienia",
      "name": "woda",
      "items": 120
   }
}
```

### Dopisanie wielu towarow jednoczesnie

```json
{
   "apikey": "tutaj-twoj-klucz",
   "task": "foodwarehouse",
   "answer": {
      "tool": "orders",
      "action": "append",
      "id": "tutaj-id-zamowienia",
      "items": {
         "chleb": 45,
         "woda": 120,
         "mlotek": 6
      }
   }
}
```

Jesli dopiszesz towar juz obecny w zamowieniu, system zwiekszy jego ilosc zamiast tworzyc duplikat.

### Odczyt tabel w bazie SQLite

```json
{
   "apikey": "tutaj-twoj-klucz",
   "task": "foodwarehouse",
   "answer": {
      "tool": "database",
      "query": "show tables"
   }
}
```

### Odczyt danych z tabeli

```json
{
   "apikey": "tutaj-twoj-klucz",
   "task": "foodwarehouse",
   "answer": {
      "tool": "database",
      "query": "select * from tabela"
   }
}
```

### Finalna weryfikacja

```json
{
   "apikey": "tutaj-twoj-klucz",
   "task": "foodwarehouse",
   "answer": {
      "tool": "done"
   }
}
```

## Co trzeba ustalic

Na podstawie `food4cities.json`:

- ktore miasta biora udzial w operacji,
- jakie towary i w jakich ilosciach sa potrzebne w kazdym miescie,
- ile zamowien trzeba utworzyc.

Na podstawie API `database` i `signatureGenerator`:

- jakie tabele istnieja w bazie,
- gdzie znajduja sie dane odpowiadajace za `destination`,
- jaki `creatorID` jest poprawny dla zamowien,
- jakie dane sa potrzebne do wyliczenia podpisu przez `signatureGenerator`.

## Plan wykonania

### Faza 1 — Discovery

1. Pobierz `food4cities.json` i zapisz lokalnie jako `food4cities.json`.
2. Wywolaj `help` i zapisz odpowiedz, aby miec pelny opis narzedzi i ewentualne dodatkowe pola.
3. Wykonaj `database: show tables`.
4. Dla kazdej istotnej tabeli wykonaj `SELECT * FROM <table>` i zbuduj lokalny dump, np. `db_dump.json`.
5. Ustal mapowanie `miasto -> destination`.
6. Ustal poprawny `creatorID`.
7. Ustal dane wejsciowe wymagane przez `signatureGenerator` i przetestuj generowanie podpisu.

### Faza 2 — Przygotowanie zamowien

1. Sprawdz aktualny stan przez `orders/get`.
2. Jesli stan nie jest czysty albo chcesz powtorzyc proces od poczatku, wywolaj `reset`.
3. Dla kazdego miasta utworz jedno zamowienie przez `orders/create`.
4. Do kazdego zamowienia dopisz towary najlepiej jednym wywolaniem batch `orders/append`.
5. Po uzupelnieniu wszystkich miast ponownie wykonaj `orders/get` i porownaj stan z JSON-em wejsciowym.

### Faza 3 — Finalizacja

1. Wywolaj `done`.
2. Zapisz odpowiedz do `verification_result.json`.
3. Jesli odpowiedz wskazuje blad danych lub stanu, wykonaj `reset`, popraw discovery i powtorz proces.

## Proponowana implementacja w repo

### Pliki robocze

| Plik | Opis |
|---|---|
| `task.py` | Glowny solver: pobranie JSON, discovery DB, tworzenie zamowien, `done` |
| `ui_server.py` | Opcjonalny lokalny serwer HTTP do uruchamiania krokow i podgladu logow |
| `ui.html` | Opcjonalny panel WWW do kontroli procesu |
| `food4cities.json` | Lokalna kopia danych wejsciowych |
| `db_dump.json` | Zapis odpowiedzi z eksploracji bazy |
| `operation_log.jsonl` | Log request/response dla wywolan API |
| `verification_result.json` | Finalna odpowiedz z `/verify` |
| `bonus_result.json` | Zapis odpowiedzi bonusowej zagadki |

### Wzorce do reuzycia

- [L18/task.py](../L18/task.py) — `post_answer()`, `get_api_key()`, logowanie do `.jsonl`
- [L19/task.py](../L19/task.py) — pobieranie zewnetrznego pliku JSON i zapis artefaktow
- [L17/ui_server.py](../L17/ui_server.py) — struktura prostego UI z endpointami pomocniczymi
- [L17/ui.html](../L17/ui.html) — panel do odpalania kolejnych krokow

## Uwagi implementacyjne

- Discovery bazy powinno byc dynamiczne, bez zakladania nazw tabel przed odczytem `show tables`.
- Podpis SHA1 nalezy pobierac przez `signatureGenerator`, a nie liczyc lokalnie, chyba ze `help` wyraznie poda identyczny algorytm i pola oraz zadanie tego wymaga.
- Batch `append` jest bezpieczniejszy niz wiele pojedynczych wywolan, bo zmniejsza liczbe requestow i upraszcza porownanie stanu.
- Przed `done` warto zrobic lokalna walidacje: liczba zamowien, zgodnosc miast, zgodnosc pozycji i ilosci.
- API ma agresywny rate limit, wiec solver spowalnia requesty i uzywa cache discovery zamiast wykonywac pelne rozpoznanie przy kazdym uruchomieniu.
- `orders/create` zwraca identyfikator zamowienia pod `order.id`, nie na poziomie top-level odpowiedzi.

## Uruchomienie

```powershell
python L20/task.py
python L20/ui_server.py
```

Jesli zadanie zostanie rozwiazane poprawnie, Centrala zwroci flage w odpowiedzi na `done`.

UI pokazuje teraz nie tylko artefakty discovery i stan zamowien, ale tez glowna flage oraz bonusowa odpowiedz z `bonus_result.json`.
