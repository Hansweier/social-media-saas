# Instagram Bot - Main Entry Point
from bot.scheduler import start_scheduler
from bot.config import load_config

if __name__ == "__main__":
    print("Instagram Bot startet...")
    config = load_config()
    start_scheduler(config)
