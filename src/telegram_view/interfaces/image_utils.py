import base64
import io
import logging
from aiogram import Bot, types
from typing import Optional

logger = logging.getLogger(__name__)


async def get_image_as_base64(bot: Bot, message: types.Message) -> Optional[str]:
    """
    Downloads the highest resolution photo from a message, encodes it to base64,
    and returns it as a string.

    Args:
        bot: The aiogram Bot instance.
        message: The message object containing the photo.

    Returns:
        A base64 encoded string of the image, or None if no photo is found or an error occurs.
    """
    if not message.photo:
        return None

    try:
        # Get the highest resolution photo
        highest_res_photo = message.photo[-1]
        file_info = await bot.get_file(highest_res_photo.file_id)

        # Download the file into an in-memory buffer
        image_data_io = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=image_data_io)
        image_data = image_data_io.getvalue()

        # Encode the image data to base64
        base64_image = base64.b64encode(image_data).decode("utf-8")
        return base64_image

    except Exception as e:
        logger.error(f"Failed to process image and convert to base64: {e}")
        return None


async def get_image_as_url(bot: Bot, message: types.Message) -> Optional[str]:
    """
    Gets the download URL for the highest resolution photo from a message.
    
    Args:
        bot: The aiogram Bot instance.
        message: The message object containing the photo.

    Returns:
        A download URL string for the image, or None if no photo is found or an error occurs.
        Note: The URL is only guaranteed to be valid for at least 1 hour.
    """
    if not message.photo:
        return None

    try:
        # Get the highest resolution photo
        highest_res_photo = message.photo[-1]
        file_info = await bot.get_file(highest_res_photo.file_id)
        
        if not file_info.file_path:
            logger.error("No file_path received from Telegram")
            return None

        # Construct the download URL
        # Format: https://api.telegram.org/file/bot<token>/<file_path>
        download_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"
        logger.debug(f"Download URL: {download_url}")
        return download_url

    except Exception as e:
        logger.error(f"Failed to get image URL: {e}")
        return None 