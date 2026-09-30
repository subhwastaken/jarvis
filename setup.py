"""Build the app bundle in alias mode, it runs the code straight from this folder: python setup.py py2app -A"""
from setuptools import setup

APP_NAME = "NIKO"

setup(
    name=APP_NAME,
    app=["app.py"],
    options={"py2app": {
        "argv_emulation": False,
        "iconfile": "assets/icon.icns",
        "plist": {
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleIdentifier": "com.niko.app",
            "CFBundleShortVersionString": "0.2",
            "LSUIElement": False,
            "NSHighResolutionCapable": True,
            "NSMicrophoneUsageDescription": "NIKO listens for your commands.",
            "NSAppleEventsUsageDescription": "NIKO controls Spotify, volume and dark mode for you.",
        },
    }},
    setup_requires=["py2app"],
)
