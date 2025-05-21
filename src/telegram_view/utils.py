import logging
from typing import List, Dict, Any
from datetime import datetime
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)


def get_sheets_table():
    """Initialize and return Google Sheets table for issues."""
    try:
        # Get credentials from config
        credentials_path = os.path.join(
            "configs",
            "awesome-tempo-437916-e6-27d0ad7fb868.json",
        )

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
        table = client.open("Provision-ISR AI").worksheet("Issues")
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


async def handle_issue_report(
    chat_id: int, issue_details: str, chat_history: List[Dict[str, Any]]
) -> None:
    """
    Handle issue reports by logging them and appending to Google Sheets.

    Args:
        chat_id: The ID of the chat where the issue was reported
        issue_details: The details of the reported issue
        chat_history: List of chat messages in the conversation, each with type and message fields
    """
    # Log the issue report
    logger.info(f"Received issue report from chat {chat_id}")
    logger.info("Issue details:")
    logger.info("-" * 50)
    logger.info(issue_details)
    logger.info("-" * 50)
    logger.info("Chat history:")
    for msg in chat_history:
        logger.info(f"[{msg.get('type', 'unknown')}]: {msg.get('message', '')}")
    logger.info("-" * 50)

    # Append to Google Sheets
    try:
        table = get_sheets_table()
        if not table:
            logger.error("Could not initialize Google Sheets table")
            return

        # Format chat history into a string
        chat_history_str = format_chat_history(chat_history)

        # Prepare the row data
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [
            current_time,  # Date
            chat_history_str,  # Thread (now contains the formatted chat history)
            issue_details,  # Description
        ]

        # Append the row to the sheet
        table.append_row(row_data)
        logger.info("Successfully appended issue report to Google Sheets")
    except Exception as e:
        logger.error(f"Failed to append issue report to Google Sheets: {e}")
