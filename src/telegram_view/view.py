import logging
from typing import Callable, Optional, Dict, List, Any
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio
import os
import traceback
from view_utils.view_abc import BaseView
from .messages import get_message
from .utils import handle_issue_report

# from utils.schemas import AgentRequest, AgentRequestType, AgentResponse
from agent_ti.utils.schemas import (
    AgentRequest,
    AgentRequestType,
    AgentResponse,
    RequestStatus,
    Metadata,
)

logger = logging.getLogger(__name__)


class TelegramView(BaseView):
    def __init__(self, view_callback, view_config):
        super().__init__()
        logger.info("Initializing Telegram View")
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.view_callback = view_callback
        self.view_config = view_config
        # Store chat history as a list of dictionaries with type and message
        self.chat_history = []
        # Track which users are in issue reporting mode
        self.reporting_users: set[int] = set()

        # Register handlers
        logger.debug("Registering message handlers")
        self.dp.message.register(self._start_command, Command(commands=["start"]))
        self.dp.message.register(
            self._delete_all_history, Command(commands=["delete_all_history"])
        )
        self.dp.message.register(self._handle_message)

    @classmethod
    def from_config(cls, view_config, callback: Callable) -> "TelegramView":
        """
        Creates TelegramView instance from config.

        Args:
            view_config: Either a TelegramViewConfig from the new config system or a dict for backward compatibility
            callback: The callback function to handle view events

        Returns:
            TelegramView: A configured view instance
        """
        # Currently, TelegramView doesn't use any special configuration,
        # but this ensures future compatibility with the config system
        # We can add Telegram-specific parameters here when needed
        return cls(view_callback=callback, view_config=view_config)

    async def send_message(self, response: AgentResponse) -> str:
        """Send a message to the chat - this is used by the orchestrator

        Args:
            response: AgentResponse object containing chat_id and message to send

        Returns:
            str: The message that was sent, or empty string if no message was available
        """
        chat_id = response.chat_id
        message = response.message or ""

        logger.debug(
            f"Sending message to {chat_id}: {message[:50]}... (length: {len(response)})"
        )
        sent_message = await self.bot.send_message(chat_id=chat_id, text=message)
        # Add bot's response to chat history
        if message:  # Only add non-empty messages
            self.chat_history.append({"type": "ai", "message": message})
        return message

    def _get_main_keyboard(self) -> ReplyKeyboardMarkup:
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

    async def _start_command(self, message: types.Message):
        """Handle the /start command"""
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        language_code = (
            message.from_user.language_code if message.from_user.language_code else "en"
        )
        logger.info(f"Received /start command from user {username} (ID: {user_id})")

        # Clear history in Graph and local chat history
        if self.view_callback:
            request = AgentRequest(
                chat_id=user_id,
                type=AgentRequestType.DELETE_ENTRIES_BY_CHAT_ID,
                user_details={
                    "username": username,
                    "name": f"{first_name} {last_name}".strip(),
                },
                bypass=True,  # Set bypass since this is a control message
            )

            logger.info("Sending delete_history request")
            try:
                await self.view_callback(request)
            except Exception as e:
                logger.error(
                    f"Error in view_callback for delete_history: {e}\n{traceback.format_exc()}"
                )

        # Clear local chat history
        self.chat_history.clear()
        self.reporting_users.discard(user_id)

        # Send welcome message with keyboard
        keyboard = self._get_main_keyboard()

        # Send welcome message
        welcome_msg = self.view_config.title
        await message.answer(welcome_msg, reply_markup=keyboard)
        self.chat_history.append({"type": "ai", "message": welcome_msg})

    async def _delete_all_history(self, message: types.Message):
        agent_request = AgentRequest(
            chat_id=0,  # Using 0 as a placeholder for all chats
            type=AgentRequestType.DELETE_HISTORY,
            message=None,
        )

        logger.info(f"Sending delete_history request: {agent_request}")

        try:
            await self.view_callback(agent_request)
            # Clear local chat history
            self.chat_history.clear()
        except Exception as e:
            logger.error(
                f"Error in view_callback for delete_history: {e}\n{traceback.format_exc()}"
            )

    async def _handle_message(self, message: types.Message):
        """Handle incoming messages"""
        user_id = message.from_user.id
        username = message.from_user.username
        full_name = message.from_user.full_name
        language_code = (
            message.from_user.language_code if message.from_user.language_code else "en"
        )

        # Add user message to chat history
        if message.text:  # Only add non-empty messages
            self.chat_history.append({"type": "user", "message": message.text})

        logger.info(
            f"[View] Received message from user {username} (ID: {user_id}): {message.text[:50]}..."
        )
        await message.bot.send_chat_action(message.chat.id, "typing")

        try:
            if message.content_type != "text":
                error_message = get_message("error", language_code)
                await message.answer(
                    error_message, reply_markup=self._get_main_keyboard()
                )
                self.chat_history.append({"type": "ai", "message": error_message})
                return

            # Handle special button commands
            if message.text == "🔄 Start New Chat":
                await self._start_command(message)
                return
            elif message.text == "⚠️ Report Issue":
                self.reporting_users.add(user_id)
                prompt = "Please describe the issue: "
                await message.answer(prompt, reply_markup=self._get_main_keyboard())
                self.chat_history.append({"type": "ai", "message": prompt})
                return
            elif user_id in self.reporting_users:
                # Handle issue report submission
                self.reporting_users.remove(user_id)
                # Get current chat history before handling the report
                await handle_issue_report(user_id, message.text, self.chat_history)
                confirmation = "Thank you for reporting the issue, starting new chat..."
                await message.answer(
                    confirmation, reply_markup=self._get_main_keyboard()
                )
                self.chat_history.append({"type": "ai", "message": confirmation})
                # Clear chat history after issue report to prevent old messages in future reports
                await self._start_command(message)
                
                return

            # Handle normal messages
            request = AgentRequest(
                chat_id=user_id,
                type=AgentRequestType.TEXT,
                message=message.text,
                user_details={
                    "username": username,
                    "name": full_name,
                    "language_code": language_code,
                },
                bypass=False,
            )

            logger.debug(f"Sending message request to orchestrator: {request}")

            if self.view_callback:
                try:
                    response = await self.view_callback(request)
                    if response and response.message:
                        # send_message will add the response to chat history
                        await self.send_message(response)
                except Exception as e:
                    logger.error(
                        f"Error in view_callback: {e}\n{traceback.format_exc()}"
                    )
                    error_message = get_message("error", language_code)
                    await message.answer(
                        error_message, reply_markup=self._get_main_keyboard()
                    )
                    self.chat_history.append({"type": "ai", "message": error_message})

        except Exception as e:
            logger.error(f"Error handling message: {e}\n{traceback.format_exc()}")
            error_message = get_message("error", language_code)
            await message.answer(error_message, reply_markup=self._get_main_keyboard())
            self.chat_history.append({"type": "ai", "message": error_message})

    async def run(self):
        """Run the telegram bot"""
        logger.debug("Starting telegram bot")
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
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "telegram_bot.log"
                )
            ),
        ],
    )

    # Load environment variables
    load_dotenv()
    logger.info("Environment variables loaded")

    # Run the bot
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        logger.info("Starting bot")
        bot = TelegramView(None)
        asyncio.run(bot.run())
    else:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        print("Please set TELEGRAM_BOT_TOKEN in your environment variables")
