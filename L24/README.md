# L24 - goingthere

## Zadanie praktyczne

Wyruszasz rakieta naziemna w kierunku Grudziadza. Problem polega na tym, ze systemy zaklocajace nawigacje na calej trasie sprawiaja, ze nie wiesz, co znajduje sie przed Toba, wiec mozesz uderzyc w skale. Jedyne, co mozesz zrobic, to nasluchiwac komunikatow radiowych opisujacych polozenie skaly tuz przed Toba.

Pamietaj, ze system OKO caly czas namierza kazdy, nawet najdrobniejszy ruch, jaki wykonujemy na tych odludnych terenach. Jesli system namierzania wykryje Cie, to wystrzeli pocisk, ktory zakonczy Twoje zycie. Mamy jednak dostep do API, ktore umozliwia wykrycie, kiedy jestes namierzany, oraz potrafi zneutralizowac sygnal radarowy, dzieki czemu bedziesz niewidoczny dla systemu OKO. Musisz jedynie sprawdzac w API przed wykonaniem kazdego ruchu, czy znajdujesz sie akurat kolo radaru, i jesli tak, przeprowadzic procedure jego deaktywacji.

Mechanizmy zagleuszajace stosowane przez system OKO maja podwojne dzialanie:

- Dane odbierane ze skanera czestotliwosci sa czesto znieksztalcone lub uszkodzone.
- API moze losowo zwracac bledy nawet przy poprawnych zapytaniach.

Kod musi byc odporny zarowno na uszkodzone pakiety danych, jak i na losowe bledy API. W razie bledu nalezy po prostu ponowic zapytanie.

## Podstawowe informacje

- Nazwa zadania: `goingthere`
- Endpoint weryfikacji: `https://hub.ag3nts.org/verify`
- Podglad trasy i stanu gry: `https://hub.ag3nts.org/goingthere_preview`

## Plansza i sterowanie

Rakieta porusza sie po siatce o wymiarach 3 wiersze na 12 kolumn. Start jest zawsze w kolumnie 1, w srodkowym wierszu (`row = 2`). Baza w Grudziadzu znajduje sie w kolumnie 12, w wierszu podanym na starcie. W kazdej kolumnie znajduje sie dokladnie jedna skala.

Dostepne komendy:

- `start` - rozpoczyna nowa gre, generuje nowa mape i resetuje stan.
- `go` - lot prosto do przodu, do nastepnej kolumny w tym samym wierszu.
- `left` - ruch po skosie w gore, do nastepnej kolumny.
- `right` - ruch po skosie w dol, do nastepnej kolumny.

Kazdy ruch przesuwa rakiete o jedna kolumne do przodu. Jesli trafisz w skale, rakieta sie rozbija i trzeba zaczac od nowa. Jesli wypadniesz poza mape, efekt jest taki sam. Jesli nie zneutralizujesz aktywnego radaru przed ruchem, rakieta zostanie zestrzelona.

## Start gry

Nowa gre uruchamiasz przez `POST` na endpoint weryfikacji:

```json
{
    "apikey": "tutaj-twoj-klucz",
    "task": "goingthere",
    "answer": {
        "command": "start"
    }
}
```

Po starcie otrzymujesz informacje o swojej pozycji, pozycji bazy docelowej oraz opisie biezacej kolumny. Na tej podstawie zapisujesz stan poczatkowy:

- `col = 1`
- `row = 2`
- `target_row = row bazy zwrocony przez API`

## Radiowe wskazowki o skalach

Aby poznac polozenie skaly w nastepnej kolumnie, nalezy pobrac wskazowke radiowa z endpointu:

`POST https://hub.ag3nts.org/api/getmessage`

```json
{
    "apikey": "tutaj-twoj-klucz"
}
```

W odpowiedzi otrzymasz pole `hint` z komunikatem po angielsku. Komunikat opisuje, ktory ruch bylby kolizyjny wzgledem aktualnej pozycji rakiety w nastepnej kolumnie. Wskazowki moga uzywac jezyka zeglarskiego, wiec warto zmapowac je na zablokowany ruch wzgledny:

- `port` lub `larboard` -> zablokowany jest ruch `left`
- `dead ahead`, `ahead`, `front`, `center` -> zablokowany jest ruch `go`
- `starboard` -> zablokowany jest ruch `right`

Wazne: przy kazdym kroku komenda ruchu moze byc inna. Ten sam hint moze prowadzic do innej decyzji zaleznie od aktualnego wiersza, bo opis dotyczy ruchu wzgledem rakiety, a nie absolutnego wiersza planszy. Jesli komunikat jest nietypowy lub znieksztalcony, mozna skorzystac z LLM (np. OpenRouter) do ustalenia zablokowanego ruchu albo bezposredniego wyboru `go`, `left` lub `right`. Dla interpretacji hintu warto wykonac dodatkowe sprawdzenie drugim modelem, np. `nvidia/nemotron-3-nano-30b-a3b:free`, i akceptowac odpowiedz tylko wtedy, gdy oba modele sa zgodne.

