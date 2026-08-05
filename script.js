const newsList = document.querySelector("#news-list");
const articleCount = document.querySelector("#article-count");
const emptyMessage = document.querySelector("#empty-message");
const updatedTime = document.querySelector("#updated-time");
const refreshButton = document.querySelector("#refresh-button");
const filterButtons = document.querySelectorAll(".filter-button");

let allArticles = [];
let selectedCategory = "전체";

function formatDate(dateText) {
  const date = new Date(dateText);

  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function createSection(className, headingText, contentText, fallbackText) {
  const section = document.createElement("section");
  section.className = `article-section ${className}`;

  const heading = document.createElement("h4");
  heading.className = "article-section-title";
  heading.textContent = headingText;

  const content = document.createElement("p");
  content.className = "article-section-content";
  content.textContent = contentText || fallbackText;

  section.append(heading, content);

  return section;
}

function createNewsCard(article) {
  const card = document.createElement("article");
  card.className = "news-card";

  const meta = document.createElement("div");
  meta.className = "news-meta";

  const source = document.createElement("span");
  source.className = "news-source";
  source.textContent = article.source || "출처 미상";

  const date = document.createElement("time");
  date.className = "news-date";
  date.dateTime = article.publishedAt;
  date.textContent = formatDate(article.publishedAt);

  const category = document.createElement("span");
  category.className = "news-category";
  category.textContent = article.category;

  meta.append(source, category, date);

  const title = document.createElement("h3");
  title.className = "news-title";
  title.textContent = article.title;

  const contentBox = document.createElement("div");
  contentBox.className = "news-content-box";

  const preview = createSection(
    "preview-section",
    "💡 기사 미리보기",
    article.preview || article.description,
    "기사 본문을 불러오지 못했습니다. 원문에서 내용을 확인해 주세요."
  );

  const originalLinkSection = document.createElement("section");
  originalLinkSection.className =
    "article-section original-link-section";

  const originalLinkTitle = document.createElement("h4");
  originalLinkTitle.className = "article-section-title";
  originalLinkTitle.textContent = "🔗 원문 링크";

  const link = document.createElement("a");
  link.className = "news-link";
  link.href = article.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "기사 원문 바로가기 →";

  originalLinkSection.append(originalLinkTitle, link);

  const keyIssue = createSection(
    "issue-section",
    "🔥 핵심 이슈",
    article.keyIssue,
    "기사 제목과 미리보기를 통해 핵심 내용을 확인해 주세요."
  );

  const importance = createSection(
    "importance-section",
    "🧠 왜 중요한가?",
    article.importance,
    "기사에서 별도의 전망이나 영향에 관한 내용을 찾지 못했습니다."
  );

  contentBox.append(
    preview,
    originalLinkSection,
    keyIssue,
    importance
  );

  card.append(meta, title, contentBox);

  return card;
}

function renderNews() {
  const filteredArticles =
    selectedCategory === "전체"
      ? allArticles
      : allArticles.filter(
          article => article.category === selectedCategory
        );

  newsList.replaceChildren();

  filteredArticles.forEach(article => {
    newsList.append(createNewsCard(article));
  });

  articleCount.textContent = `${filteredArticles.length}개`;
  emptyMessage.hidden = filteredArticles.length !== 0;
}

async function loadNews() {
  refreshButton.disabled = true;
  refreshButton.textContent = "불러오는 중...";

  try {
    const response = await fetch(`news.json?time=${Date.now()}`);

    if (!response.ok) {
      throw new Error("뉴스 데이터를 불러오지 못했습니다.");
    }

    allArticles = await response.json();

    allArticles.sort(
      (a, b) =>
        new Date(b.publishedAt) - new Date(a.publishedAt)
    );

    renderNews();

    updatedTime.textContent = new Intl.DateTimeFormat("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    }).format(new Date());
  } catch (error) {
    console.error(error);

    newsList.replaceChildren();
    articleCount.textContent = "0개";
    emptyMessage.hidden = false;
    emptyMessage.textContent =
      "뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.";
    updatedTime.textContent = "불러오기 실패";
  } finally {
    refreshButton.disabled = false;
    refreshButton.textContent = "새로고침";
  }
}

filterButtons.forEach(button => {
  button.addEventListener("click", () => {
    filterButtons.forEach(item => {
      item.classList.remove("active");
    });

    button.classList.add("active");
    selectedCategory = button.dataset.category;

    renderNews();
  });
});

refreshButton.addEventListener("click", loadNews);

loadNews();
