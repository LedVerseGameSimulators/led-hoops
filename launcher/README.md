# LED Hoops launcher

Build the operator `LED Hoops.exe` on Windows with PyInstaller:

```bat
pip install pyinstaller
pyinstaller launcher/LED_Hoops.spec --noconfirm
```

The executable is written to `dist/LED Hoops.exe`. Place it next to `START_GAME.bat` in the release folder (or use the GitHub Actions `Package Windows` workflow on a `v*` tag).