## Skaner czestotliwosci i system OKO

Przed kazdym ruchem trzeba sprawdzic, czy aktualna kolumna jest chroniona przez aktywny radar. Sluzy do tego skaner czestotliwosci:

`GET https://hub.ag3nts.org/api/frequencyScanner?key=tutaj-twoj-klucz`

Mozliwe odpowiedzi:

- `It's clear!` - brak zagrozenia, mozna przejsc do kolejnego kroku.
- Znieksztalcony JSON - aktywna pulapka, trzeba odczytac `frequency` i `detectionCode`, a nastepnie ja zneutralizowac.

Odpowiedz moze wygladac jak JSON, ale nie byc poprawnym JSON-em. Dlatego parser musi byc odporny na uszkodzone dane i w razie potrzeby probowac odzyskac potrzebne pola z tekstu.

Mozesz takze uzyc LLM (np. OpenRouter) do interpretacji znieksztalconych komunikatow, aby ustalic, czy wiadomosc oznacza "It's clear!" czy aktywny radar. W kodzie domyslnie uzywany jest model `nvidia/nemotron-3-super-120b-a12b:free`.

## Neutralizacja pulapki

Jesli skaner wykryje namierzanie, trzeba rozbroic pulapke przed wykonaniem ruchu. Wysylasz `POST` na:

`https://hub.ag3nts.org/api/frequencyScanner`

```json
{
    "apikey": "tutaj-twoj-klucz",
    "frequency": 123,
    "disarmHash": "abc123def456..."
}
```

Zasady wyliczenia danych:

- `frequency` to wartosc liczbowa odczytana z odpowiedzi skanera.
- `disarmHash` to SHA1 z ciagu `detectionCode + "disarm"`.

Lot mozna kontynuowac dopiero po potwierdzeniu poprawnej neutralizacji.

## Plan wykonania

### 1. Konfiguracja i inicjalizacja

- Wczytaj `API_KEY` z pliku `.env` przy uzyciu `python-dotenv`.
- Wyslij komenda `start` na endpoint `/verify`.
- Zapisz `target_row` oraz aktualna pozycje startowa: `col = 1`, `row = 2`.

### 2. Petla glowna dla kolumn 1-11

Dla kazdej kolumny wykonuj trzy etapy w stalej kolejnosci.

#### A. Skanowanie i neutralizacja

- Odpytaj `GET https://hub.ag3nts.org/api/frequencyScanner?key={API_KEY}`.
- Jesli pojawi sie blad API, timeout lub uszkodzona odpowiedz bez mozliwosci odzyskania danych, ponow probe.
- Jesli odpowiedz to `It's clear!`, przejdz dalej.
- Jesli radar jest aktywny, odzyskaj `frequency` oraz `detectionCode` w dwoch krokach:

  **Ekstrakcja (Regex -> LLM -> Regex)**

  1. Sprobuj sparsowac odpowiedz jako poprawny JSON, a nastepnie przez regex na znanych nazwach pol.
  2. Jesli regex zawiedzie, przeslij znieksztalcony tekst do darmowego modelu jezykowego (OpenRouter) z promptem:
     `"Extract 'frequency' and 'detectionCode' from this corrupted JSON string. Return only raw JSON"`.
  3. Sprawdz wynik LLM za pomoca regexa: `frequency` musi byc liczba, `detectionCode` niepustym ciagiem znakow.

- Oblicz `disarmHash = SHA1(detectionCode + "disarm")`.
- Wyslij `POST` na `/api/frequencyScanner` z polami `apikey`, `frequency` i `disarmHash`.
- Kontynuuj dopiero po sukcesie neutralizacji.

#### B. Analiza drogi

- Pobierz wskazowke z `/api/getmessage`.
- Zmapuj tresc komunikatu na zablokowany ruch wzgledny: `left`, `go` albo `right`.
- Gdy korzystasz z LLM, zweryfikuj interpretacje drugim, niezaleznym modelem.
- Uwzglednij klasyczne okreslenia marynistyczne: `port`, `larboard`, `dead ahead`, `starboard`.
- Dla mylacych fraz opisujacych srodek trasy, takich jak `central path`, `straight ahead`, `forward line` albo `through the middle`, nie ufaj samemu regexowi. Najpierw sprawdz zapisana wiedze z `hint_log.json` i `hint_knowledge.json`, a nastepnie recznie utrzymywana tabele wyjatkow semantycznych zbudowana na podstawie zapisanych przypadkow.

#### C. Logika sterowania (Strategia "Wiersz 2")

Priorytetem jest stabilnosc i powrot do srodka mapy.

**Tabela decyzyjna (priorytety od najwyzszego):**

| Sytuacja | Akcja |
| --- | --- |
| Ruch prosto jest zablokowany skala | Wykonaj `left` lub `right` (zaleznie od tego, ktory jest w granicach mapy) |
| Aktualna kolumna to 11 (krok przed baza) | Ignoruj preference wiersza 2, kieruj sie bezposrednio na `target_row` |
| Jestes w wierszu 1 lub 3, a wiersz 2 jest wolny | Wykonaj ruch w kierunku wiersza 2 |
| Jestes w wierszu 2 i jest on wolny | Wykonaj `go` |

