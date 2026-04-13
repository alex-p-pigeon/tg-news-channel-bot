"""Tests for FeedManager — article parsing logic (no network calls)."""
from datetime import datetime
from unittest.mock import MagicMock, patch
from models import Article, ArticleStatus
from feed_manager import FeedManager


def make_feed_manager() -> FeedManager:
    """Return a FeedManager with mocked config, db and logger."""
    config = MagicMock()
    config.RSS_URL = "https://deadline.com/feed/"
    db = MagicMock()
    logger = MagicMock()
    return FeedManager(config, db, logger)


def make_rss_entry(
    entry_id: str = "https://deadline.com/?p=999",
    title: str = "Test Movie News",
    link: str = "https://deadline.com/article",
    summary: str = "Short description of the news.",
    published_parsed: tuple = (2026, 4, 13, 10, 30, 0, 0, 0, 0),
    tags=None,
    media_content=None,
) -> MagicMock:
    """Build a minimal feedparser entry mock."""
    entry = MagicMock()
    entry.id = entry_id
    entry.title = title
    entry.link = link
    entry.summary = summary
    entry.published_parsed = published_parsed
    entry.title_detail = MagicMock()
    entry.title_detail.type = "text/plain"

    if tags:
        entry.tags = [MagicMock(term=t) for t in tags]
    else:
        del entry.tags  # ensure hasattr returns False

    if media_content:
        entry.media_content = [{"url": media_content}]
    else:
        del entry.media_content

    return entry


class TestParseEntry:
    def test_basic_parse(self):
        fm = make_feed_manager()
        entry = make_rss_entry()
        article = fm._parse_entry(entry)

        assert isinstance(article, Article)
        assert article.id == "https://deadline.com/?p=999"
        assert article.title == "Test Movie News"
        assert article.link == "https://deadline.com/article"
        assert article.summary == "Short description of the news."
        assert article.date == datetime(2026, 4, 13, 10, 30, 0)

    def test_default_status_is_new(self):
        fm = make_feed_manager()
        article = fm._parse_entry(make_rss_entry())
        assert article.status == ArticleStatus.NEW

    def test_tags_joined_with_comma(self):
        fm = make_feed_manager()
        entry = make_rss_entry(tags=["Film", "Drama", "Oscar"])
        article = fm._parse_entry(entry)
        assert article.tags == "Film, Drama, Oscar"

    def test_no_tags_returns_none(self):
        fm = make_feed_manager()
        entry = make_rss_entry(tags=None)
        article = fm._parse_entry(entry)
        assert article.tags is None

    def test_media_content_extracted(self):
        fm = make_feed_manager()
        entry = make_rss_entry(media_content="https://example.com/poster.jpg")
        article = fm._parse_entry(entry)
        assert article.media_content == "https://example.com/poster.jpg"

    def test_no_media_content_returns_none(self):
        fm = make_feed_manager()
        entry = make_rss_entry(media_content=None)
        article = fm._parse_entry(entry)
        assert article.media_content is None

    def test_date_parsed_correctly(self):
        fm = make_feed_manager()
        entry = make_rss_entry(published_parsed=(2026, 1, 15, 8, 0, 0, 0, 0, 0))
        article = fm._parse_entry(entry)
        assert article.date == datetime(2026, 1, 15, 8, 0, 0)


class TestFetchRecentArticles:
    def test_returns_empty_list_on_network_error(self):
        fm = make_feed_manager()
        with patch("feed_manager.feedparser.parse", side_effect=Exception("Network error")):
            articles = fm.fetch_recent_articles(hours_back=1)
        assert articles == []

    def test_skips_existing_articles(self):
        fm = make_feed_manager()
        fm.db.article_exists.return_value = True

        entry = make_rss_entry()
        mock_feed = MagicMock()
        mock_feed.entries = [entry]

        with patch("feed_manager.feedparser.parse", return_value=mock_feed):
            articles = fm.fetch_recent_articles(hours_back=24)

        assert articles == []

    def test_returns_new_articles_within_window(self):
        fm = make_feed_manager()
        fm.db.article_exists.return_value = False

        # Use a very recent date so it falls within any time window
        now_tuple = datetime.now().timetuple()[:6] + (0, 0, 0)
        entry = make_rss_entry(published_parsed=now_tuple)
        mock_feed = MagicMock()
        mock_feed.entries = [entry]

        with patch("feed_manager.feedparser.parse", return_value=mock_feed), \
             patch("feed_manager.time.sleep"):
            articles = fm.fetch_recent_articles(hours_back=1)

        assert len(articles) == 1
        assert articles[0].id == entry.id
