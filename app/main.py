from app.config.paths import ensure_runtime_dirs
from app.core.logging_setup import setup_logging
from app.gui.main_window import launch_gui


def main():
    ensure_runtime_dirs()
    logger = setup_logging()
    logger.info("Starting TSLA Two-Ticker Trader — Section 03")
    launch_gui()
if __name__ == "__main__":
    main()
