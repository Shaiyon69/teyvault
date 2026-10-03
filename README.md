# Teyvault

A Genshin Impact companion for Windows, Android and iOS, with a matching CLI.

- **Dashboard**: automatic HoYoLAB daily check-in, the monthly reward calendar, and promo code redeeming.
- **Events**: timeline of current and upcoming events, banners, Spiral Abyss, Imaginarium Theater and Battle Pass (from paimon.moe).
- **Wishes**: wish history synced from the game, with pity, 50/50 record, and 5★/4★ history sorted by date. UIGF and Excel import/export, plus phone sync over Wi-Fi.
- **World / Characters**: exploration progress and character builds (constellations, talents, artifacts with Crit Value) from Battle Chronicle.
- **Wiki**: searchable, filterable characters, weapons, artifacts, enemies and achievements. You tick off achievements yourself.
- Themes: Classic, Material You, Glass and Nothing, each in light or dark.

Global (`os_*`) servers only. Your cookies stay in the OS keyring and are never sent anywhere except HoYoLAB.

## Install

Download from the [latest release](https://github.com/Shaiyon69/teyvault/releases/latest):

- **Windows**: `Teyvault-Setup.exe`. Run it and click through; no admin rights needed. Windows SmartScreen may warn because the installer isn't code-signed: click *More info* then *Run anyway*.
- **Android**: `Teyvault.apk`. Open it on your phone and allow installing from your browser when asked.

Your wish history and sign-in are kept when you update or reinstall.

## Run from source

```sh
pip install -e .
teyvault-gui        # desktop app
teyvault wish stats # CLI
python -m unittest discover -s tests
```

Package mobile with `flet build apk | ipa`. Pushing a `v*` tag builds the Windows installer and APK and publishes them as a GitHub Release (`.github/workflows/release.yml`).

Made by [Shaiyon69](https://github.com/Shaiyon69). Not affiliated with HoYoverse.
