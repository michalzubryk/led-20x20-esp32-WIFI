# Architektura, API i rozwój

## Przepływ obrazu

Generator lokalny działa w ESP32, a zdalny renderer w Pythonie na serwerze. Studio renderuje scenę około 20 razy na sekundę. ESP32 pobiera ciągły strumień HTTPS w osobnym zadaniu, dzięki czemu lokalne WWW pozostaje dostępne. Wszystkie urządzenia korzystające z tej instancji serwera widzą tę samą scenę — nie ma osobnych kont ani playlist per urządzenie.

Zdalna klatka to 1200 bajtów RGB (20×20, kolejno wierszami). Jasność stosuje serwer; ESP32 mapuje współrzędne na przewód oraz kolejność kanałów. W trybie USB/DDP nadajnik przesyła już dane w kolejności fizycznych LED. Aktualizacja RMT trwa około 10,2 ms na pełną ramkę; wynikowe FPS zależy również od transportu i obciążenia.

## Endpointy lokalnego ESP32

| Metoda / ścieżka | Znaczenie |
|---|---|
| GET `/` | Panel lokalny |
| GET/POST `/api/config` | Konfiguracja; POST jako formularz URL-encoded |
| GET `/api/stats` | Statystyki |
| GET `/api/remote` | Status źródła, połączenia i OTA |
| GET `/preview` | Surowe 1200 bajtów podglądu |
| GET/POST `/update` | Formularz / upload OTA, Basic Auth |
| POST `/api/update` | Aktualizacja z serwera, Basic Auth |

Źródła: `local`, `server`, `stream`. Parametry generatora obejmują `mode`, `text`, `direction`, `speed`, `color`, `brightness`, `scale`, `start`, `blink`, `blinkMs`, `invert`, `enabled`, `layout`, `order`. `save=true` zapisuje ustawienia w NVS. Szczegóły walidacji: `generator.h`.

## Endpointy studia

Panel i API użytkownika wymagają Basic Auth; endpointy `/api/device/*` wymagają `Authorization: Bearer TOKEN`. `/health` jest publicznym sprawdzeniem gotowości. Mutacje pochodzące z obcej domeny są odrzucane po nagłówku Origin.

| Metoda / ścieżka | Znaczenie |
|---|---|
| GET `/api/state` | Scena, lista kształtów i stan połączeń |
| GET/POST `/api/game` | Stan i polecenia gry; opis w [GRY.md](GRY.md) |
| POST `/api/schedule` | Częściowe ustawienia codziennego harmonogramu JSON |
| POST `/api/scene` | Częściowa konfiguracja sceny JSON |
| GET `/api/preview` | 1200 bajtów RGB |
| POST `/api/shapes` | Dodanie kształtu JSON |
| GET/PUT/DELETE `/api/shapes/{id}` | Odczyt / zmiana / usunięcie |
| POST `/api/shapes/{id}/play` | Odtworzenie wybranego motywu, zastępuje poprzedni |
| GET `/api/device/stream` | Ciągły strumień ramek |
| GET `/api/device/frame` | Pojedyncza klatka diagnostyczna |
| GET `/api/device/firmware` | Binarka dla ESP32 |
| GET `/api/firmware` | Informacje o dostępnej binarce |
| GET `/firmware/led400.bin` | Pobranie binarki przez użytkownika |

Kształt ma pola `name` (1–60 znaków), `frames` (1–32 tablice po 1200 liczb 0–255), `durationMs` (50–2000) i `kind` (`image`, `animation`, `slideshow`). `image` musi mieć jedną klatkę. `animate=false` w scenie zatrzymuje wybrany motyw na pierwszej klatce. Edytor WWW udostępnia wybrane czasy z dopuszczalnego zakresu.

Scena i biblioteka są zapisywane atomowo w `/data/studio.json`. Limit biblioteki wynosi 100 kształtów. Pojedyncze żądanie ma limit 1 MiB. Serwer nie rozpoznaje automatycznie fizycznego typu diod.

## Renderowanie gier

`games.py` zawiera niezależne silniki Arkanoid/Tetris i ulotną sesję gry. Aktywna gra zastępuje renderer sceny tylko na czas rozgrywki; nie modyfikuje zapisanego motywu ani biblioteki. Pętla 20 FPS aktualizuje stan i wysyła te same 1200-bajtowe klatki RGB co przy animacjach. Harmonogram nadal ogranicza wyświetlanie. `static/games.js` zapewnia sterowanie, heartbeat oraz automatyczną pauzę. [Szczegóły sesji i protokołu](GRY.md).

## Harmonogram serwera

