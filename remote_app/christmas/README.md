# Grafiki świąteczne

Źródło: [OpenMoji](https://openmoji.org/), autorzy: [OpenMoji contributors](https://github.com/hfg-gmuend/openmoji). Grafiki udostępniono na [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Pełny tekst w `LICENSE.txt`; adresy plików źródłowych i sumy SHA-256 w `sources.json`.

Modyfikacje w tym projekcie: przycięcie przezroczystego marginesu, skalowanie do pola 18×18 i osadzenie w 20×20 na czarnym tle, biała śnieżynka oraz dodatkowe klatki migania i ruchu. Zmodyfikowane grafiki, animacje i ich wizualizacje na zrzutach ekranu zachowują CC BY-SA 4.0.

`originals/` zawiera obrazy źródłowe; `shapes.json` — 10 motywów i pokaz; `animated-shapes.json` — cztery animacje pojedynczych motywów. Import i wdrożenie opisano w [instrukcji](../../docs/WDROZENIE.md). `prepare.py` wymaga Pillow i internetu, `animate.py` korzysta z przygotowanych grafik. Importer używa biblioteki standardowej Pythona, pyta o dane logowania i pomija już istniejące nazwy.
