import feedparser

SEARCH_FEED = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

# Curated feeds per category — used when a topic matches a known category
CATEGORIES = {
    "tech": [
        ("Ars Technica",  "https://feeds.arstechnica.com/arstechnica/index"),
        ("The Verge",     "https://www.theverge.com/rss/index.xml"),
        ("TechCrunch",    "https://techcrunch.com/feed/"),
        ("Wired",         "https://www.wired.com/feed/rss"),
    ],
    "politics": [
        ("NYT Politics",  "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml"),
        ("NPR Politics",  "https://feeds.npr.org/1014/rss.xml"),
        ("The Hill",      "https://thehill.com/rss/syndicator/19110"),
        ("Politico",      "https://www.politico.com/rss/politics08.xml"),
    ],
    "business": [
        ("CNBC",          "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("MarketWatch",   "http://feeds.marketwatch.com/marketwatch/topstories"),
        ("Reuters Biz",   "https://feeds.reuters.com/reuters/businessNews"),
    ],
    "celebrities": [
        ("People",        "https://people.com/feed/"),
        ("E! News",       "https://www.eonline.com/syndication/feeds/rssfeeds/topstories.xml"),
        ("TMZ",           "https://www.tmz.com/rss.xml"),
    ],
    "sports": [
        ("ESPN",          "https://www.espn.com/espn/rss/news"),
        ("BBC Sport",     "https://feeds.bbci.co.uk/sport/rss.xml"),
        ("CBS Sports",    "https://www.cbssports.com/rss/headlines/"),
    ],
    "science": [
        ("Sci American",  "https://rss.sciam.com/ScientificAmerican-News"),
        ("Science Daily", "https://www.sciencedaily.com/rss/all.xml"),
        ("Nature",        "https://www.nature.com/nature.rss"),
    ],
    "world": [
        ("BBC World",     "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Reuters World", "https://feeds.reuters.com/reuters/worldNews"),
        ("NPR World",     "https://feeds.npr.org/1004/rss.xml"),
    ],
    "ai": [
        ("Ars Technica",  "https://feeds.arstechnica.com/arstechnica/index"),
        ("The Verge",     "https://www.theverge.com/rss/index.xml"),
        ("MIT Tech",      "https://www.technologyreview.com/feed/"),
        ("NYT Tech",      "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"),
    ],
    "finance": [
        ("MarketWatch",   "http://feeds.marketwatch.com/marketwatch/topstories"),
        ("CNBC",          "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("Reuters Biz",   "https://feeds.reuters.com/reuters/businessNews"),
        ("NYT Business",  "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ],
}

# Aliases so "artificial intelligence" → "ai", "celebrity" → "celebrities", etc.
ALIASES = {
    "artificial intelligence": "ai",
    "machine learning": "ai",
    "celebrity": "celebrities",
    "entertainment": "celebrities",
    "economy": "finance",
    "markets": "finance",
    "technology": "tech",
    "global": "world",
    "international": "world",
}

def _resolve_category(topic):
    key = topic.lower().strip()
    return CATEGORIES.get(ALIASES.get(key, key))

def _get_image(entry):
    for attr in ("media_content", "media_thumbnail"):
        val = getattr(entry, attr, None)
        if val:
            return val[0].get("url")
    if getattr(entry, "enclosures", None):
        return entry.enclosures[0].get("href")
    return None

def _to_item(entry, source=""):
    return {
        "title": entry.title,
        "link": entry.link,
        "summary": getattr(entry, "summary", ""),
        "image": _get_image(entry),
        "source": source or (getattr(entry, "source", {}) or {}).get("title", ""),
    }

def get_news(topics, max_items=6):
    results = {}

    for topic in topics:
        seen, items = set(), []
        category_feeds = _resolve_category(topic)

        if category_feeds:
            # Pull from curated category feeds
            for source, url in category_feeds:
                d = feedparser.parse(url)
                for e in d.entries:
                    if e.title not in seen:
                        seen.add(e.title)
                        items.append(_to_item(e, source))
                    if len(items) >= max_items:
                        break
                if len(items) >= max_items:
                    break
        else:
            # Arbitrary topic — fall back to Google News search
            d = feedparser.parse(SEARCH_FEED.format(query=topic.replace(" ", "+")))
            for e in d.entries:
                if e.title not in seen:
                    seen.add(e.title)
                    items.append(_to_item(e))
                if len(items) >= max_items:
                    break

        results[topic] = items[:max_items]

    return results