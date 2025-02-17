from enum import Enum, auto
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class UserState(Enum):
    WAITING_FOR_DESCRIPTION = "waiting_for_description"
    CHATTING = "chatting"

class StateManager:
    def __init__(self):
        self.user_states: Dict[int, UserState] = {}
        self.business_descriptions: Dict[int, str] = {}
        self.message_history: Dict[int, List[dict]] = {}  # Store messages for each user
        logger.info("StateManager initialized")
    
    def get_state(self, user_id: int) -> UserState:
        state = self.user_states.get(user_id, UserState.WAITING_FOR_DESCRIPTION)
        logger.debug(f"Getting state for user {user_id}: {state}")
        return state
    
    def set_state(self, user_id: int, state: UserState):
        logger.info(f"Setting state for user {user_id} to {state}")
        self.user_states[user_id] = state
    
    def get_description(self, user_id: int) -> Optional[str]:
        description = self.business_descriptions.get(user_id)
        logger.debug(f"Getting business description for user {user_id}: {'Found' if description else 'Not found'}")
        return description
    
    def set_description(self, user_id: int, description: str):
        logger.info(f"Setting business description for user {user_id}. Length: {len(description)} chars")
        self.business_descriptions[user_id] = description
    
    def get_message_history(self, user_id: int) -> List[dict]:
        """Get the message history for a user"""
        if user_id not in self.message_history:
            self.message_history[user_id] = []
        return self.message_history[user_id]

    def add_message(self, user_id: int, role: str, content: str):
        """Add a message to user's history"""
        if user_id not in self.message_history:
            self.message_history[user_id] = []
        
        message = {"role": role, "content": content}
        self.message_history[user_id].append(message)
        logger.info(f"Added {role} message for user {user_id}. Message history length: {len(self.message_history[user_id])}")

    def clear_message_history(self, user_id: int):
        """Clear the message history for a user"""
        if user_id in self.message_history:
            self.message_history[user_id] = []
            logger.info(f"Cleared message history for user {user_id}")

    def reset_user(self, user_id: int):
        logger.info(f"Resetting all state for user {user_id}")
        if user_id in self.user_states:
            del self.user_states[user_id]
        if user_id in self.business_descriptions:
            del self.business_descriptions[user_id]
        if user_id in self.message_history:
            del self.message_history[user_id]