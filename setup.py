
# pip install setuptools py2app
# python3 setup.py py2app

from setuptools import setup

APP = ["main.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "playlist.icns",

    # Menu bar app: no Dock icon.
    "plist": {
        "CFBundleName": "Playlist",
        "CFBundleDisplayName": "Playlist",
        "CFBundleIdentifier": "ai.hackerman.playlist",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        # Hide Dock icon / make it an agent app.
        "LSUIElement": True,
        # Avoid macOS restore-state warning where possible.
        "NSQuitAlwaysKeepsWindows": False,
    },

    # Usually needed for PyObjC/AppKit apps.
    "packages": [
        "rumps",
        "audioplayer",
        "objc",
        "Foundation",
        "AppKit",
        "Quartz",
    ],

    # Pillow is not used in your current version, so do not include it.
    "includes": [
        "pathlib",
    ],

    # Keep the app smaller.
    "excludes": [
        "tkinter",
        "PIL",
        "PyQt5",
        "PyQt6",
        "numpy",
        "scipy",
        "matplotlib",
        "pandas",
    ],
}

setup(
    app=APP,
    name="Playlist",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
)

