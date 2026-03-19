# L09 – Mailbox

## Opis zadania

Zdobyliśmy dostęp do skrzynki mailowej jednego z operatorów systemu. Wiemy, że na tę skrzynkę wpadł mail od Wiktora – nie znamy jego nazwiska, ale wiemy, że doniósł na nas. Musimy przeszukać skrzynkę przez API i wyciągnąć trzy informacje:

| Pole | Opis | Format |
| ------ | ------ | -------- |
| `date` | Kiedy dział bezpieczeństwa planuje atak na naszą elektrownię | `YYYY-MM-DD` |
| `password` | Hasło do systemu pracowniczego, które prawdopodobnie nadal znajduje się na skrzynce | dowolny tekst |
| `confirmation_code` | Kod potwierdzenia z ticketa wysłanego przez dział bezpieczeństwa | `SEC-` + 32 znaki = 36 znaków łącznie |

Skrzynka jest cały czas w użyciu – w trakcie pracy mogą na nią wpływać nowe wiadomości.

---

## Krok 1 wykonany: `help` na `zmail`

Wywołanie `help` zwróciło następujące akcje API:

- `help` - pokazuje listę akcji i wymagane parametry
- `getInbox` - zwraca listę wątków w skrzynce
- `getThread` - zwraca `rowID` oraz listę `messageID` dla wybranego wątku
- `getMessages` - zwraca pełne wiadomości po `rowID` / `messageID`
- `search` - przeszukiwanie treści z operatorami podobnymi do Gmaila
- `reset` - reset licznika zapytań dla tego klucza w pamięci podręcznej

Parametry, które warto zapamiętać:

- `getInbox`: `page` opcjonalne, domyślnie `1`, oraz `perPage` opcjonalne, zakres `5-20`, domyślnie `5`
- `getThread`: `threadID` wymagane
- `getMessages`: `ids` wymagane, może być pojedynczym ID, `messageID` albo tablicą ID
- `search`: `query` wymagane, opcjonalnie `page` i `perPage`

---

## UI dla zadania

W katalogu `L09` warto utrzymywać prosty panel WWW do kolejnych iteracji pracy nad skrzynką. Minimalny zestaw:

- `mailbox_client.py` - wspólne wywołania API `zmail`
- `ui_server.py` - lokalny serwer HTTP z endpointami do odświeżania statusu, help, inboxa i wyszukiwania
- `ui.html` - interfejs z przyciskami do wykonywania kolejnych kroków i podglądem odpowiedzi API
- `bonus_solver.py` - automatyczne wyszukiwanie wiadomości z załącznikiem, rozpakowanie `dokumenty.zip` i dekodowanie bonusowej flagi
- `task.py` - uruchamia wyszukaną konfigurację i pobiera główną flagę z `/verify`

Założenie UI: po każdym kolejnym wykonaniu ma od razu pokazywać aktualne dane z API, bo skrzynka jest aktywna i może się zmieniać.

### Główna flaga w UI

Panel zawiera osobny przycisk `Szukaj głównej flagi`, który wywołuje tor z `task.py` przez endpoint `/api/main-flag`.
Wynik trafia do `verification_result.json` i jest pokazywany w osobnej sekcji z podglądem flagi.

### Bonusowa flaga

W skrzynce jest dodatkowa wiadomość z załącznikiem `dokumenty.zip` w temacie `Akt wandalizmu - kolejny raz!`.
Bonusowy tor pracy wyszukuje tę wiadomość, pobiera załącznik, rozpakowuje archiwum i dekoduje zawartość pliku `GADERYPOLUKI.txt`.

Po poprawnym uruchomieniu solvera wynik trafia do `bonus_flag_result.json` i powinien ujawnić dodatkową flagę w UI.

---

## Co wiemy na start

- Wiktor wysłał maila z domeny **proton.me**
- API działa jak wyszukiwarka Gmail – obsługuje operatory `from:`, `to:`, `subject:`, `OR`, `AND`

---

## API zmail

Skrzynka mailowa dostępna jest przez API `zmail`:

**Endpoint:** `POST https://hub.ag3nts.org/api/zmail`  
**Content-Type:** `application/json`

### Sprawdzenie dostępnych akcji (`help`)

```json
{
  "apikey": "TWÓJ_KLUCZ",
  "action": "help",
  "page": 1
}
```

### Pobranie zawartości inboxa (`getInbox`)

```json
{
  "apikey": "TWÓJ_KLUCZ",
  "action": "getInbox",
  "page": 1
}
```

---

## Wysyłanie odpowiedzi

`POST https://hub.ag3nts.org/verify`

