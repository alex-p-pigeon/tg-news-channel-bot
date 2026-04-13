# database_manager.py
import psycopg2
from psycopg2 import pool, extras
from psycopg2.errors import DatabaseError
from typing import List, Optional
from contextlib import contextmanager
import json
from config import config
from models import Article, RatingResult, ArticleStatus


class DatabaseManager:
    def __init__(self, config: config, logger):
        self.config = config
        self.logger = logger

        # Create connection pool
        self.connection_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,  # min and max connections
            host=config.DB_HOST.get_secret_value(),
            port=config.DB_PORT.get_secret_value(),
            database=config.DB_NAME.get_secret_value(),
            user=config.DB_USER.get_secret_value(),
            password=config.DB_PASSWORD.get_secret_value()
        )

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        connection = None
        try:
            connection = self.connection_pool.getconn()
            yield connection
        except DatabaseError as e:
            self.logger.error(f"Database error: {str(e)}")
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                self.connection_pool.putconn(connection)

    def save_article(self, article: Article) -> bool:
        """Save article to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                INSERT INTO t_feed (
                    c_id, c_title, c_type, c_link, c_date, c_tags, 
                    c_summary, c_media_content, c_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                values = (
                    article.id, article.title, article.type, article.link,
                    article.date, article.tags, article.summary,
                    article.media_content, article.status.value
                )

                cursor.execute(query, values)
                conn.commit()
                return True

        except DatabaseError as e:
            self.logger.error(f"Error saving article {article.id}: {str(e)}")
            return False

    def article_exists(self, article_id: str) -> bool:
        """Check if article exists in database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM t_feed WHERE c_id = %s", (article_id,))
                return cursor.fetchone() is not None
        except DatabaseError:
            return False

    def get_unprocessed_articles(self, limit: int = 10) -> List[Article]:
        """Get articles that need rating"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                cursor.execute("""
                    SELECT * FROM t_feed 
                    WHERE c_status = 'new' 
                    ORDER BY c_date DESC 
                    LIMIT %s
                """, (limit,))

                articles = []
                for row in cursor.fetchall():
                    article = self._row_to_article(row)
                    articles.append(article)

                return articles
        except DatabaseError as e:
            self.logger.error(f"Error fetching unprocessed articles: {str(e)}")
            return []

    def update_article_rating(self, article_id: str, rating: int, lurkable: int, reasoning: str, category: str) -> bool:
        """Update article rating and lurkable score"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE t_feed 
                    SET c_rating = %s, c_lurkable = %s, c_status = 'rated', c_reasoning = %s, c_category = %s WHERE c_id = %s
                """, (rating, lurkable, reasoning, category, article_id))
                conn.commit()
                return True
        except DatabaseError as e:
            self.logger.error(f"Error updating article rating {article_id}: {str(e)}")
            return False

    def get_best_unposted_article(self) -> Optional[Article]:
        """Get the highest rated unposted article"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

                cursor.execute("""
                    SELECT * FROM t_feed 
                    WHERE c_used = FALSE AND c_status = 'rated' AND c_date >= CURRENT_DATE - INTERVAL '1 day' 
                    ORDER BY c_rating DESC, c_lurkable DESC 
                    LIMIT 1
                """)


                #cursor.execute("""
                #    SELECT * FROM t_feed WHERE c_id = 'https://deadline.com/?p=1236452090'
                #    ORDER BY c_rating DESC, c_lurkable DESC
                #    LIMIT 1
                #""")


                row = cursor.fetchone()
                return self._row_to_article(row) if row else None

        except DatabaseError as e:
            self.logger.error(f"Error fetching best article: {str(e)}")
            return None

    def mark_article_used(self, article_id: str, lurk_translation: str = None) -> bool:
        """Mark article as used and save translation"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                if lurk_translation:
                    cursor.execute("""
                        UPDATE t_feed 
                        SET c_used = TRUE, c_lurk = %s, c_status = 'posted'
                        WHERE c_id = %s
                    """, (lurk_translation, article_id))
                else:
                    cursor.execute("""
                        UPDATE t_feed 
                        SET c_used = TRUE, c_status = 'posted'
                        WHERE c_id = %s
                    """, (article_id,))

                conn.commit()
                return True

        except DatabaseError as e:
            self.logger.error(f"Error marking article as used {article_id}: {str(e)}")
            return False

    def _row_to_article(self, row: dict) -> Article:
        """Convert database row to Article object"""
        return Article(
            id=row['c_id'],
            title=row['c_title'],
            type=row['c_type'],
            link=row['c_link'],
            date=row['c_date'],
            tags=row['c_tags'],
            summary=row['c_summary'],
            media_content=row['c_media_content'],
            rating=row['c_rating'],
            lurkable=row['c_lurkable'],
            rhymable=row['c_reasoning'],
            lurk_translation=row['c_lurk'],
            used=row['c_used'],
            status=ArticleStatus(row['c_status']),
            created_at=row['c_created_at'],
            updated_at=row['c_updated_at'],
            content = row['c_content'],
            category = row['c_category']
        )

    def save_article_content(self, article_id: str, full_content: str) -> bool:
        """
        Save full article content to database

        Args:
            article_id (str): The article ID
            full_content (str): The full article content to save

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Update the article with full content
                cursor.execute("""
                    UPDATE t_feed 
                    SET c_content = %s, c_updated_at = CURRENT_TIMESTAMP
                    WHERE c_id = %s
                """, (full_content, article_id))

                # Check if update was successful
                if cursor.rowcount == 0:
                    self.logger.warning(f"No article found with ID {article_id} to update content")
                    return False

                conn.commit()
                self.logger.info(f"Successfully saved full content for article {article_id}")
                return True

        except Exception as e:
            self.logger.error(f"Error saving content for article {article_id}: {str(e)}")
            return False
