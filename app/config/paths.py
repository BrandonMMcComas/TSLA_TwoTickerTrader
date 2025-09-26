from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
MODELS_DIR = PROJECT_ROOT / "models"
APP_CONFIG_PATH = DATA_DIR / "app_config.json"
LOG_FILE_PATH = LOGS_DIR / "app.log"
def ensure_runtime_dirs():
    for p in (DATA_DIR, LOGS_DIR, MODELS_DIR, DATA_DIR / "sentiment"):
        p.mkdir(parents=True, exist_ok=True)
