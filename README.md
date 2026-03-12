# ai_devs4

Repozytorium zawiera rozwiązania zadań AI_DEVS 4.

## Lekcje

- [L01/README.md](L01/README.md) - zadanie `people` (filtrowanie, tagowanie, wysyłka do verify)
- [L02/README.md](L02/README.md) - zadania `location`, `accesslevel`, `findhim` (analiza i verify)
 - [L03/README.md](L03/README.md) - lokalny serwer i narzędzia do submit (debug endpoints)
 - [L04/README.md](L04/README.md) - zadanie `sendit` (deklaracja transportowa, test tras, logowanie odpowiedzi)

## Konfiguracja

Projekt korzysta ze standardowej biblioteki Pythona. W katalogu głównym utwórz plik `.env`:

```env
API_OPEN_ROUTER_KEY=twoj_klucz_openrouter
AI_DEVS_4_API_KEY=twoj_klucz_ai_devs
```

Wymagane zmienne:

- `API_OPEN_ROUTER_KEY` dla skryptów używających OpenRouter (L01)
- `AI_DEVS_4_API_KEY` dla endpointów hub.ag3nts.org (L01, L02)
 - `AI_DEVS_4_API_KEY` jest również używana przez skrypty w `L04` (send_payload/test_routes)

## Ostatnie zmiany (skrót)

- L03: dodano lokalny serwer i narzędzia pomocnicze; folder `L03` zawiera logi i endpointy debugujące (sprawdź L03/logs).
- L04: komplet rozwiązań dla zadania `sendit` — `send_payload.py` (opcje `--route`, `--wdp`, `--response-log`), `test_routes.py` do batch-testów, `validate_declaration.py` do lokalnej walidacji. Usunięto pliki tymczasowe i dodano oddzielny `response_log.jsonl` dla maszynowego przetwarzania odpowiedzi.
- Rezultat L04: poprawne wypełnienie deklaracji i otrzymanie potwierdzenia zwrotnego (szczegóły w [L04/README.md](L04/README.md)).
