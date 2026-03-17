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

Powodzenia!
