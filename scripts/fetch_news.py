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
from trafilatura import extract


SEARCHES = [
    ("생성형 AI", "생성형 AI OR ChatGPT OR Claude OR Gemini OR OpenAI"),
    ("AI 반도체", "AI 반도체 OR GPU OR 엔비디아"),
    ("AI 정책", "인공지능 정책 OR AI 규제 OR AI 법안"),
]

MAX_ARTICLES = 10
MAX_AGE = timedelta(days=7)

MAX_PREVIEW_LENGTH = 650
MAX_ISSUE_LENGTH = 240
MAX_IMPORTANCE_LENGTH = 300

OUTPUT_FILE = Path(__file__).resolve().parents[1] / "news.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)

IMPORTANCE_WORDS = [
    "전망",
    "기대",
    "계획",
    "예정",
    "목표",
    "의미",
    "중요",
    "영향",
    "확대",
    "강화",
    "성장",
    "활용",
    "기여",
    "개선",
    "필요",
    "가능",
    "예상",
]


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


def clean_text(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def shorten_text(text, maximum_length):
    text = clean_text(text)

    if len(text) <= maximum_length:
        return text

    shortened = text[:maximum_length]

    last_sentence = max(
        shortened.rfind("."),
        shortened.rfind("다."),
        shortened.rfind("요."),
    )

    if last_sentence > maximum_length // 2:
        return shortened[: last_sentence + 1].strip()

    return shortened.rstrip() + "…"


def is_useful_paragraph(paragraph):
    paragraph = clean_text(paragraph)

    if len(paragraph) < 30:
        return False

    unwanted_patterns = [
        "무단전재",
        "재배포 금지",
        "저작권자",
        "기자 =",
        "기자=",
        "구독",
        "로그인",
        "제보",
        "관련기사",
        "Copyright",
        "copyright",
        "기사제보",
        "뉴스레터",
    ]

    return not any(
        pattern in paragraph
        for pattern in unwanted_patterns
    )


def split_sentences(text):
    text = clean_text(text)

    sentences = re.split(
        r"(?<=[.!?])\s+|(?<=다\.)\s+|(?<=요\.)\s+",
        text,
    )

    return [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip()) >= 20
    ]


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


def download_article(article_url):
    if "news.google.com" in article_url:
        return ""

    request = urllib.request.Request(
        article_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.7",
        },
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        page = response.read(1_500_000)
        encoding = response.headers.get_content_charset() or "utf-8"
        return page.decode(encoding, errors="replace")


def get_metadata_description(page_html):
    try:
        parser = MetadataParser()
        parser.feed(page_html)

        description = (
            parser.metadata.get("og:description")
            or parser.metadata.get("twitter:description")
            or parser.metadata.get("description")
            or ""
        )

        description = clean_text(description)

        if contains_korean(description) and len(description) >= 30:
            return shorten_text(description, MAX_PREVIEW_LENGTH)

    except Exception:
        pass

    return ""


def extract_paragraphs(page_html):
    try:
        extracted_json = extract(
            page_html,
            output_format="json",
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            no_fallback=False,
        )

        if not extracted_json:
            return []

        article_data = json.loads(extracted_json)
        article_text = article_data.get("text", "")

        raw_paragraphs = re.split(r"\n+", article_text)

        paragraphs = []

        for raw_paragraph in raw_paragraphs:
            paragraph = clean_text(raw_paragraph)

            if (
                is_useful_paragraph(paragraph)
                and contains_korean(paragraph)
            ):
                paragraphs.append(paragraph)

        return paragraphs

    except Exception as error:
        print(f"본문 분석 실패: {error}")
        return []


def create_preview(paragraphs, metadata_description):
    if not paragraphs:
        return metadata_description

    selected = paragraphs[:3]
    preview = "\n\n".join(selected)

    return shorten_text(preview, MAX_PREVIEW_LENGTH)


def create_key_issue(paragraphs, title):
    candidate_sentences = []

    for paragraph in paragraphs[:4]:
        candidate_sentences.extend(split_sentences(paragraph))

    if not candidate_sentences:
        return shorten_text(title, MAX_ISSUE_LENGTH)

    scored_sentences = []

    for position, sentence in enumerate(candidate_sentences):
        score = 10 - position

        if re.search(r"\d", sentence):
            score += 3

        if any(
            word in sentence
            for word in [
                "발표",
                "출시",
                "개발",
                "도입",
                "공개",
                "협력",
                "투자",
                "규제",
                "서비스",
                "기술",
            ]
        ):
            score += 2

        scored_sentences.append((score, sentence))

    scored_sentences.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return shorten_text(
        scored_sentences[0][1],
        MAX_ISSUE_LENGTH,
    )


def create_importance(paragraphs):
    if not paragraphs:
        return ""

    ending_paragraphs = paragraphs[-5:]
    candidates = []

    for position, paragraph in enumerate(reversed(ending_paragraphs)):
        sentences = split_sentences(paragraph)

        for sentence in sentences:
            score = 5 - position

            for keyword in IMPORTANCE_WORDS:
                if keyword in sentence:
                    score += 3

            candidates.append((score, sentence))

    if not candidates:
        return shorten_text(
            paragraphs[-1],
            MAX_IMPORTANCE_LENGTH,
        )

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    selected_sentences = []

    for _, sentence in candidates:
        if sentence not in selected_sentences:
            selected_sentences.append(sentence)

        if len(selected_sentences) == 2:
            break

    return shorten_text(
        " ".join(selected_sentences),
        MAX_IMPORTANCE_LENGTH,
    )


def analyse_article(article_url, title):
    try:
        page_html = download_article(article_url)

        if not page_html:
            return "", title, ""

        metadata_description = get_metadata_description(page_html)
        paragraphs = extract_paragraphs(page_html)

        preview = create_preview(
            paragraphs,
            metadata_description,
        )

        key_issue = create_key_issue(
            paragraphs,
            title,
        )

        importance = create_importance(paragraphs)

        return preview, key_issue, importance

    except Exception as error:
        print(f"기사 분석 실패: {article_url} / {error}")
        return "", title, ""


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
            "preview": "",
            "keyIssue": "",
            "importance": "",
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
            f"{article['title']} 분석 중"
        )

        original_url = decode_google_news_url(article["url"])
        article["url"] = original_url

        preview, key_issue, importance = analyse_article(
            original_url,
            article["title"],
        )

        article["description"] = preview
        article["preview"] = preview
        article["keyIssue"] = key_issue
        article["importance"] = importance

    OUTPUT_FILE.write_text(
        json.dumps(
            unique_articles,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    preview_count = sum(
        bool(article["preview"])
        for article in unique_articles
    )

    print(
        f"{len(unique_articles)}개 기사를 저장했습니다. "
        f"본문 분석 성공: {preview_count}개"
    )


if __name__ == "__main__":
    main()
