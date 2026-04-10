# L25 — timetravel

**Nazwa zadania:** `timetravel`  
**Endpoint weryfikacji:** `https://hub.ag3nts.org/verify`  
**Interfejs urządzenia:** `https://hub.ag3nts.org/timetravel_preview`  
**Dokumentacja urządzenia:** `https://hub.ag3nts.org/dane/timetravel.md`

---

## Cel zadania

Uruchomić maszynę czasu CHRONOS-P1 i otworzyć tunel czasowy do **12 listopada 2024 roku** (dzień przed znalezieniem Rafała w jaskini). Ze względu na brak energii na bezpośredni skok potrzebne są trzy etapy:

1. Skok do **5 listopada 2238** — odebranie nowych baterii
2. Powrót do **dziś** (10 kwietnia 2026) — wymiana zużytych baterii
3. Otwarcie **tunelu** do 12 listopada 2024

---

## Uruchomienie

```powershell
python L25/task.py
```

Skrypt wyświetla interaktywne menu CLI. Każda faza prowadzi operatora krok po kroku — co ustawić przez API i co kliknąć ręcznie w interfejsie web.

---

## Przedliczone parametry skoków

| Faza | Data docelowa         | syncRatio                                    | internalMode | PWR | PT        |
|------|-----------------------|----------------------------------------------|--------------|-----|-----------|
| 1    | 5 listopada 2238      | `(5×8 + 11×12 + 2238×7) % 101 = 82 → 0.82`  | 3 (2151–2300) | 91  | PT-B      |
| 2    | 10 kwietnia 2026      | `(10×8 + 4×12 + 2026×7) % 101 = 69 → 0.69`  | 2 (2000–2150) | 28  | PT-A      |
| 3    | 12 listopada 2024     | `(12×8 + 11×12 + 2024×7) % 101 = 54 → 0.54` | 2 (2000–2150) | 19  | PT-A + PT-B |

**Wzór syncRatio:** `(day×8 + month×12 + year×7) % 101`, wynik (0–100) mapowany na `0.00–1.00`

**internalMode:**
- 1 → lata < 2000
- 2 → lata 2000–2150
- 3 → lata 2151–2300
- 4 → lata 2301+

---

## Sekwencja każdej fazy

```
Faza N:
  [API] getConfig — sprawdź stan urządzenia
  [UI]  Ustaw urządzenie w tryb standby
  [API] configure day, month, year, syncRatio
  [API] getConfig — odczytaj wskazówkę stabilization
  [API] configure stabilization=<wartość z podpowiedzi>
  [UI]  Ustaw PWR=<wartość z tabeli>
  [UI]  Ustaw PT-A / PT-B według trybu skoku
  [WAIT] Czekaj aż internalMode = <wymagany tryb>
  [UI]  Przełącz na active
  [UI]  Kliknij pulsującą sferę (flux density musi = 100%)
  [CONFIRM] Potwierdź wykonanie skoku
```

**Faza 3 (tunel)** wymaga battery ≥ 60% i jednoczesnego PT-A + PT-B.

---

## Co robi asystent (task.py), a co robi operator

| Kto | Co |
|-----|----|
| **Asystent (CLI)** | Oblicza syncRatio, pobiera wskazówki stabilization z API, ustawia day/month/year/syncRatio/stabilization przez API, monitoruje internalMode |
| **Operator (UI)** | Ustawia PWR w suwaku, włącza/wyłącza PT-A i PT-B, przełącza standby/active, klika sferę aktywacji |

---

## Ograniczenia API

- Konfiguracja przez API tylko w trybie **standby**
- Przez API można ustawić tylko: `day`, `month`, `year`, `syncRatio`, `stabilization`
- `PT-A`, `PT-B`, `PWR` — wyłącznie przez interfejs webowy
- `internalMode` zmienia się automatycznie co kilka sekund, **nie da się ustawić ręcznie**
- Przy rozładowanej baterii do zera zostają tylko: `help`, `getConfig`, `reset`
- Tunel wymaga baterii ≥ 60%

---

## Architektura skryptu

### Kluczowe funkcje

- `calc_sync_ratio(day, month, year)` — wzór z dokumentacji
- `required_internal_mode(year)` — lookup trybu
- `pwr_for_year(year)` — lookup z wbudowanej tabeli PWR
- `api_call(action, **kwargs)` — POST do `/verify`
- `configure_param(param, value)` — konfiguracja przez API
- `get_config()` — odczyt aktualnego stanu
- `extract_stabilization_hint(response)` — parsuje wskazówkę API
- `poll_internal_mode(expected_mode)` — odpytuje co 3s, czeka na właściwy mode
- `run_phase(phase_num)` — orkiestracja jednej fazy skoku
- `main()` — menu CLI

### Menu CLI

