# main_controller.py
import asyncio
import schedule
import time
from datetime import datetime, timedelta
import logging
from typing import List, Optional
from config import config
from database_manager import DatabaseManager
from models import Article, RatingResult, ArticleStatus
from feed_manager import FeedManager
from ai_processor import AIProcessor
from telegram_manager import TelegramManager
import os
import random

os.environ['PYTHONUTF8'] = '1'



class AutopostController:
    def __init__(self, config: config):
        self.config = config
        self.logger = self._setup_logger()

        # Initialize components
        self.db = DatabaseManager(config, self.logger)
        self.feed_manager = FeedManager(config, self.db, self.logger)
        self.ai_processor = AIProcessor(config, self.logger)
        self.telegram_manager = TelegramManager(config, self.logger)

        # State tracking
        self.is_running = False
        self.last_run_time = None

    def _setup_logger(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger('autopost')
        logger.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # File handler
        file_handler = logging.FileHandler('autopost.log')
        file_handler.setLevel(logging.DEBUG)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger

    async def run_processing_cycle(self):
        """Main processing cycle"""
        if self.is_running:
            self.logger.warning("Processing cycle already running, skipping")
            return

        self.is_running = True
        self.last_run_time = datetime.now()

        try:
            self.logger.info("Starting processing cycle")

            # Step 1: Fetch new articles
            articles = self.feed_manager.fetch_recent_articles(hours_back=12)

            # Step 2: Save articles to database
            for article in articles:
                if self.db.save_article(article):
                    self.logger.info(f"Saved article: {article.id}")

            # Step 3: Process unrated articles
            await self._process_unrated_articles()

            # Step 4: Post best article
            await self._post_best_article()

            self.logger.info("Processing cycle completed successfully")

        except Exception as e:
            self.logger.error(f"Error in processing cycle: {str(e)}")
        finally:
            self.is_running = False

    async def _process_unrated_articles(self):
        """Process articles that need rating"""
        unrated_articles = self.db.get_unprocessed_articles(
            limit=self.config.MAX_ARTICLES_PER_RUN          #непонятно зачем
        )

        for article in unrated_articles:
            try:
                self.logger.info(f"Rating article: {article.id}")

                # Get AI rating
                rating_result = self.ai_processor.rate_article(article)

                if rating_result:
                    # Update database
                    success = self.db.update_article_rating(
                        article.id,
                        rating_result.interest_score,
                        rating_result.lurkable_score,
                        rating_result.rhymable_score,           #AJRM   поправить на reasoning
                        rating_result.category
                    )

                    if success:
                        self.logger.info(
                            f"Rated article {article.id}: "
                            f"interest={rating_result.interest_score}, "
                            f"lurkable={rating_result.lurkable_score}, "
                            f"reasoning = {rating_result.rhymable_score}, "     #AJRM   поправить на reasoning
                            f"category = {rating_result.category}"
                        )

                    # Rate limiting
                    await asyncio.sleep(0.3)

            except Exception as e:
                self.logger.error(f"Error rating article {article.id}: {str(e)}")

    async def _post_best_article(self):
        """Find and post the best available article"""
        try:
            # Get best article
            best_article = self.db.get_best_unposted_article()

            if not best_article:
                self.logger.info("No articles ready for posting")
                return

            # Check if article meets minimum thresholds
            if (best_article.rating < self.config.MIN_RATING_THRESHOLD or
                    best_article.lurkable < self.config.MIN_LURKABLE_THRESHOLD):
                self.logger.info(
                    f"Best article {best_article.id} doesn't meet thresholds: "
                    f"rating={best_article.rating}, lurkable={best_article.lurkable}"
                )
                return

            self.logger.info(f"Processing best article: {best_article.id}")

            # Get full content
            full_content = self.feed_manager.get_full_article_content(best_article.link)

            if not full_content:
                self.logger.warning(f"Could not retrieve full content for {best_article.id}")
                # Use summary as fallback
                full_content = best_article.summary

            # Save full content to database
            content_saved = self.db.save_article_content(best_article.id, full_content)
            if not content_saved:
                self.logger.error(f"Failed to save content for article {best_article.id}")
                # Continue with processing even if save failed
            # Translate to lurk-style
            lurk_translation = self.ai_processor.translate_to_lurk(
                best_article, full_content
            )

            if not lurk_translation:
                self.logger.error(f"Failed to translate article {best_article.id}")
                return

            # Send to Telegram
            success = await self.telegram_manager.send_article(
                best_article, lurk_translation
            )


            if success:
                # Mark as used
                self.db.mark_article_used(best_article.id, lurk_translation)
                self.logger.info(f"Successfully posted article {best_article.id}")
            else:
                self.logger.error(f"Failed to post article {best_article.id}")

        except Exception as e:
            self.logger.error(f"Error posting best article: {str(e)}")

    async def start_scheduler(self):
        """Start the hourly scheduler"""
        self.logger.info("Starting autopost scheduler")

        # Run immediately on startup
        await self.run_processing_cycle()

        # Schedule runs with dynamic delays
        while True:
            current_time = datetime.now()
            current_hour = current_time.hour

            # Determine delay based on current time
            if 8 <= current_hour < 24:  # 8am to 12am
                # Random delay between 50min and 1h20min (3000-4800 seconds)
                delay_seconds = random.randint(100 * 60, 140 * 60)
                delay_description = f"{delay_seconds // 60} minutes"
            elif 0 <= current_hour < 8:  # 12am to 8am
                # Random delay between 4h and 4h30min (14400-16200 seconds)
                delay_seconds = random.randint(4 * 60 * 60, 4 * 60 * 60 + 30 * 60)
                delay_description = f"{delay_seconds // 3600}h {(delay_seconds % 3600) // 60}min"
            else:
                # Should not occur, but safe fallback
                delay_seconds = 2 * 60 * 60
                delay_description = "2 hours"

            next_run = current_time + timedelta(seconds=delay_seconds)
            self.logger.info(f"Next run scheduled at {next_run} (delay: {delay_description})")

            await asyncio.sleep(delay_seconds)
            await self.run_processing_cycle()


        '''
        # Schedule hourly runs
        schedule.every().hour.do(
            lambda: asyncio.create_task(self.run_processing_cycle())
        )

        # Run immediately on startup
        asyncio.create_task(self.run_processing_cycle())


        # Keep scheduler running
        while True:

            schedule.run_pending()
            time.sleep(60)  # Check every minute
        '''


# Application entry point
async def main():

    controller = AutopostController(config)

    # Start the scheduler
    await controller.start_scheduler()


if __name__ == "__main__":
    asyncio.run(main())