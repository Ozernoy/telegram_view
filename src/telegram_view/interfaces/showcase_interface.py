import logging
from typing import Callable, Optional, Dict, List, Any
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import traceback
from ..messages import get_message

logger = logging.getLogger(__name__)


class ShowcaseInterface:
    """Showcase Telegram bot interface - handles only basic functionality with start new chat button"""
    
    def __init__(self, token: str, config):
        """Initialize the Telegram bot interface"""
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.chat_history = []
        self.config = config

    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Create a keyboard with only the start new chat button"""
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="🔄 Start New Chat"),
                ],
            ],
            resize_keyboard=True,
            is_persistent=True,
        )
        return keyboard

    async def send_message(self, chat_id: int, message: str) -> None:
        """Send a message via Telegram bot"""
        logger.debug(f"Sending message to {chat_id}: {message[:50]}...")
        await self.bot.send_message(chat_id=chat_id, text=message)
        # Add AI response to chat history
        self.chat_history.append({"type": "ai", "message": message})

    async def _send_error_message(self, message: types.Message, language_code: str):
        """Send an error message to the user"""
        error_message = get_message("error", language_code)
        await message.answer(error_message, reply_markup=self.get_main_keyboard())
        self.chat_history.append({"type": "ai", "message": error_message})

    def setup_handlers(self, handle_message: Callable, config):
        """Setup message handlers for the Telegram bot
        
        Args:
            handle_message: Function to call when messages are received
            config: Configuration object with title and other settings
        """
        
        async def process_message(message: types.Message, message_type: str, text: str = None):
            """Unified message processing function"""
            user_id = message.from_user.id
            username = message.from_user.username
            first_name = message.from_user.first_name
            last_name = message.from_user.last_name
            language_code = message.from_user.language_code or "en"
            
            # Create unified message data structure
            message_data = {
                "type": message_type,
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "full_name": message.from_user.full_name,
                "language_code": language_code,
                "text": text
            }
            
            logger.info(f"Processing {message_type} from user {username} (ID: {user_id})")
            
            # Call orchestrator callback
            try:
                await handle_message(message_data)
            except Exception as e:
                logger.error(f"Error in orchestrator callback: {e}\n{traceback.format_exc()}")
                if message_type == "text_message":
                    # Only show error to user for text messages
                    error_message = get_message("error", language_code)
                    await message.answer(error_message, reply_markup=self.get_main_keyboard())
        
        @self.dp.message(Command(commands=["start"]))
        async def start_command(message: types.Message):
            """Handle the /start command"""
            logging.debug(f"Message: {message}")
            # Clear local state before processing
            user_id = message.from_user.id
            self.chat_history.clear()
            
            # Process message through orchestrator
            await process_message(message, "start_command")
            
            # Send welcome message with keyboard
            keyboard = self.get_main_keyboard()
            welcome_msg = config.title
            await message.answer(welcome_msg, reply_markup=keyboard)
            self.chat_history.append({"type": "ai", "message": welcome_msg})

        @self.dp.message(Command(commands=["delete_all_history"]))
        async def delete_all_history(message: types.Message):
            """Handle delete all history command"""
            # Process message through orchestrator
            await process_message(message, "delete_all_history")
            
            # Clear local chat history after orchestrator processes the request
            self.chat_history.clear()

        @self.dp.message()
        async def handle_telegram_message(message: types.Message):
            """Handle incoming messages"""
            user_id = message.from_user.id
            language_code = message.from_user.language_code or "en"

            # Add user message to chat history
            if message.text:
                self.chat_history.append({"type": "user", "message": message.text})

            await message.bot.send_chat_action(message.chat.id, "typing")

            try:
                if message.content_type != "text":
                    await self._send_error_message(message, language_code)
                    return

                # Handle start new chat button
                if message.text == "🔄 Start New Chat":
                    await start_command(message)
                    return

                # Handle normal text messages
                await process_message(message, "text_message", message.text)

            except Exception as e:
                logger.error(f"Error handling message: {e}\n{traceback.format_exc()}")
                await self._send_error_message(message, language_code)

    async def run(self):
        """Run the telegram bot"""
        logger.debug("Starting telegram bot polling")
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Error running telegram bot: {e}\n{traceback.format_exc()}")
            raise
        finally:
            await self.bot.session.close() 