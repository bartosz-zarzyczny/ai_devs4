Zadanie: electricity

Opis

Masz do rozwiązania puzzle elektryczne na planszy 3x3. Twoim celem jest doprowadzenie prądu do wszystkich trzech elektrowni (PWR6132PL, PWR1593PL, PWR7264PL), łącząc je z awaryjnym źródłem zasilania (po lewej na dole) przez obracanie pól planszy.

Plansza

Aktualny stan planszy pobierasz jako obrazek PNG:

https://hub.ag3nts.org/data/tutaj-twój-klucz/electricity.png

Adresowanie pól

Pola adresujesz jako AxB, gdzie A to wiersz (1-3 od góry), B to kolumna (1-3 od lewej):

1x1 | 1x2 | 1x3
----|-----|----
2x1 | 2x2 | 2x3
----|-----|----
3x1 | 3x2 | 3x3

Przykład rozwiązania (schemat docelowy):

https://hub.ag3nts.org/i/solved_electricity.png

Interakcja z hubem

Każde zapytanie to osobne POST na `https://hub.ag3nts.org/verify` z JSON-em:

{
  "apikey": "tutaj-twój-klucz",
  "task": "electricity",
  "answer": {
    "rotate": "2x3"
  }
}

Uwaga: jedno zapytanie = jeden obrót (90° w prawo) jednego pola. Aby obrócić pole o 90° w lewo, wyślij 3 zapytania dla tego pola.

Reset planszy

Jeśli chcesz zresetować planszę do początkowego stanu:

https://hub.ag3nts.org/data/tutaj-twój-klucz/electricity.png?reset=1

Kroki rozwiązania

1. Pobierz aktualny obraz PNG i zidentyfikuj układ przewodów w każdym z 9 pól.
2. Porównaj z obrazem docelowym i oblicz, ile obrotów (90° w prawo) potrzebuje każde pole.
3. Dla każdego pola wymagającego obrotu wyślij odpowiednią liczbę POSTów `rotate` (po jednym na obrót).
4. Po partii obrotów pobierz powtórnie obraz i zweryfikuj postęp; w razie potrzeby kontynuuj lub wykonaj reset.
5. Gdy układ będzie poprawny, hub zwróci flagę w formacie `{FLG:...}`.

Wskazówki

- LLM nie widzi obrazu bezpośrednio — opisz każdy kafelek symbolicznie (np. krawędzie, które mają przewody: N,E,S,W) lub użyj narzędzia/vision do przetworzenia PNG przed podejmowaniem decyzji.
- Testuj modele vision — nie wszystkie dobrze rozpoznają kształty przewodów. Przetwarzanie obrazu (wycięcie kafelków, kontrast) może poprawić wyniki.
- Obrót to zawsze 90° w prawo; obrót w lewo = 3x obrót w prawo.
- Weryfikuj po każdym zestawie obrotów — błędy w interpretacji obrazu prowadzą do niepotrzebnych zapytań lub konieczności resetu.
- Podejście agentowe: idealne do zautomatyzowania — agent może pobrać obraz, rozpoznać kafelki, policzyć obroty i wysyłać POSTy sekwencyjnie.

Implementacja w tym folderze

W folderze `L07` znajduje się działająca implementacja z UI WWW i backendem w Pythonie:

- `get_electricity.py` — pobiera aktualny obraz `electricity.png` z użyciem klucza `AI_DEVS_4_API_KEY` z pliku `.env`.
- `electricity_solver.py` — logika solvera: pobranie obrazów, wykrycie siatki 3x3, porównanie kafelków z obrazem docelowym i wykonanie obrotów przez API.
- `ui_server.py` — serwer HTTP udostępniający UI i endpointy API.
- `ui.html` — interfejs WWW do podglądu planszy, analizy pól i sterowania obrotami.
- `electricity.png` — aktualny stan planszy pobrany z huba.
- `solved_electricity.png` — obraz docelowy używany do porównania.

Jak działa solver

