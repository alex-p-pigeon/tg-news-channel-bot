# telegram_manager.py
#import telegram
#from telegram.error import TelegramError
import requests

from models import Article
from config import config
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile  # Add this import


#from telegram.error import TelegramError, BadRequest, TimedOut, NetworkError
from image_processor import ImageProcessor


class TelegramManager:
    def __init__(self, config: config, logger):
        self.config = config
        self.logger = logger
        self.bot = Bot(token=config.BOT_TOKEN.get_secret_value())
        self.image_processor = ImageProcessor(logger)

    async def send_article(self, article: Article, lurk_text: str) -> bool:
        """Send article to Telegram channel"""
        try:
            # Prepare message
            message = self._format_message(lurk_text, article)

            # Process and send with image if available
            if article.media_content and self.image_processor.validate_image_url(article.media_content):
                success = await self._send_with_processed_image(message, article)
            else:
                success = await self._send_text_only(message)

            if success:
                self.logger.info(f"Successfully sent article {article.id} to Telegram")

            return success

        except Exception as e:
            self.logger.error(f"Error sending article {article.id} to Telegram: {str(e)}")
            return False

    def _format_message(self, lurk_text: str, article: Article) -> str:
        """Format message for Telegram"""
        # Add source link at the end
        message = f"{lurk_text}\n\n"         #📰 [Источник]({article.link})"

        # Ensure message is not too long (Telegram limit is 4096 characters)
        if len(message) > 1020:
            message = message[:1010] + "..."      # 📰 [Источник]({article.link})"

        return message

    async def _send_with_media(self, message: str, media_url: str) -> bool:
        """Send message with media attachment"""
        try:
            # Download media
            response = requests.get(media_url, timeout=10)
            response.raise_for_status()

            # Determine media type
            content_type = response.headers.get('content-type', '').lower()
            self.logger.info(f"--------------->content_type - {content_type}")  #
            #self.logger.info(f"--------------->message - {message}")  #

            if 'image' in content_type:
                await self.bot.send_photo(
                    chat_id=self.config.TG_CHANNEL_ID.get_secret_value(),
                    photo=media_url,
                    caption=message,
                    parse_mode='HTML'
                )
            else:
                # Fallback to text-only
                return await self._send_text_only(message)

            return True

        except Exception as e:
            self.logger.error(f"Error sending media: {str(e)}")
            # Fallback to text-only
            return await self._send_text_only(message)

    async def _send_with_processed_image(self, message: str, article) -> bool:
        """Send message with processed image"""
        try:
            self.logger.info(f"Processing image for article {article.id}: {article.media_content}")

            # Process image
            processed_image = self.image_processor.process_image_from_url(article.media_content)

            if not processed_image:
                self.logger.warning("Failed to process image, sending text only")
                return await self._send_text_only(message)

            # Create BufferedInputFile for aiogram
            image_file = BufferedInputFile(
                file=processed_image,
                filename="image_1.jpg"  #{article.id}
            )

            # Send photo with caption
            await self.bot.send_photo(
                chat_id=self.config.TG_CHANNEL_ID.get_secret_value(),
                photo=image_file,
                caption=message,
                parse_mode='HTML'
            )



            self.logger.info(f"Successfully sent processed image for article {article.id}")
            return True

        except TelegramAPIError as e:
            self.logger.error(f"Telegram error sending image: {str(e)}")
            # Fallback to text-only
            return await self._send_text_only(message)
        except Exception as e:
            self.logger.error(f"Error sending processed image: {str(e)}")
            # Fallback to text-only
            return await self._send_text_only(message)

    async def _send_text_only(self, message: str) -> bool:
        """Send text-only message"""
        try:
            await self.bot.send_message(
                chat_id=self.config.TG_CHANNEL_ID.get_secret_value(),
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            return True

        except TelegramAPIError as e:       #TelegramError
            self.logger.error(f"Telegram error: {str(e)}")
            return False
