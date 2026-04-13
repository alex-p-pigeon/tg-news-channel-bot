"""Tests for AIProcessor — JSON parsing and RatingResult construction (no real API calls)."""
import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
from models import Article, ArticleStatus, RatingResult
from ai_processor import AIProcessor


def make_processor() -> AIProcessor:
    config = MagicMock()
    logger = MagicMock()
    with patch("ai_processor.OpenAI"):
        processor = AIProcessor(config, logger)
    return processor


def make_article(**kwargs) -> Article:
    defaults = dict(
        id="https://deadline.com/?p=1",
        title="Major Studio Cancels Sequel",
        type=None,
        link="https://deadline.com/article",
        date=datetime(2026, 4, 13),
        tags="film, sequel",
        summary="The studio has decided to cancel the long-awaited sequel.",
        media_content=None,
    )
    defaults.update(kwargs)
    return Article(**defaults)


def _mock_openai_response(content: str):
    """Build a minimal OpenAI response mock that returns `content` as message text."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


class TestRateArticleJsonParsing:
    """Test that rate_article correctly parses GPT JSON output into RatingResult."""

    def test_valid_json_returns_rating_result(self):
        processor = make_processor()
        payload = json.dumps({
            "interest_score": 75,
            "lurkable_score": 65,
            "rhymable_score": 40,
            "reasoning": "Popular franchise, high Russian audience interest",
            "category": "A",
        })
        processor.client.chat.completions.create.return_value = _mock_openai_response(payload)

        article = make_article()
        result = processor.rate_article(article)

        assert isinstance(result, RatingResult)
        assert result.interest_score == 75
        assert result.lurkable_score == 65
        assert result.category == "A"

    def test_invalid_json_returns_none(self):
        processor = make_processor()
        processor.client.chat.completions.create.return_value = _mock_openai_response(
            "Sorry, I cannot rate this."
        )

        article = make_article()
        result = processor.rate_article(article)

        assert result is None

    def test_malformed_json_returns_none(self):
        processor = make_processor()
        processor.client.chat.completions.create.return_value = _mock_openai_response(
            "{interest_score: 80, broken json"
        )
        article = make_article()
        result = processor.rate_article(article)
        assert result is None

    def test_low_interest_category_p_accepted(self):
        """Category P (potpourri) should return scores of 10 per prompt rules."""
        processor = make_processor()
        payload = json.dumps({
            "interest_score": 10,
            "lurkable_score": 10,
            "rhymable_score": 10,
            "reasoning": "Mixed unrelated stories",
            "category": "P",
        })
        processor.client.chat.completions.create.return_value = _mock_openai_response(payload)
        result = processor.rate_article(make_article())
        assert result is not None
        assert result.category == "P"
        assert result.interest_score == 10

    def test_api_exception_returns_none(self):
        """When the API call raises, rate_article catches it and returns None.

        The outer `except Exception` in rate_article absorbs errors so the
        scheduler cycle can continue without crashing. Tenacity retries are
        triggered only when the exception propagates past the inner except block;
        in the current implementation they are swallowed.
        """
        processor = make_processor()
        processor.client.chat.completions.create.side_effect = Exception("API timeout")
        article = make_article()
        result = processor.rate_article(article)
        assert result is None


class TestRatingResultFieldConsistency:
    """Catch field name mismatch between ai_processor output and RatingResult dataclass."""

    def test_rating_result_does_not_have_rhymable_score_field(self):
        """RatingResult uses 'reasoning', not 'rhymable_score'.

        This test documents the known field name bug in main_controller.py
        (lines 113, 122) where rating_result.rhymable_score is accessed
        but that attribute does not exist on RatingResult.
        """
        result = RatingResult(
            interest_score=50,
            lurkable_score=50,
            reasoning="test",
            category="Z",
        )
        assert hasattr(result, "reasoning")
        assert not hasattr(result, "rhymable_score"), (
            "RatingResult should not have 'rhymable_score'. "
            "main_controller.py references this non-existent attribute on lines 113 and 122."
        )
