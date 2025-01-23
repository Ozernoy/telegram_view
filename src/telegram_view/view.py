import logging
from typing import Callable, Optional
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import asyncio
import os
import traceback

logger = logging.getLogger(__name__)

class View:
    def __init__(self, token: str, view_callback: Optional[Callable] = None):
        logger.info("Initializing Telegram View")
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self._original_callback = view_callback
        self.view_callback = self._wrap_callback(view_callback) if view_callback else None
        # Dictionary to track user states
        self.user_states = {}  # {user_id: {"has_description": bool, "description": str}}
        
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
        
        # Reset user state
        self.user_states[user_id] = {"has_description": False, "description": None}
        
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
        await message.answer("Welcome! Please provide a brief description of your business to help me assist you better.")

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
                self.user_states[user_id] = {"has_description": False, "description": None}
            
            if message.content_type == 'text':
                if not self.user_states[user_id]["has_description"]:
                    # Store business description
                    logger.info(f"[View] Storing business description for user {user_id}")
                    self.user_states[user_id]["description"] = message.text
                    self.user_states[user_id]["has_description"] = True
                    await message.answer("Thank you! I understand your business context. How can I help you today?")
                else:
                    # Only send to orchestrator if we have business description
                    data_dict = {
                        "type": "extendedText",
                        "chat_id": str(user_id),
                        "sender": str(user_id),
                        "data": message.text,
                        "description": self.user_states[user_id]["description"],
                        "name": username
                    }
                    logger.info(f"[View] Sending message data to orchestrator: {data_dict}")
                    
                    if self.view_callback:
                        try:
                            logger.info("[View] Calling view_callback")
                            responses = await self.view_callback(data_dict)
                            logger.info(f"[View] Received responses from orchestrator: {responses}")
                            
                            if responses:
                                logger.info(f"[View] Processing {len(responses) if isinstance(responses, list) else 1} responses")
                                if isinstance(responses, list):
                                    for i, response in enumerate(responses):
                                        try:
                                            logger.info(f"[View] Processing response {i}: {response}")
                                            # If it's a MessageResponse object
                                            if hasattr(response, 'message'):
                                                msg = response.message
                                                logger.info(f"[View] Sending MessageResponse: {msg}")
                                                await message.answer(msg)
                                            # If it's a string
                                            elif isinstance(response, str):
                                                logger.info(f"[View] Sending string response: {response}")
                                                await message.answer(response)
                                            # If it's a dict
                                            elif isinstance(response, dict):
                                                msg = response.get('message', str(response))
                                                logger.info(f"[View] Sending dict response: {msg}")
                                                await message.answer(msg)
                                            else:
                                                msg = str(response)
                                                logger.info(f"[View] Sending generic response: {msg}")
                                                await message.answer(msg)
                                        except Exception as e:
                                            logger.error(f"[View] Error sending response {i}: {e}")
                                else:
                                    logger.info(f"[View] Processing single non-list response: {responses}")
                                    await message.answer(str(responses))
                            else:
                                logger.warning("[View] No responses received from orchestrator")
                                
                        except Exception as e:
                            logger.error(f"[View] Error in view_callback: {e}")
                            logger.error(traceback.format_exc())
                            await message.answer("Sorry, I encountered an error processing your request. Please try again.")
                    else:
                        logger.error("[View] No view_callback configured")
                        await message.answer("Sorry, I'm not properly configured to handle messages yet.")
            else:
                logger.warning(f"[View] Unsupported content type: {message.content_type}")
                await message.answer("Sorry, I can only process text messages at the moment.")
                
        except Exception as e:
            logger.error(f"[View] Error handling message: {e}")
            logger.error(traceback.format_exc())
            await message.answer("Sorry, something went wrong. Please try again.")

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
        bot = View(token)
        asyncio.run(bot.run())
    else:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        print("Please set TELEGRAM_BOT_TOKEN in your environment variables")