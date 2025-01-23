import asyncio
import logging
from typing import Optional, Callable
import os
from src.view import View

logger = logging.getLogger(__name__)

def run_telegram_view(callback: Optional[Callable] = None):
    """
    Run the telegram view with the given callback
    
    Args:
        callback: Optional callback function to handle messages
    """
    logger.info("Initializing Telegram view")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
    
    try:
        view = View(token=token, view_callback=callback)
        # Run the view in an async context
        asyncio.run(view.run())
    except Exception as e:
        logger.error(f"Error running telegram view: {e}")
        raise