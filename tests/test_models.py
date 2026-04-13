"""Tests for data models (Article, RatingResult, ArticleStatus)."""
import pytest
from datetime import datetime
from models import Article, RatingResult, ArticleStatus


class TestArticleStatus:
    def test_all_statuses_have_string_values(self):
        expected = {"new", "processing", "rated", "translated", "posted", "failed"}
        actual = {s.value for s in ArticleStatus}
        assert actual == expected

    def test_status_from_string(self):
        assert ArticleStatus("new") == ArticleStatus.NEW
        assert ArticleStatus("posted") == ArticleStatus.POSTED

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            ArticleStatus("invalid_status")


class TestArticle:
    def _make_article(self, **kwargs) -> Article:
        defaults = dict(
            id="https://deadline.com/?p=123",
            title="Test Article",
            type="text/html",
            link="https://deadline.com/article",
            date=datetime(2026, 4, 13, 12, 0, 0),
            tags="film, drama",
            summary="Short summary of the article.",
            media_content="https://example.com/image.jpg",
        )
        defaults.update(kwargs)
        return Article(**defaults)

    def test_default_rating_is_zero(self):
        article = self._make_article()
        assert article.rating == 0
        assert article.lurkable == 0

    def test_default_status_is_new(self):
        article = self._make_article()
        assert article.status == ArticleStatus.NEW

    def test_default_used_is_false(self):
        article = self._make_article()
        assert article.used is False

    def test_optional_fields_default_to_none(self):
        article = self._make_article(tags=None, media_content=None)
        assert article.tags is None
        assert article.media_content is None
        assert article.lurk_translation is None
        assert article.content is None

    def test_article_equality(self):
        a1 = self._make_article()
        a2 = self._make_article()
        assert a1 == a2

    def test_article_with_custom_status(self):
        article = self._make_article(status=ArticleStatus.POSTED, used=True)
        assert article.status == ArticleStatus.POSTED
        assert article.used is True

    def test_article_rating_can_be_set(self):
        article = self._make_article(rating=85, lurkable=72)
        assert article.rating == 85
        assert article.lurkable == 72


class TestRatingResult:
    def test_create_rating_result(self):
        result = RatingResult(
            interest_score=80,
            lurkable_score=65,
            reasoning="Popular actor, high meme potential",
            category="A",
        )
        assert result.interest_score == 80
        assert result.lurkable_score == 65
        assert result.reasoning == "Popular actor, high meme potential"
        assert result.category == "A"

    def test_rating_result_fields(self):
        """RatingResult must have exactly these four fields."""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(RatingResult)}
        assert field_names == {"interest_score", "lurkable_score", "reasoning", "category"}

    def test_score_boundary_values(self):
        result = RatingResult(interest_score=0, lurkable_score=100, reasoning="", category="Z")
        assert result.interest_score == 0
        assert result.lurkable_score == 100