**Przyklad uniku (kolumna 5):**

1. Pozycja: wiersz 2. Wskazowka: `dead ahead` (skala w wierszu 2).
2. Decyzja: uciekasz z wiersza 2, wybierasz `left` do wiersza 1 (jesli nie jestes na krawedzi).
3. W nastepnym kroku (kolumna 6): jesli wskazowka wskazuje wiersz != 2, wybierasz `right`, aby wrocic do bezpiecznego, srodkowego toru.

### 3. Odpornosc i bezpieczenstwo

- Kazde zapytanie do API (`start`, ruch, `frequencyScanner`, `getmessage`) owin retry policy.
- Jesli API zwroci komunikat `Za czesto wykonujesz zapytania. Zwolnij.`, potraktuj to jako rate limit: zwieksz odstep miedzy zapytaniami i odczekaj przed ponowna proba.
- Przed ruchem `left` lub `right` sprawdz, czy wynikowy wiersz miesci sie w przedziale `1..3`.
- Po kazdej odpowiedzi aktualizuj lokalny stan pozycji rakiety, zeby decyzje w kolejnych krokach byly deterministyczne.
- W razie rozbicia lub zestrzelenia rozpocznij nowa probe od `start`.

## Co musi zrobic solver

1. Wystartowac gre komenda `start` i zapisac pozycje bazy.
2. Na kazdym polu sprawdzic przez `frequencyScanner`, czy rakieta nie jest namierzana.
3. W razie aktywnego radaru sparsowac znieksztalcona odpowiedz, obliczyc SHA1 i rozbroic pulapke.
4. Pobierac wskazowke radiowa z `getmessage`, aby ustalic polozenie skaly w nastepnej kolumnie.
5. Wybrac poprawny ruch (`go`, `left`, `right`) bez kolizji i bez wyjscia poza plansze.
6. Powtarzac te kroki az do dotarcia do Grudziadza i odebrania flagi.

## Bonus - Trzy Groby

Zagadka bonusowa wymaga wykonania jednej scislej sekwencji kontrolowanych porazek:

1. Dojdz do kroku 6 i dopiero wtedy rozbij rakiete lub daj sie zestrzelic.
2. Uruchom gre ponownie, dojdz do kroku 4 i dopiero wtedy rozbij rakiete lub daj sie zestrzelic.
3. Uruchom gre ponownie, dojdz do kroku 2 i dopiero wtedy rozbij rakiete lub daj sie zestrzelic.

Kolejnosc `6 -> 4 -> 2` ma znaczenie i nie nalezy powtarzac tego samego etapu wiele razy w petli. To ma byc jedna sekwencja trzech kolejnych podejsc.

## Endpointy

| Akcja | Metoda | URL |
| --- | --- | --- |
| Gra i ruch | `POST` | `https://hub.ag3nts.org/verify` |
| Skaner czestotliwosci | `GET` | `https://hub.ag3nts.org/api/frequencyScanner?key={KEY}` |
| Neutralizacja radaru | `POST` | `https://hub.ag3nts.org/api/frequencyScanner` |
| Wiadomosc radiowa | `POST` | `https://hub.ag3nts.org/api/getmessage` |

## Bonus: Trzy groby 642

Jesli chcesz sprawdzic zagadke z kontrolowanymi rozbiciami, uruchom:

`python L24/task.py --graves`

Do debugowania pojedynczego etapu mozesz uruchomic tylko jeden kontrolowany crash, na przyklad:

`python L24/task.py --grave-step 6`

Tryb bonusowy wymusza trzy kolejne rozbicia na krokach `6`, `4` i `2`, a wynik zapisuje do `bonus_result.json`.

Podczas uruchomien solver zapisuje dodatkowo historie hintow do `hint_log.json` oraz utrwala sprawdzone interpretacje i poprawki po blednych ruchach w `hint_knowledge.json`. `hint_log.json` jest dziennikiem zdarzen, ale identyczne wpisy sa teraz scalane licznikiem powtorzen zamiast byc bezwarunkowo duplikowane. Przy kolejnych probach solver najpierw probuje wykorzystac te zapamietane, potwierdzone przypadki.

Korekty dopisywane po rozbiciu o kamien nie sa juz utrwalane, jezeli jawnie przecza literalnej tresci hintu, na przyklad gdy hint opisuje dany kierunek jako `safe/open/clear`, a pojedynczy crash sugerowalby odwrotna interpretacje.

Solver korzysta tez z recznie utrzymywanej tabeli wyjatkow dla fraz, ktore w praktyce okazaly sie mylace mimo pozornie oczywistej interpretacji. Tabela jest zasilana analiza zapisanych hintow i sluzy jako nadrzedne zrodlo dla podejrzanych wzorcow typu `middle/straight/forward`.
