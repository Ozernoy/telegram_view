import logging
from typing import Callable, Optional
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio
import os
import traceback
from .view_abc import BaseView, RedisEnabledMixin
from .messages import get_message
from utils.schemas import AgentRequest, AgentRequestType

logger = logging.getLogger(__name__)

class TelegramView(RedisEnabledMixin, BaseView):
    def __init__(self, view_callback):
        super().__init__()
        logger.info("Initializing Telegram View")
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.view_callback = view_callback
        
        # Register handlers
        logger.info("Registering message handlers")
        self.dp.message.register(self._start_command, Command(commands=["start"]))
        self.dp.message.register(self._handle_message)

    @classmethod
    def from_config(cls, config: dict, callback: Callable) -> 'TelegramView':
        """Creates TelegramView instance from config"""
        return cls(view_callback=callback)

    async def send_message(self, chat_id: str, message: str, chat_type: str = "c") -> str:
        """Send a message to the chat - this is used by the orchestrator"""
        logger.info(f"Sending message to {chat_id}: {message}")
        await self.bot.send_message(chat_id=chat_id, text=message)
        return message  # Return message for compatibility with other views

    async def _start_command(self, message: types.Message):
        """Handle the /start command"""
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        language_code = message.from_user.language_code if message.from_user.language_code else "en"
        logger.info(f"Received /start command from user {username} (ID: {user_id})")
        
        # Clear history in Graph
        if self.view_callback:
            request = AgentRequest(
                chat_id=user_id,
                type=AgentRequestType.DELETE_ENTRIES_BY_THREAD_ID,
                user_details={"username": username, "name": f"{first_name} {last_name}".strip()},
                bypass=True  # Set bypass since this is a control message
            )
            
            logger.info(f"Sending delete_history request: {request}")
            try:
                await self.view_callback(request)
            except Exception as e:
                logger.error(f"Error in view_callback for delete_history: {e}\n{traceback.format_exc()}")
        
        # Send welcome message asking for business description
        welcome_message = get_message("welcome", language_code)
        # await message.answer(welcome_message)

    async def _handle_message(self, message: types.Message):
        """Handle incoming messages"""
        user_id = message.from_user.id
        username = message.from_user.username
        full_name = message.from_user.full_name
        language_code = message.from_user.language_code if message.from_user.language_code else "en"
        logger.info(f"[View] Received message from user {username} (ID: {user_id}): {message.text[:50]}...")
        
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        try:
            if message.content_type != 'text':
                error_message = get_message("error", language_code)
                await message.answer(error_message)
                return 
            
            # Create AgentRequest
            request = AgentRequest(
                chat_id=user_id,
                type=AgentRequestType.TEXT,
                message=message.text,
                user_details={
                    "username": username,
                    "name": full_name,
                    "language_code": language_code
                },
                bypass=False  # Set bypass=False for normal messages
            )
            
            logger.info(f"[View] Sending message request to orchestrator: {request}")
            
            if self.view_callback:
                try:
                    await self.view_callback(request)
                except Exception as e:
                    logger.error(f"Error in view_callback: {e}\n{traceback.format_exc()}")
                    error_message = get_message("error", language_code)
                    await message.answer(error_message)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}\n{traceback.format_exc()}")
            error_message = get_message("error", language_code)
            await message.answer(error_message)

    async def run(self):
        """Run the telegram bot"""
        logger.info("Starting telegram bot")
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Error running telegram bot: {e}\n{traceback.format_exc()}")
            raise
        finally:
            await self.bot.session.close()

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    # Configure logging for direct execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'telegram_bot.log'))
        ]
    )
    
    # Load environment variables
    load_dotenv()
    logger.info("Environment variables loaded")
    
    # Run the bot
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        logger.info("Starting bot")
        bot = View(None, None)
        asyncio.run(bot.run())
    else:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        print("Please set TELEGRAM_BOT_TOKEN in your environment variables")