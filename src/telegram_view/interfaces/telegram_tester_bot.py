import logging
from typing import Callable, Optional, Dict
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import traceback
from ..messages import get_message
from .tester_utils import handle_issue_report
from common_utils.logging.bug_catcher import report_error_if_enabled
from common_utils.allowed_models import ALLOWED_MODELS, get_model_by_id
from .image_utils import get_image_as_url
from .file_utils import get_file_as_base64, get_audio_as_base64, is_supported_document

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
        # Per-user model preferences storage
        self.user_model_preferences: Dict[int, str] = {}
        # Check if model selector should be shown (from view config)
        self.show_model_selector = getattr(getattr(config, 'view', None), 'show_model_selector', False)

    def get_user_model(self, user_id: int) -> Optional[str]:
        """Get the selected model for a user, or None for default"""
        return self.user_model_preferences.get(user_id)

    def set_user_model(self, user_id: int, model_id: str) -> None:
        """Set the selected model for a user"""
        self.user_model_preferences[user_id] = model_id
        logger.info(f"User {user_id} selected model: {model_id}")

    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Create a keyboard with the main action buttons"""
        buttons = [
            [
                KeyboardButton(text="🔄 Start New Chat"),
                KeyboardButton(text="⚠️ Report Issue"),
            ],
        ]
        # Add model selector button if enabled in config
        if self.show_model_selector:
            buttons.append([KeyboardButton(text="🤖 Select Model")])
        
        keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, is_persistent=True)
        return keyboard

    def get_model_selection_keyboard(self) -> InlineKeyboardMarkup:
        """Create an inline keyboard with available models"""
        buttons = []
        for model in ALLOWED_MODELS:
            buttons.append([InlineKeyboardButton(text=model["name"], callback_data=f"select_model:{model['id']}")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def send_message(self, chat_id: int, message: str) -> None:
        """Send a message via Telegram bot"""
        try:
            logger.debug(f"Sending message to {chat_id}: {message[:50]}...")
            await self.bot.send_message(chat_id=chat_id, text=message)
            # Add AI response to chat history for issue reporting
            self.chat_history.append({"type": "ai", "message": message})
        except Exception as e:
            # Report error using the centralized bug catcher function
            report_error_if_enabled(
                self.config, 
                e, 
                "Error sending message (Tester Interface)", 
                {"chat_id": chat_id, "message_length": len(message)}
            )
            
            logger.error(f"Error sending message: {e}\n{traceback.format_exc()}")
            raise

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

    def _get_current_model_info(self, user_id: int) -> dict:
        """Get the model info for the current session - either user-selected or config default."""
        selected_model_id = self.get_user_model(user_id)
        
        if selected_model_id:
            # User explicitly selected a model
            model_info = get_model_by_id(selected_model_id)
            if model_info:
                return {**model_info, "source": "user_selected"}
        
        # Fall back to config default
        llm_config = getattr(self.config, 'llm', None)
        if llm_config and hasattr(llm_config, 'large'):
            large_config = llm_config.large
            return {
                "id": getattr(large_config, 'model', 'unknown'),
                "provider": getattr(large_config, 'provider', 'unknown'),
                "temperature": getattr(large_config, 'temperature', None),
                "source": "config_default"
            }
        
        return {"source": "unknown"}

    async def _handle_issue_submission(self, message: types.Message):
        """Handle issue report submission"""
        user_id = message.from_user.id
        self.reporting_users.remove(user_id)
        
        # Get model info (either user-selected or config default)
        model_info = self._get_current_model_info(user_id)
        
        await handle_issue_report(user_id, message.text, self.chat_history, self.config, model_info)
        confirmation = "Thank you for reporting the issue, starting new chat..."
        await message.answer(confirmation, reply_markup=self.get_main_keyboard())
        self.chat_history.append({"type": "ai", "message": confirmation})
        # Need to call start_command - we'll handle this in setup_handlers

    async def _handle_model_selection(self, message: types.Message):
        """Handle the model selection command - show inline keyboard with models"""
        user_id = message.from_user.id
        current_model = self.get_user_model(user_id)
        current_model_name = "Default"
        if current_model:
            for model in ALLOWED_MODELS:
                if model["id"] == current_model:
                    current_model_name = model["name"]
                    break
        
        prompt = f"Current model: {current_model_name}\n\nSelect a model:"
        await message.answer(prompt, reply_markup=self.get_model_selection_keyboard())
        self.chat_history.append({"type": "ai", "message": prompt})

    def setup_handlers(self, handle_message: Callable, config):
        """Setup message handlers for the Telegram bot
        
        Args:
            orchestrator_callback: Function to call when messages are received
            config: Configuration object with title and other settings
        """
        
        async def process_message(message: types.Message, message_type: str, text: str = None):
            """Unified message processing function"""
            user_id = message.from_user.id
            chat_id = message.chat.id
            username = message.from_user.username
            first_name = message.from_user.first_name
            last_name = message.from_user.last_name
            language_code = message.from_user.language_code or "en"
            
            # Get user's selected model (if any)
            selected_model = self.get_user_model(user_id)
            
            # Create unified message data structure
            message_data = {
                "type": message_type,
                "user_id": user_id,
                "chat_id": chat_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "full_name": message.from_user.full_name,
                "language_code": language_code,
                "text": text,
                "timestamp": int(message.date.timestamp()),
                "settings": {"model": selected_model} if selected_model else {}
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
                # Report error using the centralized bug catcher function
                report_error_if_enabled(
                    config, 
                    e, 
                    "Error in orchestrator callback (Tester Interface)", 
                    {"message_type": message_type, "user_id": message.from_user.id}
                )
                
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
            # logging.debug(f"Message: {message}")
            # Clear local state before processing
            user_id = message.from_user.id
            self.chat_history.clear()
            self.reporting_users.discard(user_id)
            
            # Process message through orchestrator
            await process_message(message, "start_command")
            
            # Send welcome message with keyboard
            keyboard = self.get_main_keyboard()
            welcome_msg = config.title
            
            # Add model info if model selector is enabled
            if self.show_model_selector:
                model_info = self._get_current_model_info(user_id)
                model_name = model_info.get("name") or model_info.get("id", "Unknown")
                welcome_msg += f"\n\n🤖 Model: {model_name}"
            
            await message.answer(welcome_msg, reply_markup=keyboard)
            self.chat_history.append({"type": "ai", "message": welcome_msg})

        @self.dp.message(Command(commands=["delete_all_history"]))
        async def delete_all_history(message: types.Message):
            """Handle delete all history command"""
            # Process message through orchestrator
            await process_message(message, "delete_all_history")
            
            # Clear local chat history after orchestrator processes the request
            self.chat_history.clear()

        @self.dp.callback_query(F.data.startswith("select_model:"))
        async def handle_model_selection_callback(callback: CallbackQuery):
            """Handle model selection from inline keyboard"""
            user_id = callback.from_user.id
            model_id = callback.data.split(":")[1]
            
            # Find model name for confirmation message
            model_name = model_id
            for model in ALLOWED_MODELS:
                if model["id"] == model_id:
                    model_name = model["name"]
                    break
            
            # Store user's model preference
            self.set_user_model(user_id, model_id)
            
            # Acknowledge the callback and update message
            await callback.answer(f"Selected: {model_name}")
            await callback.message.edit_text(f"✅ Model changed to: {model_name}\n\nYour next messages will use this model.")

        @self.dp.message()
        async def handle_telegram_message(message: types.Message):
            """Handle incoming messages"""
            # logging.debug(f"Telegram Message: {message}")

            user_id = message.from_user.id
            language_code = message.from_user.language_code or "en"

            # Add user message to chat history
            if message.text:
                self.chat_history.append({"type": "user", "message": message.text})

            await message.bot.send_chat_action(message.chat.id, "typing")

            try:
                if message.content_type == "photo":
                    # Handle photo messages - get URL instead of base64
                    image_url = await get_image_as_url(self.bot, message)
                    if image_url:
                        caption = message.caption if message.caption else ""
                        
                        # Create combined image data with URL
                        image_data = {
                            "image": image_url,
                            "caption": caption
                        }
                        
                        # Add to chat history
                        chat_message = caption if caption else "Image sent"
                        self.chat_history.append({"type": "user", "message": chat_message})
                        
                        # Process as an image message
                        await process_message(message, "image_message", image_data)
                    return
                
                elif message.content_type == "document":
                    # Handle document messages (PDF, DOC, TXT)
                    if not is_supported_document(message):
                        await self._send_unsupported_content_message(message, language_code)
                        return
                    
                    caption = message.caption if message.caption else ""
                    file_name = message.document.file_name if message.document else "document"
                    
                    # Use base64 to embed file content for persistence across turns
                    logger.debug(f"Processing document: {file_name}")
                    file_result = await get_file_as_base64(self.bot, message)
                    
                    if file_result:
                        file_data, mime_type = file_result
                        logger.info(f"Document encoded to base64: {file_name} ({mime_type}, {len(file_data)} chars)")
                        document_data = {
                            "file": file_data,
                            "mime_type": mime_type,
                            "file_name": file_name,
                            "caption": caption
                        }
                        
                        chat_message = caption if caption else f"Document sent: {file_name}"
                        self.chat_history.append({"type": "user", "message": chat_message})
                        
                        await process_message(message, "document_message", document_data)
                    else:
                        logger.error(f"Failed to encode document to base64: {file_name}")
                    return
                
                elif message.content_type in ["voice", "audio"]:
                    # Handle voice/audio messages
                    caption = message.caption if message.caption else ""
                    
                    # Use base64 to embed audio content for persistence across turns
                    logger.debug(f"Processing audio message (type: {message.content_type})")
                    audio_result = await get_audio_as_base64(self.bot, message)
                    
                    if audio_result:
                        audio_data, mime_type = audio_result
                        logger.info(f"Audio encoded to base64: {mime_type} ({len(audio_data)} chars)")
                        audio_msg_data = {
                            "audio": audio_data,
                            "mime_type": mime_type,
                            "caption": caption
                        }
                        
                        chat_message = caption if caption else "Audio message sent"
                        self.chat_history.append({"type": "user", "message": chat_message})
                        
                        await process_message(message, "audio_message", audio_msg_data)
                    else:
                        logger.error(f"Failed to encode audio to base64")
                    return
                
                elif message.content_type not in ["text", "photo", "document", "voice", "audio"]:
                    await self._send_unsupported_content_message(message, language_code)
                    return

                # Handle model selection button
                if message.text == "🤖 Select Model" and self.show_model_selector:
                    await self._handle_model_selection(message)
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
                # Report error using the centralized bug catcher function
                report_error_if_enabled(
                    config, 
                    e, 
                    "Error handling message (Tester Interface)", 
                    {"user_id": message.from_user.id, "content_type": message.content_type}
                )
                
                logger.error(f"Error handling message: {e}\n{traceback.format_exc()}")
                await self._send_error_message(message, language_code)

    async def run(self):
        """Run the telegram bot"""
        logger.debug("Starting telegram bot polling")
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            # Report error using the centralized bug catcher function
            report_error_if_enabled(
                self.config, 
                e, 
                "Critical error in telegram bot polling (Tester Interface)", 
                {"bot_token_configured": bool(self.bot.token)}
            )
            
            logger.error(f"Error running telegram bot: {e}\n{traceback.format_exc()}")
            raise
        finally:
            await self.bot.session.close() 