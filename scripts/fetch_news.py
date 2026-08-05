import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from googlenewsdecoder import gnewsdecoder


SEARCHES = [
    ("생성형 AI", "생성형 AI OR ChatGPT OR Claude OR Gemini OR OpenAI"),
    ("AI 반도체", "AI 반도체 OR GPU OR 엔비디아"),
    ("AI 정책", "인공지능 정책 OR AI 규제 OR AI 법안"),
]

MAX_ARTICLES = 10
MAX_AGE = timedelta(days=7)
MAX_DESCRIPTION_LENGTH = 250
OUTPUT_FILE = Path(__file__).resolve().parents[1] / "news.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadata = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return

        attributes = {
            str(key).lower(): value
            for key, value in attrs
            if key and value
        }

        key = (
            attributes.get("property")
            or attributes.get("name")
            or ""
        ).lower()

        content = attributes.get("content", "").strip()

        if key and content:
            self.metadata[key] = content


def contains_korean(text):
    return bool(re.search(r"[가-힣]", text))


def normalize_title(title):
    return re.sub(r"[^0-9a-z가-힣]+", "", title.lower())


def clean_title(title, source):
    title = html.unescape(title).strip()

    if source and title.endswith(f" - {source}"):
        title = title[: -(len(source) + 3)].strip()

    return title


def clean_description(description):
    description = html.unescape(description)
    description = re.sub(r"<[^>]+>", " ", description)
    description = re.sub(r"\s+", " ", description).strip()

    unwanted_texts = [
        "기자",
        "무단전재",
        "재배포 금지",
    ]

    if not description or not contains_korean(description):
        return ""

    if len(description) < 20:
        return ""

    if any(
        description == unwanted
        for unwanted in unwanted_texts
    ):
        return ""

    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[:MAX_DESCRIPTION_LENGTH].rstrip() + "…"

    return description


def decode_google_news_url(google_url):
    try:
        result = gnewsdecoder(google_url, interval=0.2)

        if result.get("status"):
            decoded_url = result.get("decoded_url", "").strip()

            if decoded_url.startswith(("https://", "http://")):
                return decoded_url
    except Exception as error:
        print(f"원문 주소 확인 실패: {error}")

    return google_url


def fetch_article_description(article_url):
    if "news.google.com" in article_url:
        return ""

    try:
        request = urllib.request.Request(
            article_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
            },
        )

        with urllib.request.urlopen(request, timeout=12) as response:
            page = response.read(500_000)

            encoding = response.headers.get_content_charset() or "utf-8"
            page_text = page.decode(encoding, errors="replace")

        parser = MetadataParser()
        parser.feed(page_text)

        description = (
            parser.metadata.get("og:description")
            or parser.metadata.get("twitter:description")
            or parser.metadata.get("description")
            or ""
        )

        return clean_description(description)

    except Exception as error:
        print(f"기사 미리보기 수집 실패: {article_url} / {error}")
        return ""


def fetch_feed(category, query):
    parameters = urllib.parse.urlencode({
        "q": f"{query} when:7d",
        "hl": "ko",
        "gl": "KR",
        "ceid": "KR:ko",
    })

    feed_url = f"https://news.google.com/rss/search?{parameters}"

    request = urllib.request.Request(
        feed_url,
        headers={"User-Agent": USER_AGENT},
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    articles = []

    for item in root.findall("./channel/item"):
        raw_title = item.findtext("title", default="")
        google_link = item.findtext("link", default="").strip()
        source = item.findtext("source", default="Google News").strip()
        published_text = item.findtext("pubDate", default="")

        if not raw_title or not google_link or not published_text:
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

        articles.append({
            "title": title,
            "description": "",
            "source": source,
            "publishedAt": published_at.isoformat(),
            "url": google_link,
            "category": category,
        })

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

    for index, article in enumerate(unique_articles, start=1):
        print(
            f"[{index}/{len(unique_articles)}] "
            f"{article['title']} 미리보기 수집 중"
        )

        original_url = decode_google_news_url(article["url"])
        article["url"] = original_url
        article["description"] = fetch_article_description(original_url)

    OUTPUT_FILE.write_text(
        json.dumps(
            unique_articles,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    descriptions_count = sum(
        bool(article["description"])
        for article in unique_articles
    )

    print(
        f"{len(unique_articles)}개 기사를 저장했습니다. "
        f"미리보기 수집 성공: {descriptions_count}개"
    )


if __name__ == "__main__":
    main()