`POST /api/schedule` przyjmuje `enabled` (bool), `on` i `off` (`HH:MM`, różne godziny) oraz `timezone` (nazwa IANA, np. `Europe/Warsaw`). Wymaga Basic Auth i kontroli Origin jak pozostałe mutacje. `GET /api/state` zwraca `schedule` z dodatkowymi polami `active` (czy aktualnie wolno świecić) i `localTime` (ISO 8601 z offsetem).

Przed renderowaniem każdej klatki serwer ocenia przedział według `zoneinfo`. Poza nim zwraca 1200 zer, zachowując wybraną scenę i połączenie HTTPS. `scene.enabled=false` nadal ma pierwszeństwo. Zmiana sceny nie usuwa godzin, a wyłączenie harmonogramu nie włącza ręcznie wyłączonej sceny. Restart nie wymaga czekania na następne zdarzenie zegarowe: aktualny stan wynika od razu z bieżącej godziny. Czas animacji biegnie również podczas wygaszenia.

Konfiguracja jest zapisywana atomowo ze sceną i biblioteką. Starszy plik bez pola `schedule` otrzymuje ustawienia domyślne z `enabled=false`. Pakiet `tzdata` dostarcza bazę stref, gdy system nie posiada własnej. Firmware nie pobiera reguł godzinowych; w trybie awaryjnym lokalny generator działa niezależnie.

## Protokoły transportowe

- HTTPS stream: każda paczka to 4 bajty numeru klatki uint32 little-endian + 1200 bajtów RGB. ESP używa HTTP/1.0 bez chunked encoding, buforuje pełną paczkę. Nagłówki urządzenia: `X-Device-ID`, `X-Frames-Received`. Identyfikatory widoczne w panelu to dane instalacji, nie element źródeł.
- USB: 921600 baud, 8N1; `L400` + numer uint32 LE + RGB1200 + CRC32 LE liczony z numeru i RGB (1212 bajtów).
- UDP DDP: port 4048, DDP v1, RGB24, display ID 1, obsługa offsetów i flagi PUSH. Brak gwarancji doręczenia.
- UDP statystyki: tekst `stats` na port 4049, odpowiedź JSON.

## Testy i zmiany

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r remote_app/requirements.txt
python -m unittest discover -s remote_app/tests -v
node --check remote_app/static/app.js
python esp32_led_standalone/prepare_assets.py
```

Testy backendu uruchamiają własny tymczasowy serwer i katalog danych. Sprawdzają autoryzację, zapis stanu, błędy walidacji, strumień, odróżnienie obrazu od pokazu i zatrzymywanie animacji. Nie łączą się ze sprzętem ani prywatną instalacją. Testy harmonogramu obejmują granice godzin, północ, zmianę czasu, zgodność starszego zapisu, błędy zapisu i klatki API przed oraz po godzinie przełączenia.

`remote_app/tests/schedule_browser.cjs` to dodatkowy test mobilnego panelu w Playwright. Wymaga tymczasowego lokalnego serwera z aktywną, nieczarną sceną, `LED_TEST_URL`, `BASIC_USER` i `BASIC_PASSWORD`. Zmienia harmonogram tej instancji; celowo odrzuca adresy spoza localhost. Instrukcja uruchomienia znajduje się na początku pliku.

Do lokalnego podglądu można uruchomić `app.py` z ustawionymi `BASIC_USER`, `BASIC_PASSWORD`, `DEVICE_TOKEN`, `DATA_DIR`, `BIND=127.0.0.1`, `PORT=8080` i bez `CERT_FILE`. Jest to HTTP wyłącznie do lokalnego rozwoju; wdrożenie i ESP32 korzystają z HTTPS. Dane demonstracyjne można zbudować z plików `christmas/*shapes.json` przez API.

Zmiany lokalnego panelu wykonuj w `panel.html`, po czym generuj `page.h`. Wzorce bitów LED i GPIO znajdują się w pliku `.ino`. `make_font.py` odtwarza font (Pillow i systemowy DejaVuSans-Bold). Nie edytuj wyłącznie wygenerowanych plików.

## Ochrona konfiguracji

Repozytorium ignoruje `.env`, prywatne nagłówki, certyfikaty, klucze, katalogi danych i binarki. To nie zastępuje kontroli `git diff --cached` przed publikacją. Nie dodawaj logów z adresami urządzeń, kopii stanu biblioteki ani obrazów firmware zawierających hasła. Token urządzenia i hasło panelu powinny być różnymi losowymi wartościami. OTA nie jest systemem podpisów producenta: aktualizacje udostępnia administrator własnego serwera.
