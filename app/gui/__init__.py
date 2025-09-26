# Package init for app.gui
# Ensure SettingsPanel is extended with the Sentiment "Run now" button
try:
    from . import settings_panel_ext  # noqa: F401  # side-effect: patches SettingsPanel class
except Exception:
    # safe no-op if extension fails to import
    pass
