# feed_manager.py
import feedparser
import requests
import time
from datetime import datetime, timedelta
from typing import List, Optional
from bs4 import BeautifulSoup
import hashlib
from models import Article, RatingResult, ArticleStatus
from config import config


class FeedManager:
    def __init__(self, config: config, db_manager, logger):
        self.config = config
        self.db = db_manager
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; AutopostBot/1.0)'
        })

    def fetch_recent_articles(self, hours_back: int = 1) -> List[Article]:
        """Fetch articles from the last N hours"""
        try:
            self.logger.info(f"Fetching articles from {self.config.RSS_URL}")

            # Parse RSS feed
            feed = feedparser.parse(self.config.RSS_URL)
            articles = []
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            #self.logger.info(f"cutoff_time - {cutoff_time}  | feed len - {len(feed)}")      #
            for entry in feed.entries:
                # Check if article is recent enough
                published_time = datetime(*entry.published_parsed[:6])
                #self.logger.info(f"published_time - {published_time}")  #
                if published_time < cutoff_time:
                    self.logger.info(f"Reached cutoff time, stopping at {published_time}")
                    break

                #self.logger.info(f"--------------->1")  #
                # Check if article already exists
                if self.db.article_exists(entry.id):
                    self.logger.info(f"Article {entry.id} already exists, stopping")
                    break
                #self.logger.info(f"--------------->2")  #
                # Create article object
                article = self._parse_entry(entry)
                articles.append(article)
                #self.logger.info(f"--------------->3")  #
                # Respect rate limits
                time.sleep(0.1)

            self.logger.info(f"Fetched {len(articles)} new articles")
            return articles

        except Exception as e:
            self.logger.error(f"Error fetching RSS feed: {str(e)}")
            return []

    def _parse_entry(self, entry) -> Article:
        """Parse RSS entry into Article object"""
        # Extract media content
        media_url = None
        if hasattr(entry, 'media_content') and entry.media_content:
            media_url = entry.media_content[0].get('url')

        # Extract and clean tags
        tags = None
        if hasattr(entry, 'tags') and entry.tags:
            tags = ', '.join([tag.term for tag in entry.tags])

        return Article(
            id=entry.id,
            title=entry.title,
            type=getattr(entry.title_detail, 'type', None) if hasattr(entry, 'title_detail') else None,
            link=entry.link,
            date=datetime(*entry.published_parsed[:6]),
            tags=tags,
            summary=entry.summary,
            media_content=media_url
        )

    def get_full_article_content(self, url: str) -> Optional[str]:
        # version1
        '''
        """Scrape full article content from URL"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'aside']):
                element.decompose()

            # Extract main content (adapt selectors based on site structure)
            content_selectors = [
                'article',
                '.entry-content',
                '.post-content',
                '.content',
                'main'
            ]

            content = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content = elements[0].get_text(strip=True)
                    break

            return content if content else soup.get_text(strip=True)

        except Exception as e:
            self.logger.error(f"Error fetching full content from {url}: {str(e)}")
            return None
        '''
        #version2

        """Scrape full article content from URL with improved targeting"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # First, let's be more conservative and only remove clearly unwanted elements
            unwanted_tags = ['script', 'style', 'nav', 'footer', 'noscript', 'form']
            for tag in unwanted_tags:
                for element in soup.find_all(tag):
                    element.decompose()

            # Remove specific unwanted classes/ids (more conservative approach)
            unwanted_selectors = [
                '.social-share', '.share-buttons', '.advertisement', '.ad-container',
                '.comments-section', '.comment-form', '.newsletter-signup',
                '.related-stories', '.more-stories', '.sidebar', '.author-bio',
                '.tags-container', '.breadcrumb', '.pagination'
            ]

            for selector in unwanted_selectors:
                for element in soup.select(selector):
                    element.decompose()

            # Try multiple content selectors in order of preference
            content_selectors = [
                # Most specific first
                'article .entry-content',
                'article .post-content',
                'article .content',
                '.entry-content',
                '.post-content',
                '.article-content',
                '.story-content',
                '.main-content',
                # More general
                'article',
                'main',
                '.content'
            ]

            article_content = None

            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    article_content = elements[0]
                    break

            if not article_content:
                # Fallback to body content
                article_content = soup.find('body')

            if article_content:
                # Extract text from paragraphs and headers within the article
                content_parts = []

                # Find all paragraphs and headers
                for element in article_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    text = element.get_text(strip=True)

                    # Skip empty or very short text
                    if not text or len(text) < 20:
                        continue

                    # Check element classes for unwanted patterns
                    element_classes = ' '.join(element.get('class', [])).lower()

                    # Skip elements with caption-like classes
                    skip_patterns = [
                        'caption', 'credit', 'source', 'byline', 'author',
                        'share', 'social', 'ad', 'promo', 'related', 'tag',
                        'meta', 'widget', 'sidebar'
                    ]

                    if any(pattern in element_classes for pattern in skip_patterns):
                        continue

                    # Skip text that looks like captions or credits
                    text_lower = text.lower()
                    caption_indicators = [
                        'image:', 'photo:', 'credit:', 'source:', 'getty images',
                        'reuters', 'ap photo', 'courtesy of', 'via'
                    ]

                    if any(indicator in text_lower for indicator in caption_indicators):
                        continue

                    # Skip very short paragraphs that might be captions
                    if len(text) < 30:
                        continue

                    content_parts.append(text)

                # Join the content parts
                content = '\n\n'.join(content_parts)

                # If we didn't get much content, try a broader approach
                if not content or len(content) < 100:
                    # Get all text but filter more carefully
                    all_text = article_content.get_text(separator='\n', strip=True)
                    lines = [line.strip() for line in all_text.split('\n') if line.strip()]

                    # Filter out short lines and obvious non-content
                    filtered_lines = []
                    for line in lines:
                        if (len(line) > 30 and
                                not line.lower().startswith(('image:', 'photo:', 'credit:', 'source:')) and
                                'getty images' not in line.lower() and
                                'deadline.com' not in line.lower() and
                                'watch on deadline' not in line.lower()):
                            filtered_lines.append(line)

                    content = '\n\n'.join(filtered_lines)

                return content.strip() if content and content.strip() else None

            return None

        except Exception as e:
            self.logger.error(f"Error fetching full content from {url}: {str(e)}")
            return None