1. Pobiera bieżący obraz planszy i obraz docelowy.
2. Wykrywa granice siatki 3x3 przez analizę ciemnych linii w obrazie.
3. Wyciąga 9 kafelków z planszy aktualnej i 9 kafelków z planszy docelowej.
4. Dla każdego pola testuje 4 warianty obrotu (`0`, `90`, `180`, `270` stopni w prawo).
5. Wybiera obrót z najmniejszą różnicą pikseli względem odpowiadającego pola docelowego.
6. Wysyła odpowiednią liczbę zapytań `rotate` do huba.
7. Pobiera świeży obraz planszy i ponownie wykonuje analizę.

Wymagania

Kod korzysta z:

- `requests`
- `Pillow`

Jeśli pakiety nie są jeszcze zainstalowane w aktywnym środowisku, doinstaluj je:

```powershell
pip install requests Pillow
```

Uruchomienie

Pobranie aktualnego obrazu:

```powershell
python L07/get_electricity.py
```

Pobranie obrazu z resetem planszy:

```powershell
python L07/get_electricity.py --reset
```

Uruchomienie UI WWW:

```powershell
python L07/ui_server.py
```

Serwer spróbuje uruchomić się na porcie `8080`, a jeśli będzie zajęty, wybierze kolejny wolny port. Po starcie otworzy przeglądarkę z adresem `http://localhost:<port>/ui.html`.

Funkcje UI

Interfejs WWW pozwala na:

- pobranie aktualnej planszy,
- reset planszy,
- analizę wszystkich 9 pól,
- podgląd aktualnej i docelowej planszy z zaznaczeniem siatki,
- kliknięcie konkretnego pola i obejrzenie go w powiększeniu,
- ręczne wykonanie pojedynczego obrotu dla wybranego pola,
- automatyczne wykonanie całego planu obrotów.

Endpointy serwera

`ui_server.py` udostępnia także endpointy pomocnicze:

- `GET /api/status`
- `GET /api/download`
- `GET /api/reset`
- `GET /api/analyze`
- `POST /api/rotate`
- `POST /api/apply-plan`

Uwagi praktyczne

- Klucz API jest odczytywany z głównego pliku `.env` z repozytorium.
- Solver opiera się na porównaniu obrazu bieżącego z obrazem wzorcowym, a nie na ręcznej definicji typów kafelków.
- Po wykonaniu planu serwer pobiera świeży obraz i ponownie przelicza analizę, więc wynik jest od razu widoczny w UI.

Dodatkowa zagadka: mapa na metapoziomie

Wskazówkę „Mapa na metapoziomie” można czytać tak: zamiast analizować samą sieć przewodów jak klasyczną mapę połączeń, można potraktować cały obraz docelowy jako mapę wyższego poziomu, czyli wzorzec odniesienia dla planszy aktualnej.

W praktyce oznacza to:

- nie trzeba ręcznie modelować każdego rodzaju kafelka i jego semantyki,
- nie trzeba rozwiązywać układu jako grafu połączeń,
- można porównać stan bieżący z docelowym kafelek po kafelku,
- obrót jest wyliczany przez znalezienie takiej orientacji pola, która najlepiej pasuje do odpowiedniego pola na mapie wzorcowej.

To właśnie zostało zaimplementowane w tym rozwiązaniu: obraz docelowy pełni rolę „mapy meta”, a solver dopasowuje do niej aktualny stan planszy przez analizę obrazu i test 4 możliwych rotacji każdego pola.

Dodatkowa podpowiedź: plik wie o sobie więcej niż obraz

Wskazówkę „Nie tylko piksele niosą informację. Czasem plik mówi więcej niż pokazuje - zapytaj go o to, co wie o sobie.” warto rozumieć dosłownie: w zadaniach obrazkowych nie należy ograniczać się wyłącznie do analizy pikseli.

W praktyce warto sprawdzić również:

- nazwę pliku,
- nagłówki HTTP przy pobieraniu,
- metadane obrazu,
- komentarze, profile i dodatkowe pola zapisane w pliku,
- rozmiar, format, strukturę i ewentualne dane pomocnicze dołączone do zasobu.

Innymi słowy: sam plik może zawierać wskazówki, które nie są widoczne na obrazie gołym okiem. To osobny trop analityczny, niezależny od rozpoznawania kształtów na planszy.

Powodzenia!
