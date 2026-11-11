# Firmware 2.4 — ostatnia klatka przy utracie połączenia

Wersja: `LED400 2.4 hold-last-frame 2026-11-11`.

## Problem i zmiana

W wersji 2.3 brak klatek z serwera przez około 3 sekundy uruchamiał generator lokalny zapisany w ESP32. Powodowało to nieoczekiwane pojawianie się lokalnego tekstu lub efektu podczas animacji albo gry.

**W wersji 2.4 ESP32 zachowuje ostatnią kompletną klatkę.** Nadal próbuje połączyć się z serwerem i automatycznie aktualizuje obraz po powrocie transmisji. Nie trzeba naciskać Play ponownie tylko z powodu przerwy w strumieniu.

| Sytuacja | Zachowanie 2.4 |
|---|---|
| Serwer przesyła dane | Wyświetlanie kolejnych klatek |
| Transmisja chwilowo ustaje | Zatrzymanie ostatniego obrazu |
| Brak nowych danych przez ponad 3 s | Status braku połączenia; obraz pozostaje nieruchomy |
| Ostatnia klatka była czarna | Lampki pozostają wygaszone |
| Transmisja wraca | Automatyczne wznowienie wyświetlania |
| Restart lub ponowne zasilenie ESP32 | Czarny obraz do otrzymania pierwszej klatki w trybie serwera |
| Ręczny wybór generatora lokalnego | Działa lokalny tekst lub efekt zgodnie z ustawieniami |

Klatka pozostaje w pamięci RAM, nie jest zapisywana do Flash. Zatrzymanie obrazu nie oznacza restartu ESP32 ani zmiany wybranego źródła.

## Aktualizacja istniejącej instalacji

Zmiana znajduje się w **firmware ESP32**. Aktualizacja samej aplikacji Docker nie zmieni zachowania urządzenia z wersją 2.3.

1. Zachowaj swoje lokalne `wifi_secrets.h` i `remote_secrets.h`; nie dodawaj ich do GitHuba.
2. Pobierz aktualny kod projektu i skompiluj firmware zgodnie z [instrukcją wdrożenia](WDROZENIE.md#1-sprzęt-i-firmware). Sprawdzony pakiet Arduino ESP32: **3.2.1**.
3. Otwórz lokalne `http://ADRES_ESP/update` i wyślij plik aplikacji `esp32_led_standalone.ino.bin`. Alternatywnie umieść go na własnym serwerze jako `releases/led400.bin` i wybierz aktualizację z serwera.
4. Poczekaj na zakończenie aktualizacji i restart, pozostawiając zasilanie.
5. W lokalnym panelu lub `GET /api/remote` sprawdź wersję **2.4 hold-last-frame** i ponowne odbieranie klatek.

Pełny opis plików, logowania i OTA: [OTA bez kabla](WDROZENIE.md#ota-bez-kabla). Nie wgrywaj obrazu merged, bootloadera ani tablicy partycji. Binarka skompilowana z własnymi ustawieniami zawiera dane dostępowe; nie publikuj jej razem ze źródłami.

## Diagnostyka

Lokalny panel przy przerwie w strumieniu pokazuje informację **„zachowuję ostatnią klatkę”**. W `GET /api/remote` przydatne są:

- `version` — identyfikator uruchomionego firmware;
- `connected` — czy ostatnia klatka przyszła w ciągu ostatnich 3 sekund;
- `ageMs` — czas od ostatniej odebranej klatki; przed pierwszą klatką wynosi 0;
- `frames` — licznik odebranych klatek od uruchomienia;
- `fallback` — pole zachowane dla zgodności API; w wersji 2.4 oznacza oczekiwanie z zatrzymanym obrazem, **nie uruchomienie lokalnego generatora**.

Jeżeli nadal pojawia się lokalny napis, sprawdź wersję działającą na ESP32 oraz wybrane źródło. Sam plik na serwerze nie oznacza, że został już wgrany do urządzenia.

## Harmonogram i gry

Harmonogram jest wykonywany przez serwer. Podczas braku połączenia ESP32 nie otrzyma nowego polecenia wygaszenia: pozostanie ostatnia klatka, nawet gdy w tym czasie minie godzina wyłączenia. Po powrocie połączenia otrzyma aktualny obraz, w tym czarną klatkę poza godzinami świecenia.

Podczas gry obraz na LED-ach może zastygnąć, mimo że telefon nadal steruje serwerem. W takim przypadku użyj pauzy do czasu powrotu transmisji. Ta zmiana nie dodaje automatycznej pauzy silnika gry w reakcji na utratę połączenia samego ESP32.

## Wynik sprawdzenia na urządzeniu

11 listopada 2026:

- Firmware skompilowano dla klasycznego ESP32 i wgrano przez OTA.
- Potwierdzono uruchomienie wersji 2.4 oraz ponowny odbiór strumienia.
- Wstrzymano serwer na **9 sekund**, bez zmiany zapisanej sceny.
- Po przekroczeniu progu 3 sekund kolejne odczyty podglądu RGB były identyczne; lokalny napis nie zastąpił obrazu.
- Po wznowieniu serwera połączenie wróciło automatycznie, a licznik klatek ponownie rósł.
- Porównanie konfiguracji ESP32 przed i po aktualizacji potwierdziło zachowanie ustawień.

Był to test zatrzymania transmisji przez wstrzymanie serwera. Nie obejmował wszystkich możliwych usterek sieci ani pomiaru czasu powrotu po zerwaniu Wi-Fi.
