import logging
from typing import List, Dict, Any
from datetime import datetime
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)


def get_sheets_table(config):
    """Initialize and return Google Sheets table for issues."""
    try:
        # Get credentials from config
        credentials_path = config.sheets.path_to_json_file

        # Use the same scope as in __init__.py
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            credentials_path, scope
        )
        client = gspread.authorize(creds)

        # Get the issues table from the Provision-ISR AI sheet
        table = client.open(config.sheets.data_sheet_name).worksheet(config.sheets.issues_table)
        return table
    except Exception as e:
        logger.error(f"Failed to initialize Google Sheets table: {e}")
        return None


def format_chat_history(chat_history: List[Dict[str, Any]]) -> str:
    """Format chat history into a readable string."""
    formatted_messages = []
    for msg in chat_history:
        role = "User" if msg.get("type") == "user" else "AI"
        content = msg.get("message", "")
        formatted_messages.append(f"{role}: {content}")
    return "\n".join(formatted_messages)


def format_model_info(model_info: Dict[str, Any]) -> str:
    """Format model info into a readable string."""
    if not model_info:
        return "Default (no model selected)"
    
    lines = []
    for key, value in model_info.items():
        if isinstance(value, dict):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


async def handle_issue_report(
    chat_id: int, issue_details: str, chat_history: List[Dict[str, Any]], config, model_info: Dict[str, Any] = None
) -> None:
    """
    Handle issue reports by logging them and appending to Google Sheets.

    Args:
        chat_id: The ID of the chat where the issue was reported
        issue_details: The details of the reported issue
        chat_history: List of chat messages in the conversation, each with type and message fields
        config: Configuration object
        model_info: Dictionary containing model configuration used during the session
    """
    # Log the issue report
    logger.info(f"Received issue report from chat {chat_id}")
    logger.info("Issue details:")
    logger.info("-" * 50)
    logger.info(issue_details)
    logger.info("-" * 50)
    logger.info("Model info:")
    logger.info(model_info if model_info else "Default")
    logger.info("-" * 50)
    logger.info("Chat history:")
    for msg in chat_history:
        logger.info(f"[{msg.get('type', 'unknown')}]: {msg.get('message', '')}")
    logger.info("-" * 50)

    # Append to Google Sheets
    try:
        table = get_sheets_table(config)
        if not table:
            logger.error("Could not initialize Google Sheets table")
            return

        # Format chat history into a string
        chat_history_str = format_chat_history(chat_history)
        model_info_str = format_model_info(model_info)

        # Prepare the row data
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [
            current_time,  # Date
            model_info_str,  # Model Info
            chat_history_str,  # Thread (formatted chat history)
            issue_details,  # Description
        ]

        # Append the row to the sheet
        table.append_row(row_data)
        logger.info("Successfully appended issue report to Google Sheets")
    except Exception as e:
        logger.error(f"Failed to append issue report to Google Sheets: {e}")
