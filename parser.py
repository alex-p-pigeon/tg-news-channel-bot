import feedparser

def get_movie_news(feed_url='https://deadline.com/feed/', max_items=5):
    """
    Fetches latest movie news from an RSS feed.

    Args:
        feed_url (str): URL of the RSS feed.
        max_items (int): How many news items to return.

    Returns:
        List of dictionaries with title, summary, and link.
    """
    feed = feedparser.parse(feed_url)
    news_items = []

    i = 0
    for entry in feed.entries[:max_items]:
        i += 1
        print('-------------------------------------------------------------------------------------------------')
        print(i, ' entry - ', entry)
        item = {
            'title': entry.title,
            'summary': entry.summary,
            'link': entry.link
        }
        news_items.append(item)

    return news_items

if __name__ == "__main__":
    news = get_movie_news()
    for i, item in enumerate(news, 1):
        print(f"\n🔹 News {i}")
        print(f"📰 Title: {item['title']}")
        print(f"📄 Summary: {item['summary'][:200]}...")  # cropped for readability
        print(f"🔗 Link: {item['link']}")
