import logging
from typing import Callable, Optional, Dict, List, Any
import asyncio
import os
import traceback
import time
from common_utils.view.view_abc import BaseView
from common_utils.schemas import (
    AgentRequest,
    AgentRequestType,
    AgentResponse,
    RequestStatus,
    Message,
)
from common_utils.logging.bug_catcher import report_error_if_enabled
from .interfaces.telegram_tester_bot import TesterBotInterface
from .interfaces.showcase_interface import ShowcaseInterface

logger = logging.getLogger(__name__)


class TelegramView(BaseView):
    def __init__(self, view_callback, config):
        super().__init__()
        logger.info("Initializing Telegram View")
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")
        
        self.view_callback = view_callback
        self.config = config
        logger.info(f"Config: {self.config}")
        self.view_config = config.view
        
        # Initialize the Telegram bot interface based on config
        interface_type = getattr(self.view_config, 'interface', 'tester')
        
        if interface_type == 'tester':
            self.bot_interface = TesterBotInterface(self.token, self.config)
        elif interface_type == 'showcase':
            self.bot_interface = ShowcaseInterface(self.token, self.config)
        else:
            raise ValueError(f"Unsupported interface type: {interface_type}. Supported types: 'tester', 'showcase'")
        
        # Setup message handling
        self.bot_interface.setup_handlers(self._handle_bot_message, self.view_config)

    @classmethod
    def from_config(cls, config, callback: Callable) -> "TelegramView":
        """
        Creates TelegramView instance from config.

        Args:
            view_config: Either a TelegramViewConfig from the new config system or a dict for backward compatibility
            callback: The callback function to handle view events

        Returns:
            TelegramView: A configured view instance
        """
        return cls(view_callback=callback, config=config)

    # TODO: Change message passed to callback from AgentRequest to Message 
    async def _handle_bot_message(self, message_data: Dict[str, Any]) -> Optional[str]:
        """Handle messages from the Telegram bot interface
        
        This method bridges between the Telegram bot interface and the orchestrator
        
        Args:
            message_data: Dictionary containing message information from the bot
            
        Returns:
            Optional[str]: Response message to send back, or None
        """
        try:
            message_type = message_data.get("type")
            
            if message_type == "start_command":
                # Handle start command - delete user history
                request = Message(
                    webhook_type="incoming_message",
                    platform="telegram",
                    timestamp=message_data.get("timestamp", int(time.time())),
                    message_type="delete_history",
                    chatbot_id=self.token,
                    sender_id=str(message_data.get("user_id")),
                    sender_name=message_data.get("full_name"),
                    chat_type="c",
                    chat_id=str(message_data.get("chat_id")),
                )


                # request = AgentRequest(
                #     chat_id=message_data["user_id"],
                #     type=AgentRequestType.DELETE_ENTRIES_BY_CHAT_ID,
                #     user_details={
                #         "username": message_data["username"],
                #         "name": f"{message_data['first_name']} {message_data.get('last_name', '')}".strip(),
                #     },
                #     bypass=True,  # Set bypass since this is a control message
                # )
                
                logger.info(f"Sending {message_data['user_id']} delete_history request for start command")
                if self.view_callback:
                    await self.view_callback(request)
                return None  # Welcome message is handled by the bot interface
                
            elif message_type == "delete_all_history":
                # Handle delete all history command
                request = Message(
                    webhook_type="incoming_message",
                    platform="telegram",
                    timestamp=message_data.get("timestamp", int(time.time())),
                    message_type="delete_history",
                    chatbot_id=self.token,
                    sender_id=str(message_data.get("user_id")),
                    sender_name=message_data.get("full_name"),
                    chat_type="c",
                    chat_id=str(message_data.get("chat_id")),
                )
                # request = AgentRequest(
                #     chat_id=0,  # Using 0 as a placeholder for all chats
                #     type=AgentRequestType.DELETE_HISTORY,
                #     message=None,
                # )
                
                logger.info("Sending delete_all_history request")
                if self.view_callback:
                    await self.view_callback(request)
                return None
                
            elif message_type == "image_message":
                # Handle image messages
                image_data = message_data.get("text", {})
                request = Message(
                    webhook_type="incoming_message",
                    platform="telegram",
                    timestamp=message_data.get("timestamp", int(time.time())),
                    message_type="image",
                    data=image_data.get("image", ""),  # Base64 image data goes in data field
                    description=image_data.get("caption", ""),  # Caption text goes in description field
                    chatbot_id=self.token,
                    sender_id=str(message_data.get("user_id")),
                    sender_name=message_data.get("full_name"),
                    chat_type="c",
                    chat_id=str(message_data.get("chat_id")),
                )
                
                logger.debug(f"Sending image request to orchestrator for user: {request.sender_id}")
                
                if self.view_callback:
                    await self.view_callback(request)
                return None

            elif message_type == "text_message":
                # Handle normal text messages
                request = Message(
                    webhook_type="incoming_message",
                    platform="telegram",
                    timestamp=message_data.get("timestamp", int(time.time())),
                    message_type="text",
                    data=message_data.get("text"),
                    chatbot_id=self.token,
                    sender_id=str(message_data.get("user_id")),
                    sender_name=message_data.get("full_name"),
                    chat_type="c",
                    chat_id=str(message_data.get("chat_id")),
                )

                # request = AgentRequest(
                #     chat_id=message_data["user_id"],
                #     type=AgentRequestType.TEXT,
                #     message=message_data["text"],
                #     user_details={
                #         "username": message_data["username"],
                #         "name": message_data["full_name"],
                #         "language_code": message_data["language_code"],
                #     },
                #     bypass=False,
                # )
                
                logger.debug(f"Sending message request to orchestrator: {request}")
                
                if self.view_callback:
                    response = await self.view_callback(request)
                    # if response and response.message: # Returning a message here sends a message to the user
                        # return response.message
                        
            return None
            
        except Exception as e:
            # Report error using the centralized bug catcher function
            report_error_if_enabled(
                self.config, 
                e, 
                "Error in _handle_bot_message (Telegram View)", 
                {"message_data": str(message_data)}
            )
            
            logger.error(f"Error in _handle_bot_message: {e}\n{traceback.format_exc()}")
            return None

    async def send_message(self, chat_id: str, message: str) -> str:
        """Send a message to the chat - this is used by the orchestrator

        Args:
            chat_id: The chat ID to send the message to
            message: The message text to send

        Returns:
            str: The message that was sent, or empty string if no message was available
        """
        try:
            if message:
                logger.debug(f"Sending message to {chat_id}: {message[:50]}... (length: {len(message)})")
                await self.bot_interface.send_message(chat_id, message)
            return message
        except Exception as e:
            # Report error using the centralized bug catcher function
            report_error_if_enabled(
                self.config, 
                e, 
                "Error in send_message (Telegram View)", 
                {"chat_id": chat_id, "message_length": len(message) if message else 0}
            )
            
            logger.error(f"Error sending message: {e}\n{traceback.format_exc()}")
            return ""

    async def run(self):
        """Run the telegram bot"""
        logger.debug("Starting telegram bot")
        try:
            await self.bot_interface.run()
        except Exception as e:
            # Report error using the centralized bug catcher function
            report_error_if_enabled(
                self.config, 
                e, 
                "Critical error in telegram bot run", 
                {"bot_interface_type": type(self.bot_interface).__name__}
            )
            
            logger.error(f"Error running telegram bot: {e}\n{traceback.format_exc()}")
            raise


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
        
        # Create a mock config for testing
        class MockConfig:
            title = "Welcome to Telegram Bot!"
        
        bot = TelegramView(None, MockConfig())
        asyncio.run(bot.run())
    else:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        print("Please set TELEGRAM_BOT_TOKEN in your environment variables")
