"""Main entry point for the SSH GPU Monitor."""
import asyncio
from .main import main
from .src.config_loader import load_config

def main_entry():
    """Entry point for the console script."""
    config = load_config()
    asyncio.run(main(config))

if __name__ == '__main__':
    main_entry() 