import asyncio
import logging
import os
from dotenv import load_dotenv
from src.telegram_view.view import TelegramView
from agent_ti.utils.schemas import AgentRequest, AgentResponse


def setup_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("telegram_bot.log")],
    )


async def dummy_callback(request: AgentRequest) -> AgentResponse:
    """A dummy callback function that echoes back the message"""
    print(f"Received request: {request}")
    # In a real implementation, this would be your orchestrator callback
    return AgentResponse(
        chat_id=request.chat_id, message=f"Echo: {request.message}", status="success"
    )


async def main():
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    # Load environment variables
    load_dotenv()
    logger.info("Environment variables loaded")

    # Get bot token
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        print("Please set TELEGRAM_BOT_TOKEN in your environment variables")
        return

    # Initialize and run the bot
    logger.info("Starting Telegram bot")
    bot = TelegramView(dummy_callback)
    try:
        await bot.run()
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error: {e}")
