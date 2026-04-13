"""Tests for AutopostController scheduling logic (no DB/API connections)."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def make_controller():
    """Build AutopostController with all dependencies mocked."""
    with patch("main_controller.DatabaseManager"), \
         patch("main_controller.FeedManager"), \
         patch("main_controller.AIProcessor"), \
         patch("main_controller.TelegramManager"), \
         patch("main_controller.config"):
        from main_controller import AutopostController
        config = MagicMock()
        config.MIN_RATING_THRESHOLD = 60
        config.MIN_LURKABLE_THRESHOLD = 70
        config.MAX_ARTICLES_PER_RUN = 10
        controller = AutopostController(config)
    return controller


class TestSchedulerDelays:
    """Verify the time-based delay logic."""

    def _get_delay(self, hour: int) -> tuple[int, int]:
        """Return (min_delay_seconds, max_delay_seconds) for the given hour."""
        if 8 <= hour < 24:
            return 100 * 60, 140 * 60   # 100–140 minutes
        else:
            return 4 * 60 * 60, 4 * 60 * 60 + 30 * 60  # 4h–4h30m

    @pytest.mark.parametrize("hour", range(8, 24))
    def test_daytime_delay_range(self, hour):
        min_d, max_d = self._get_delay(hour)
        assert min_d == 6000
        assert max_d == 8400

    @pytest.mark.parametrize("hour", range(0, 8))
    def test_nighttime_delay_range(self, hour):
        min_d, max_d = self._get_delay(hour)
        assert min_d == 14400
        assert max_d == 16200

    def test_daytime_delay_shorter_than_nighttime(self):
        day_max = self._get_delay(12)[1]
        night_min = self._get_delay(3)[0]
        assert day_max < night_min


class TestProcessingCycle:
    @pytest.mark.asyncio
    async def test_cycle_not_reentrant(self):
        """A second concurrent cycle call should be skipped."""
        controller = make_controller()
        controller.is_running = True

        # Patch the methods that should not be called
        controller.feed_manager.fetch_recent_articles = MagicMock(return_value=[])
        await controller.run_processing_cycle()

        controller.feed_manager.fetch_recent_articles.assert_not_called()

    @pytest.mark.asyncio
    async def test_cycle_sets_running_flag(self):
        controller = make_controller()
        controller.feed_manager.fetch_recent_articles = MagicMock(return_value=[])
        controller._process_unrated_articles = AsyncMock()
        controller._post_best_article = AsyncMock()

        assert controller.is_running is False
        await controller.run_processing_cycle()
        assert controller.is_running is False  # should be reset after completion

    @pytest.mark.asyncio
    async def test_cycle_resets_flag_on_exception(self):
        """is_running must be reset even when the cycle raises."""
        controller = make_controller()
        controller.feed_manager.fetch_recent_articles = MagicMock(
            side_effect=RuntimeError("feed down")
        )
        await controller.run_processing_cycle()
        assert controller.is_running is False


class TestPostBestArticle:
    @pytest.mark.asyncio
    async def test_skips_when_no_article(self):
        controller = make_controller()
        controller.db.get_best_unposted_article.return_value = None

        # Should return without error
        await controller._post_best_article()
        controller.telegram_manager.send_article.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_below_threshold(self):
        controller = make_controller()

        article = MagicMock()
        article.rating = 50      # below MIN_RATING_THRESHOLD=60
        article.lurkable = 80
        controller.db.get_best_unposted_article.return_value = article

        await controller._post_best_article()
        controller.telegram_manager.send_article.assert_not_called()

    @pytest.mark.asyncio
    async def test_posts_when_above_threshold(self):
        controller = make_controller()

        article = MagicMock()
        article.rating = 80
        article.lurkable = 75
        article.id = "https://deadline.com/?p=42"
        article.link = "https://deadline.com/article"
        article.summary = "Fallback summary."
        controller.db.get_best_unposted_article.return_value = article
        controller.feed_manager.get_full_article_content = MagicMock(return_value="Full content.")
        controller.db.save_article_content = MagicMock(return_value=True)
        controller.ai_processor.translate_to_lurk = MagicMock(return_value="Translated text")
        controller.telegram_manager.send_article = AsyncMock(return_value=True)
        controller.db.mark_article_used = MagicMock()

        await controller._post_best_article()

        controller.telegram_manager.send_article.assert_called_once()
        controller.db.mark_article_used.assert_called_once_with(article.id, "Translated text")
