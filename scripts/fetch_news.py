import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


SEARCHES = [
    ("생성형 AI", "생성형 AI OR ChatGPT OR Claude OR Gemini OR OpenAI"),
    ("AI 반도체", "AI 반도체 OR GPU OR 엔비디아"),
    ("AI 정책", "인공지능 정책 OR AI 규제 OR AI 법안"),
]

MAX_ARTICLES = 10
MAX_AGE = timedelta(days=7)

OUTPUT_FILE = Path(__file__).resolve().parents[1] / "news.json"


def contains_korean(text):
    return bool(re.search(r"[가-힣]", text))


def normalize_title(title):
    return re.sub(r"[^0-9a-z가-힣]+", "", title.lower())


def clean_title(title, source):
    title = html.unescape(title).strip()

    if source and title.endswith(f" - {source}"):
        title = title[: -(len(source) + 3)].strip()

    return title


def fetch_feed(category, query):
    parameters = urllib.parse.urlencode(
        {
            "q": f"{query} when:7d",
            "hl": "ko",
            "gl": "KR",
            "ceid": "KR:ko",
        }
    )

    url = f"https://news.google.com/rss/search?{parameters}"

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 AI-News-Briefing/1.0"
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    articles = []

    for item in root.findall("./channel/item"):
        raw_title = item.findtext("title", default="")
        link = item.findtext("link", default="").strip()
        source = item.findtext("source", default="Google News").strip()
        published_text = item.findtext("pubDate", default="")

        if not raw_title or not link or not published_text:
            continue

        try:
            published_at = parsedate_to_datetime(published_text)
        except (TypeError, ValueError):
            continue

        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        title = clean_title(raw_title, source)

        if not contains_korean(title):
            continue

        if datetime.now(timezone.utc) - published_at > MAX_AGE:
            continue

        articles.append(
            {
                "title": title,
                "description": "",
                "source": source,
                "publishedAt": published_at.isoformat(),
                "url": link,
                "category": category,
            }
        )

    return articles


def main():
    collected = []

    for category, query in SEARCHES:
        try:
            collected.extend(fetch_feed(category, query))
        except Exception as error:
            print(f"{category} 수집 실패: {error}")

    unique_articles = []
    seen_titles = set()

    for article in sorted(
        collected,
        key=lambda item: item["publishedAt"],
        reverse=True,
    ):
        title_key = normalize_title(article["title"])

        if not title_key or title_key in seen_titles:
            continue

        seen_titles.add(title_key)
        unique_articles.append(article)

        if len(unique_articles) == MAX_ARTICLES:
            break

    if not unique_articles:
        raise RuntimeError(
            "수집된 기사가 없어 기존 news.json을 유지합니다."
        )

    OUTPUT_FILE.write_text(
        json.dumps(
            unique_articles,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"{len(unique_articles)}개 기사를 news.json에 저장했습니다.")


if __name__ == "__main__":
    main()
