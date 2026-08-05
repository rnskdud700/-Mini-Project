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

function createNewsCard(article) {
  const card = document.createElement("article");
  card.className = "news-card";

  const meta = document.createElement("div");
  meta.className = "news-meta";

  const source = document.createElement("span");
  source.className = "news-source";
  source.textContent = article.source;

  const date = document.createElement("time");
  date.textContent = formatDate(article.publishedAt);

  const title = document.createElement("h3");
  title.className = "news-title";
  title.textContent = article.title;

  const description = document.createElement("p");
  description.className = "news-description";
  description.textContent =
    article.description || "제공된 기사 설명이 없습니다.";

  const category = document.createElement("span");
  category.className = "news-category";
  category.textContent = article.category;

  const link = document.createElement("a");
  link.className = "news-link";
  link.href = article.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "기사 원문 보기 →";

  meta.append(source, date);
  card.append(meta, title, description, category, link);

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
      (a, b) => new Date(b.publishedAt) - new Date(a.publishedAt)
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
    filterButtons.forEach(item => item.classList.remove("active"));
    button.classList.add("active");

    selectedCategory = button.dataset.category;
    renderNews();
  });
});

refreshButton.addEventListener("click", loadNews);

loadNews();