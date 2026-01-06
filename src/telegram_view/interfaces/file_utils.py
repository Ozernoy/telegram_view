import base64
import io
import logging
from aiogram import Bot, types
from typing import Optional, Tuple

from agent_db.utils import get_s3_uploader

logger = logging.getLogger(__name__)

# Supported document MIME types
SUPPORTED_DOCUMENT_MIMES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


async def get_file_as_url(bot: Bot, message: types.Message) -> Optional[Tuple[str, str]]:
    """
    Gets the download URL for a document from a message.
    
    Args:
        bot: The aiogram Bot instance.
        message: The message object containing the document.

    Returns:
        Tuple of (download_url, mime_type), or None if no document or error.
        Note: The URL is only guaranteed to be valid for at least 1 hour.
    """
    if not message.document:
        return None

    try:
        document = message.document
        mime_type = document.mime_type or "application/octet-stream"
        
        file_info = await bot.get_file(document.file_id)
        
        if not file_info.file_path:
            logger.error("No file_path received from Telegram for document")
            return None

        download_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        logger.debug(f"Document URL: {download_url}, MIME: {mime_type}")
        return (download_url, mime_type)

    except Exception as e:
        logger.error(f"Failed to get document URL: {e}")
        return None


async def get_file_as_base64(bot: Bot, message: types.Message) -> Optional[Tuple[str, str]]:
    """
    Downloads a document from a message and encodes it to base64.

    Args:
        bot: The aiogram Bot instance.
        message: The message object containing the document.

    Returns:
        Tuple of (base64_data, mime_type), or None if no document or error.
    """
    if not message.document:
        return None

    try:
        document = message.document
        mime_type = document.mime_type or "application/octet-stream"
        
        file_info = await bot.get_file(document.file_id)

        file_data_io = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=file_data_io)
        file_data = file_data_io.getvalue()

        base64_data = base64.b64encode(file_data).decode("utf-8")
        logger.debug(f"Document encoded to base64, MIME: {mime_type}, size: {len(file_data)} bytes")
        return (base64_data, mime_type)

    except Exception as e:
        logger.error(f"Failed to process document and convert to base64: {e}")
        return None


async def get_audio_as_url(bot: Bot, message: types.Message) -> Optional[Tuple[str, str]]:
    """
    Gets the download URL for audio/voice from a message.
    
    Args:
        bot: The aiogram Bot instance.
        message: The message object containing voice or audio.

    Returns:
        Tuple of (download_url, mime_type), or None if no audio or error.
        Note: The URL is only guaranteed to be valid for at least 1 hour.
    """
    audio_obj = message.voice or message.audio
    if not audio_obj:
        return None

    try:
        mime_type = getattr(audio_obj, 'mime_type', None) or "audio/ogg"
        
        file_info = await bot.get_file(audio_obj.file_id)
        
        if not file_info.file_path:
            logger.error("No file_path received from Telegram for audio")
            return None

        download_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        logger.debug(f"Audio URL: {download_url}, MIME: {mime_type}")
        return (download_url, mime_type)

    except Exception as e:
        logger.error(f"Failed to get audio URL: {e}")
        return None


async def get_audio_as_base64(bot: Bot, message: types.Message) -> Optional[Tuple[str, str]]:
    """
    Downloads audio/voice from a message and encodes it to base64.

    Args:
        bot: The aiogram Bot instance.
        message: The message object containing voice or audio.

    Returns:
        Tuple of (base64_data, mime_type), or None if no audio or error.
    """
    audio_obj = message.voice or message.audio
    if not audio_obj:
        return None

    try:
        mime_type = getattr(audio_obj, 'mime_type', None) or "audio/ogg"
        
        file_info = await bot.get_file(audio_obj.file_id)

        file_data_io = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=file_data_io)
        file_data = file_data_io.getvalue()

        base64_data = base64.b64encode(file_data).decode("utf-8")
        logger.debug(f"Audio encoded to base64, MIME: {mime_type}, size: {len(file_data)} bytes")
        return (base64_data, mime_type)

    except Exception as e:
        logger.error(f"Failed to process audio and convert to base64: {e}")
        return None


def is_supported_document(message: types.Message) -> bool:
    """Check if the document type is supported."""
    if not message.document:
        return False
    mime_type = message.document.mime_type or ""
    return mime_type in SUPPORTED_DOCUMENT_MIMES


async def upload_document_to_s3(bot: Bot, message: types.Message, chat_id: str) -> Optional[Tuple[str, str]]:
    """
    Downloads a document from Telegram and uploads it to S3.
    
    Args:
        bot: The aiogram Bot instance.
        message: The message object containing the document.
        chat_id: Chat ID for organizing files in S3.
        
    Returns:
        Tuple of (s3_url, mime_type), or None if upload failed.
    """
    if not message.document:
        return None

    try:
        document = message.document
        mime_type = document.mime_type or "application/octet-stream"
        filename = document.file_name or "document"

        # Download file from Telegram
        file_info = await bot.get_file(document.file_id)
        file_data_io = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=file_data_io)
        file_bytes = file_data_io.getvalue()

        logger.debug(f"Downloaded document from Telegram: {filename}, size: {len(file_bytes)} bytes")

        # Upload to S3
        uploader = get_s3_uploader()
        if not uploader.is_enabled:
            logger.warning("S3 not enabled, falling back to base64")
            return None

        s3_url = uploader.upload_bytes(file_bytes, filename, mime_type, chat_id)
        if s3_url:
            logger.info(f"Uploaded document to S3: {s3_url}")
            return (s3_url, mime_type)
        return None

    except Exception as e:
        logger.error(f"Failed to upload document to S3: {e}")
        return None


async def upload_audio_to_s3(bot: Bot, message: types.Message, chat_id: str) -> Optional[Tuple[str, str]]:
    """
    Downloads audio/voice from Telegram and uploads it to S3.
    
    Args:
        bot: The aiogram Bot instance.
        message: The message object containing voice or audio.
        chat_id: Chat ID for organizing files in S3.
        
    Returns:
        Tuple of (s3_url, mime_type), or None if upload failed.
    """
    audio_obj = message.voice or message.audio
    if not audio_obj:
        return None

    try:
        mime_type = getattr(audio_obj, 'mime_type', None) or "audio/ogg"
        filename = getattr(audio_obj, 'file_name', None) or "audio.ogg"

        # Download file from Telegram
        file_info = await bot.get_file(audio_obj.file_id)
        file_data_io = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=file_data_io)
        file_bytes = file_data_io.getvalue()

        logger.debug(f"Downloaded audio from Telegram: {filename}, size: {len(file_bytes)} bytes")

        # Upload to S3
        uploader = get_s3_uploader()
        if not uploader.is_enabled:
            logger.warning("S3 not enabled, falling back to base64")
            return None

        s3_url = uploader.upload_bytes(file_bytes, filename, mime_type, chat_id)
        if s3_url:
            logger.info(f"Uploaded audio to S3: {s3_url}")
            return (s3_url, mime_type)
        return None

    except Exception as e:
        logger.error(f"Failed to upload audio to S3: {e}")
        return None

