<p align="center">
  <img src="assets/logo.png" alt="Auto Spicetify logo" width="120">
</p>

<h1 align="center">Auto Spicetify</h1>

A tiny Windows background app that keeps [Spicetify](https://spicetify.app) applied after Spotify updates, so you don't have to re-run it by hand.

## How it works

Spotify downloads updates in the background and applies them the next time it is relaunched. Auto Spicetify:

1. Starts with Windows (via a Startup shortcut).
2. Waits for Spotify to be running.
3. Compares Spotify's version to the last version it applied Spicetify to.
4. If it changed, runs `spicetify backup apply` — the command the [Spicetify FAQ](https://spicetify.app/docs/faq) says to run after any Spotify update.
5. If that fails, it tries `spicetify upgrade` followed by `spicetify restore backup apply`, then retries hourly (useful when Spicetify hasn't been updated for the new Spotify version yet).

Everything is logged to `%LOCALAPPDATA%\AutoSpicetify\auto_spicetify.log`.

## Requirements

- Windows 10/11
- Spotify installed from [spotify.com](https://www.spotify.com/download/) (**not** the Microsoft Store version — Spicetify doesn't support it)
- [Spicetify](https://spicetify.app/docs/getting-started) installed (the app will try to install it if it's missing, but installing it yourself first is more reliable)

## Install

1. Download `auto_spicetify.exe` from the [Releases](../../releases) page.
2. Double-click it once. That's it.

It copies itself to `%LOCALAPPDATA%\AutoSpicetify`, adds a Startup shortcut and starts running immediately.

> **Note:** On first run it applies Spicetify once, because it has no record of the current Spotify version yet. Spotify may restart when Spicetify is applied — that is normal.

## Uninstall

```
%LOCALAPPDATA%\AutoSpicetify\auto_spicetify.exe --uninstall
```

## Build from source

```
git clone https://github.com/mezzi003e/auto-spicetify.git
cd auto-spicetify
build.bat
```

The executable ends up in `dist\auto_spicetify.exe`. Requires Python 3.9+.

## Limitations

- Spotify sometimes updates before Spicetify supports the new version. Until Spicetify releases a fix, applying will fail; the app keeps retrying hourly and the log shows what happened. See the [Spicetify issue tracker](https://github.com/spicetify/cli/issues).
- Unsigned PyInstaller executables are sometimes flagged by antivirus software. You can review the source and build it yourself.

## Disclaimer

This project is not affiliated with Spotify or Spicetify. Modifying the Spotify client may violate Spotify's terms of service. Use at your own risk.

## License

MIT
