
import json
import re
import html
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import feedparser

# Project folders
ROOT = Path(__file__).resolve().parent.parent
SOURCE_FILE = ROOT / "config" / "sources.json"
OUTPUT_FILE = ROOT / "data" / "articles.json"

# Maximum number of new articles to collect per feed
MAX_ARTICLES_PER_SOURCE = 20


def clean_text(value):
    """Remove HTML tags and clean article descriptions."""
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    return " ".join(value.split())[:500]


def load_json(path, default):
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_published_date(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")

    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc).date().isoformat()

    return ""


def collect_articles():
    sources = load_json(SOURCE_FILE, {"sources": []})
    existing = load_json(OUTPUT_FILE, [])

    # Index previously collected articles by URL
    known_urls = {
        article.get("source_url")
        for article in existing
        if article.get("source_url")
    }

    new_articles = []

    for source in sources.get("sources", []):
        if not source.get("enabled", False):
            continue

        if source.get("type") != "rss":
            continue

        print("Reading:", source["name"])

        try:
            feed = feedparser.parse(source["url"])

            if feed.bozo and not feed.entries:
                print("Feed could not be read:", source["name"])
                continue

            count = 0

            for entry in feed.entries:
                if count >= MAX_ARTICLES_PER_SOURCE:
                    break

                article_url = entry.get("link", "").strip()

                if not article_url or article_url in known_urls:
                    continue

                title = clean_text(entry.get("title", ""))

                if not title:
                    continue

                article = {
                    "id": hashlib.sha256(
                        article_url.encode("utf-8")
                    ).hexdigest()[:16],
                    "title": title,
                    "source": source["name"],
                    "source_url": article_url,
                    "category": source["category"],
                    "destination": "",
                    "published_date": get_published_date(entry),
                    "collected_date": datetime.now(
                        timezone.utc
                    ).date().isoformat(),
                    "summary": clean_text(
                        entry.get("summary", "")
                    ),
                    "content_type": "Article"
                }

                new_articles.append(article)
                known_urls.add(article_url)
                count += 1

            print("New articles:", count)

        except Exception as error:
            print("Error reading source:", error)

    # Keep new and previously collected articles
    all_articles = new_articles + existing

    # Sort newest published articles first
    all_articles.sort(
        key=lambda article: (
            article.get("published_date") or
            article.get("collected_date") or ""
        ),
        reverse=True
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            all_articles,
            file,
            indent=2,
            ensure_ascii=False
        )

    print("Total articles stored:", len(all_articles))
    print("New articles collected:", len(new_articles))


if __name__ == "__main__":
    collect_articles()
