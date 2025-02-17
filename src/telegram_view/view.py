import logging
from typing import Callable, Optional
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio
import os
import traceback
from typing import Optional, Callable
from .view_abc import BaseView, RedisEnabledMixin
from .state import UserState
from .messages import WELCOME_MESSAGE, DESCRIPTION_ACCEPTED_MESSAGE, ERROR_MESSAGE

logger = logging.getLogger(__name__)

class View(RedisEnabledMixin, BaseView):
    def __init__(self, app, view_callback):
        super().__init__()
        logger.info("Initializing Telegram View")
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self._original_callback = view_callback
        self.view_callback = self._wrap_callback(view_callback) if view_callback else None
        # Dictionary to track user states and their business descriptions
        self.user_states = {}  # {user_id: {"state": UserState, "business_description": str}}
        
        # Register handlers
        logger.info("Registering message handlers")
        self.dp.message.register(self._start_command, Command(commands=["start"]))
        self.dp.message.register(self._handle_message)

    def _wrap_callback(self, callback: Callable) -> Callable:
        """Wrap the callback to handle MessageResponse objects"""
        async def wrapped_callback(data_dict):
            logger.info("Calling wrapped callback")
            try:
                messages = await callback(data_dict)
                logger.info(f"Raw messages from callback: {messages}")
                
                if not messages:
                    return []
                
                # Simply return the messages without sending them
                # The _handle_message method will handle sending
                processed_messages = []
                for msg in messages:
                    if hasattr(msg, 'message'):
                        processed_messages.append(msg.message)
                    elif isinstance(msg, str):
                        processed_messages.append(msg)
                    elif isinstance(msg, dict) and 'message' in msg:
                        processed_messages.append(msg['message'])
                    else:
                        processed_messages.append(str(msg))
                
                logger.info(f"Processed messages: {processed_messages}")
                return processed_messages
                
            except Exception as e:
                logger.error(f"Error in wrapped callback: {str(e)}")
                logger.error(traceback.format_exc())
                return ["Sorry, I encountered an error processing your request. Please try again."]
        
        return wrapped_callback

    async def send_message(self, chat_id: str, message: str, chat_type: str = "c") -> str:
        """Send a message to the chat - this is used by the orchestrator"""
        logger.info(f"Sending message to {chat_id}: {message}")
        await self.bot.send_message(chat_id=chat_id, text=message)
        return message  # Return message for compatibility with other views

    async def _start_command(self, message: types.Message):
        """Handle the /start command"""
        user_id = message.from_user.id
        username = message.from_user.username
        logger.info(f"Received /start command from user {username} (ID: {user_id})")
        
        # Set initial state
        self.user_states[user_id] = {
            "state": UserState.WAITING_FOR_DESCRIPTION,
            "business_description": None
        }
        
        # Clear history in Graph
        if self.view_callback:
            data_dict = {
                "type": "delete_history",
                "chat_id": str(user_id),
                "sender": str(user_id),
                "name": username
            }
            logger.info(f"Sending delete_history data: {data_dict}")
            try:
                await self.view_callback(data_dict)
            except Exception as e:
                logger.error(f"Error in view_callback for delete_history: {e}\n{traceback.format_exc()}")
        
        # Send welcome message asking for business description
        await message.answer(WELCOME_MESSAGE)

    async def _handle_message(self, message: types.Message):
        """Handle incoming messages"""
        user_id = message.from_user.id
        username = message.from_user.username
        logger.info(f"[View] Received message from user {username} (ID: {user_id}): {message.text[:50]}...")
        
        await message.bot.send_chat_action(message.chat.id, "typing")
        
        try:
            # Initialize user state if not exists
            if user_id not in self.user_states:
                logger.info(f"[View] Initializing state for user {user_id}")
                self.user_states[user_id] = {
                    "state": UserState.WAITING_FOR_DESCRIPTION,
                    "business_description": None
                }
            
            if message.content_type == 'text':
                user_state = self.user_states[user_id]
                
                if user_state["state"] == UserState.WAITING_FOR_DESCRIPTION:
                    # Store business description and update state
                    logger.info(f"[View] Storing business description for user {user_id}")
                    user_state["business_description"] = message.text
                    user_state["state"] = UserState.CHATTING
                    await message.answer(DESCRIPTION_ACCEPTED_MESSAGE)
                
                elif user_state["state"] == UserState.CHATTING:
                    # Prepare prompt with business context
                    prompt = (
                        f"Here is the user's business description: {user_state['business_description']}\n"
                        f"Here is the user's question: {message.text}\n"
                        "You must answer this question according to the description."
                    )
                    
                    # Send to orchestrator
                    data_dict = {
                        "type": "text",
                        "chat_id": str(user_id),
                        "user_id": str(user_id),
                        "sender": str(user_id),
                        "text": prompt,
                        "name": username
                    }
                    logger.info(f"[View] Sending message data to orchestrator: {data_dict}")
                    
                    if self.view_callback:
                        try:
                            await self.view_callback(data_dict)
                        except Exception as e:
                            logger.error(f"Error in view_callback: {e}\n{traceback.format_exc()}")
                            await message.answer(ERROR_MESSAGE)
                
            else:
                await message.answer("Sorry, I can only process text messages at the moment.")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}\n{traceback.format_exc()}")
            await message.answer(ERROR_MESSAGE)

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