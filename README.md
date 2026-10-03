# Teyvault

A Genshin Impact companion for Windows, Android and iOS, with a matching CLI.

- **Today**: automatic HoYoLAB daily check-in, the monthly reward calendar, and promo code redeeming.
- **Wishes**: wish history synced from the game, with pity, 50/50 record, and 5★/4★ history sorted by date. UIGF and Excel import/export, plus phone sync over Wi-Fi.
- **World / Characters**: exploration progress and character builds (constellations, talents, artifacts with Crit Value) from Battle Chronicle.
- **Wiki**: searchable, filterable characters, weapons, artifacts, enemies and achievements. You tick off achievements yourself.
- Themes: Classic, Material You, Glass and Nothing, each in light or dark.

Global (`os_*`) servers only. Your cookies stay in the OS keyring and are never sent anywhere except HoYoLAB.

## Run

```sh
pip install -e .
teyvault-gui        # desktop app
teyvault wish stats # CLI
python -m unittest discover -s tests
```

Package with `flet build windows | apk | ipa`.

Made by [Shaiyon69](https://github.com/Shaiyon69). Not affiliated with HoYoverse.