```
1. Pokaż aktualną konfigurację
2. Przegląd misji (wszystkie 3 skoki z parametrami)
3. Faza 1 — skok do 2238 (odbiór baterii)
4. Faza 2 — powrót do dziś (2026)
5. Faza 3 — otwórz tunel do 12 listopada 2024
6. Wywołaj help
7. Reset urządzenia
0. Wyjdź
```

---

## Weryfikacja

1. `python L25/task.py` → opcja 6 (help) → sprawdź połączenie z API
2. Opcja 1 → odczyt stanu urządzenia
3. Opcja 3 → Faza 1 krok po kroku z operatorem przy UI
4. Opcja 4 → Faza 2
5. Opcja 5 → Faza 3 (tunel) → flaga pojawia się w odpowiedzi API

---

## Pliki

| Plik | Opis |
|------|------|
| `task.py` | Główny skrypt CLI — asystent operatora |
| `README.md` | Ta dokumentacja |
| `verification_result.json` | Odpowiedź huba po weryfikacji (generowany) |

---

## Kroki wykonania zadania

### 0. Przygotowanie

```powershell
python L25/task.py
```

Wywołaj opcję **6 (help)** — sprawdź połączenie z API i listę dostępnych akcji.  
Wywołaj opcję **1 (getConfig)** — sprawdź aktualny stan urządzenia.  
Otwórz w przeglądarce: `https://hub.ag3nts.org/timetravel_preview`

---

### 1. Faza 1 — skok do 5 listopada 2238 (odebranie baterii)

**Asystent (CLI — opcja 3):**
1. Wywołuje `getConfig` — pokazuje aktualny stan
2. Konfiguruje przez API: `day=5`, `month=11`, `year=2238`, `syncRatio=0.82`
3. Pobiera z API wskazówkę `stabilization` i ustawia ją

**Operator (UI — `https://hub.ag3nts.org/timetravel_preview`):**
1. Upewnij się, że urządzenie jest w trybie **standby** (wymagane przed każdą zmianą API)
2. Ustaw suwak **PWR = 91**
3. Włącz **PT-B**, wyłącz **PT-A** (skok w przyszłość)

**Asystent:**
4. Monitoruje `internalMode` — czeka aż osiągnie **3** (zakres 2151–2300)
5. Gdy mode = 3 i flux density = 100%, wyświetla komunikat: _"Gotowe do skoku!"_

**Operator:**
4. Przełącz urządzenie na **active**
5. Kliknij pulsującą **sferę aktywacji** (musi być zielona)
6. Odbierz nowe baterie od kontaktu w 2238 roku i włóż je do urządzenia
7. Potwierdź w CLI wykonanie skoku (Enter)

---

### 2. Faza 2 — powrót do 10 kwietnia 2026 (dziś)

**Operator (UI):**
1. Upewnij się, że urządzenie jest w trybie **standby**

**Asystent (CLI — opcja 4):**
1. Konfiguruje przez API: `day=10`, `month=4`, `year=2026`, `syncRatio=0.69`
2. Pobiera z API wskazówkę `stabilization` i ustawia ją

**Operator (UI):**
2. Ustaw suwak **PWR = 28**
3. Włącz **PT-A**, wyłącz **PT-B** (skok w przeszłość)

**Asystent:**
3. Monitoruje `internalMode` — czeka aż osiągnie **2** (zakres 2000–2150)
4. Gdy mode = 2 i flux density = 100%, wyświetla: _"Gotowe do powrotu!"_

**Operator:**
4. Przełącz na **active**
5. Kliknij **sferę aktywacji**
6. Potwierdź w CLI wykonanie skoku (Enter)

---

### 3. Faza 3 — otwarcie tunelu do 12 listopada 2024

> **Uwaga:** tunel wymaga baterii ≥ 60%. Asystent weryfikuje poziom przez `getConfig` przed startem.

**Operator (UI):**
1. Upewnij się, że urządzenie jest w trybie **standby**

**Asystent (CLI — opcja 5):**
1. Sprawdza przez `getConfig` czy bateria ≥ 60% — jeśli nie, zgłasza błąd
2. Konfiguruje przez API: `day=12`, `month=11`, `year=2024`, `syncRatio=0.54`
3. Pobiera z API wskazówkę `stabilization` i ustawia ją

**Operator (UI):**
2. Ustaw suwak **PWR = 19**
3. Włącz **JEDNOCZEŚNIE PT-A i PT-B** (tryb tunelu czasowego)

**Asystent:**
4. Monitoruje `internalMode` — czeka aż osiągnie **2** (zakres 2000–2150)
5. Gdy mode = 2 i flux density = 100%, wyświetla: _"Gotowe do otwarcia tunelu!"_

**Operator:**
4. Przełącz na **active**
5. Kliknij **sferę aktywacji**
6. Centrala odsyła flagę w odpowiedzi API — asystent ją wyświetla

---

### 4. Odebranie flagi

Odpowiedź z flagą pojawia się w terminalu po wykonaniu Fazy 3.  
Asystent automatycznie zapisuje ją do `L25/verification_result.json`.
