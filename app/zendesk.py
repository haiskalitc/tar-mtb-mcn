from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify
from slugify import slugify


@dataclass(frozen=True)
class Article:
  article_id: str
  title: str
  slug: str
  source_url: str
  updated_at: str
  markdown: str


class ZendeskClient:
  def __init__(self, base_url: str, locale: str) -> None:
    self.base_url = base_url.rstrip("/")
    self.locale = locale

  # Convert Articles to Markdowns
  def fetch_documents(self, limit: int) -> list[Article]:
    articles = self._fetch_articles(limit)
    documents = []

    for article in articles:
      document = self._to_document(article)
      documents.append(document)

    return documents

  # Fetch articles from Zendesk API
  # Limit the maximum items
  def _fetch_articles(self, limit: int) -> list[dict]:
    sort_by = "updated_at"
    sort_order = "desc"

    url = (
      f"{self.base_url}/api/v2/help_center/"
      f"{self.locale}/articles.json"
      f"?sort_by={sort_by}&sort_order={sort_order}"
    )

    articles: list[dict] = []

    while url and len(articles) < limit:
      response = requests.get(url)
      response.raise_for_status()

      payload = response.json()

      for article in payload.get("articles", []):
        if article.get("draft"):
          continue

        articles.append(article)
        if len(articles) >= limit:
          break

      url = payload.get("next_page") or ""

    return articles

  # Convert Zendesk API response to Article
  # Get fields: id | title | html_url | body
  def _to_document(self, article: dict) -> Article:

    article_id = str(article["id"])
    title = (article.get("title") or "Untitled").strip()
    source_url = article.get("html_url") or ""
    markdown_body = self._html_to_markdown(article.get("body") or "")

    markdown = (
                 f"# {title}\n\n"
                 f"Article URL: {source_url}\n\n"
                 f"{markdown_body}\n"
               ).replace("\r\n", "\n").strip() + "\n"

    return Article(
      article_id=article_id,
      title=title,
      slug=slugify(title) or "article",
      source_url=source_url,
      updated_at=article.get("updated_at") or "",
      markdown=markdown,
    )

  # Convert HTML to Markdown
  @staticmethod
  def _html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for element in soup.select("script, style, nav, aside, form"):
      element.decompose()

    return markdownify(
      str(soup),
      heading_style="ATX",
      bullets="-",
      strip=["script", "style"]
    ).strip()