```json
{
  "apikey": "TWÓJ_KLUCZ",
  "task": "mailbox",
  "answer": {
    "password": "znalezione-hasło",
    "date": "2026-02-28",
    "confirmation_code": "SEC-tu-wpisz-kod"
  }
}
```

Gdy wszystkie trzy wartości będą poprawne, hub zwróci flagę `{FLG:...}`.

### Wyszukiwanie i pobieranie wiadomości

Przy kolejnych krokach pracy z danymi korzystamy z dwóch etapów:

1. `search` lub `getInbox` / `getThread` zwraca metadane oraz identyfikatory.
2. `getMessages` pobiera pełną treść wiadomości po identyfikatorach.

To ważne, bo w tej skrzynce nie wolno zgadywać treści na podstawie samych tematów.

---

## Plan działania

1. Wywołaj akcję `help` na API zmail, żeby poznać wszystkie dostępne akcje i parametry.
2. Spraw, aby agent korzystał z wyszukiwarki maili – na podstawie opisu zadania może budować odpowiednie zapytania (np. `from:proton.me`, `subject:password`, `subject:SEC-`).
3. Pobierz pełną treść znalezionych wiadomości, żeby przeczytać ich zawartość (API działa dwuetapowo: najpierw lista z metadanymi, potem treść po ID).
4. Szukaj informacji po kolei – nie musisz znaleźć wszystkich na raz.
5. Korzystaj z feedbacku huba, żeby wiedzieć, których wartości jeszcze brakuje lub które są błędne.
6. Kontynuuj przeszukiwanie skrzynki, aż zbierzesz wszystkie trzy wartości i hub zwróci flagę.
7. Pamiętaj, że skrzynka jest aktywna – jeśli szukasz czegoś i nie możesz znaleźć, spróbuj ponownie, bo nowe wiadomości mogły dopiero wpłynąć.

---

## Wskazówki implementacyjne

### Podejście agentowe z Function Calling

To zadanie doskonale nadaje się do **pętli agentowej z narzędziami**. Agent może mieć do dyspozycji:

- `search_mail(query, page)` – wyszukiwanie maili z operatorami
- `get_mail(id)` – pobieranie pełnej treści wiadomości po ID
- `submit_answer(password, date, confirmation_code)` – wysyłanie odpowiedzi do huba
- `stop()` – zakończenie pracy po znalezieniu flagi

Pętla powinna działać iteracyjnie: **szukaj → czytaj → wyciągaj wnioski → szukaj dalej**.

### Dwuetapowe pobieranie danych

API zmail działa w dwóch krokach:

1. Wyszukaj i dostań listę maili z metadanymi (bez treści).
2. Pobierz pełną treść wybranych wiadomości po ich identyfikatorach.

Nie próbuj odgadywać treści na podstawie samego tematu – zawsze pobieraj pełną wiadomość.

### Aktywna skrzynka

Skrzynka jest cały czas w użyciu i nowe wiadomości mogą wpływać w trakcie pracy. Jeśli przeszukałeś całą skrzynkę i nie możesz czegoś znaleźć, warto spróbować ponownie – szukana informacja mogła właśnie dotrzeć.

### Wybór modelu

Do tego zadania wystarczy tańszy model, np. `google/gemini-flash-2.0`. Zadanie polega na przeszukiwaniu i ekstrakcji faktów, nie na złożonym rozumowaniu. Pętla agentowa może wykonać kilkanaście zapytań do LLM – droższy model nie da tutaj istotnej przewagi.

### Operatory wyszukiwania

API obsługuje składnię podobną do Gmail. Przykłady:

```text
from:proton.me
from:wiktor@proton.me
subject:password
subject:SEC-
subject:atak
from:proton.me subject:hasło
```

Zacznij od szerokich zapytań, żeby nie przegapić istotnych maili, a potem zawęź wyszukiwanie.

### Proponowana implementacja

- `mailbox_client.py` - enkapsuluje `help`, `search`, `getInbox`, `getThread`, `getMessages` i `reset`
- `task.py` - krok po kroku wyciąga `date`, `password` i `confirmation_code`, a następnie wysyła odpowiedź do `/verify`
- `bonus_solver.py` - wyszukuje wiadomość z załącznikiem, rozpakowuje ZIP i dekoduje bonusową flagę
- `ui_server.py` / `ui.html` - panel do ręcznej kontroli kolejnych iteracji, podglądu odpowiedzi API oraz uruchamiania głównego i bonusowego toru

---

## Struktura plików

```text
L09/
├── README.md          # ten plik
├── agent.py           # główny agent w pętli agentowej
└── prompts/           # prompty systemowe dla agenta
```
