import logging
from typing import Callable, Optional, Dict, List, Any
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import traceback
from ..messages import get_message
from .tester_utils import handle_issue_report

logger = logging.getLogger(__name__)


class TesterBotInterface:
    """Pure Telegram bot interface - handles only Telegram-specific functionality"""
    
    def __init__(self, token: str, config):
        """Initialize the Telegram bot interface"""
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.chat_history = []
        self.reporting_users: set[int] = set()
        self.config = config

    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Create a keyboard with the main action buttons"""
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="🔄 Start New Chat"),
                    KeyboardButton(text="⚠️ Report Issue"),
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
        # Add AI response to chat history for issue reporting
        self.chat_history.append({"type": "ai", "message": message})

    async def _send_error_message(self, message: types.Message, language_code: str):
        """Send an error message to the user"""
        error_message = get_message("error", language_code)
        await message.answer(error_message, reply_markup=self.get_main_keyboard())
        self.chat_history.append({"type": "ai", "message": error_message})

    async def _send_unsupported_content_message(self, message: types.Message, language_code: str):
        """Send a message for unsupported content types"""
        unsupported_message = get_message("unsupported_content", language_code)
        await message.answer(unsupported_message, reply_markup=self.get_main_keyboard())
        self.chat_history.append({"type": "ai", "message": unsupported_message})

    async def _handle_report_issue(self, message: types.Message):
        """Handle the report issue command"""
        user_id = message.from_user.id
        self.reporting_users.add(user_id)
        prompt = "Please describe the issue: "
        await message.answer(prompt, reply_markup=self.get_main_keyboard())
        self.chat_history.append({"type": "ai", "message": prompt})

    async def _handle_issue_submission(self, message: types.Message):
        """Handle issue report submission"""
        user_id = message.from_user.id
        self.reporting_users.remove(user_id)
        await handle_issue_report(user_id, message.text, self.chat_history, self.config)
        confirmation = "Thank you for reporting the issue, starting new chat..."
        await message.answer(confirmation, reply_markup=self.get_main_keyboard())
        self.chat_history.append({"type": "ai", "message": confirmation})
        # Need to call start_command - we'll handle this in setup_handlers

    def setup_handlers(self, handle_message: Callable, config):
        """Setup message handlers for the Telegram bot
        
        Args:
            orchestrator_callback: Function to call when messages are received
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
            
            # Call orchestrator callback and DO NOT return response
            try:
                await handle_message(message_data)
                # response = await orchestrator_callback(message_data)
                # if response:
                #     await self.send_message(user_id, response)
                #     self.chat_history.append({"type": "ai", "message": response})
                # return response
            except Exception as e:
                logger.error(f"Error in orchestrator callback: {e}\n{traceback.format_exc()}")
                if message_type == "text_message":
                    # Only show error to user for text messages
                    error_message = get_message("error", language_code)
                    await message.answer(error_message, reply_markup=self.get_main_keyboard())
                    # self.chat_history.append({"type": "ai", "message": error_message})
                # return None
        
        @self.dp.message(Command(commands=["start"]))
        async def start_command(message: types.Message):
            """Handle the /start command"""
            logging.debug(f"Message: {message}")
            # Clear local state before processing
            user_id = message.from_user.id
            self.chat_history.clear()
            self.reporting_users.discard(user_id)
            
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
                if message.content_type == "photo":
                    # Handle photo messages - process like text with [photo] prefix
                    photo_text = "[photo]"
                    if message.caption:
                        photo_text += " " + message.caption
                    
                    # Add to chat history
                    self.chat_history.append({"type": "user", "message": photo_text})
                    
                    # Process as normal text message
                    await process_message(message, "text_message", photo_text)
                    return
                elif message.content_type != "text":
                    await self._send_unsupported_content_message(message, language_code)
                    return

                # Command pattern for special button commands
                command_handlers = {
                    "🔄 Start New Chat": start_command,
                    "⚠️ Report Issue": self._handle_report_issue
                }

                # Execute command if it exists
                command_handler = command_handlers.get(message.text)
                if command_handler:
                    await command_handler(message)
                    return

                # Handle issue report submission
                if user_id in self.reporting_users:
                    await self._handle_issue_submission(message)
                    # After handling issue submission, call start_command
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