import os

# Bot configuration
API_TOKEN = os.environ.get('TELEGRAM_API_TOKEN', '7849996561:AAHCSSt9W2nffW07UPp7l2zmWGWFtgLgNkk')

# Initial user IDs (can be extended dynamically)
DEFAULT_USERS = [
    957555131,
    502783765
]

# RSS feeds sources
RSS_FEEDS = [
    "https://lenta.ru/rss/news",
    "https://news.mail.ru/rss/90/",
    "https://russian.rt.com/rss",
]

# News update frequency in seconds
DAILY_UPDATE_INTERVAL = 86400  # 24 hours
TEST_UPDATE_INTERVAL = 60      # 1 minute (for testing)

# News limits
NEWS_PER_FEED = 3
