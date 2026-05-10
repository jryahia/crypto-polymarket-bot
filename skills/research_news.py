"""Research crypto news and market sentiment from multiple sources."""

from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from src.config import get_settings
from src.memory_store import get_memory_store

settings = get_settings()

DESCRIPTION = "Fetch and analyze crypto news and sentiment from CryptoPanic and NewsAPI"
PARAMS = {
    "query": "str — search term or asset name (e.g. Bitcoin, Ethereum)",
    "limit": "int — number of articles to fetch (default: 10)",
    "currencies": "str — comma-separated crypto tickers (e.g. BTC,ETH)",
}
RETURNS = "dict with articles, sentiment summary, and key themes"

CRYPTOPANIC_URL = "https://cryptopanic.com/api/v1/posts/"
NEWSAPI_URL = "https://newsapi.org/v2/everything"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    query = params.get("query", "crypto market")
    limit = int(params.get("limit", 10))
    currencies = params.get("currencies", "BTC,ETH")

    articles: list[dict[str, Any]] = []

    # CryptoPanic feed
    if settings.cryptopanic_api_key:
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.get(
                    CRYPTOPANIC_URL,
                    params={
                        "auth_token": settings.cryptopanic_api_key,
                        "currencies": currencies,
                        "filter": "hot",
                        "public": "true",
                        "limit": limit,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                for post in data.get("results", [])[:limit]:
                    votes = post.get("votes", {})
                    bullish = votes.get("positive", 0)
                    bearish = votes.get("negative", 0)
                    total_votes = bullish + bearish
                    sentiment = "neutral"
                    if total_votes > 0:
                        ratio = bullish / total_votes
                        sentiment = "bullish" if ratio > 0.6 else ("bearish" if ratio < 0.4 else "neutral")
                    articles.append({
                        "source": "cryptopanic",
                        "title": post.get("title", ""),
                        "url": post.get("url", ""),
                        "published": post.get("published_at", ""),
                        "sentiment": sentiment,
                        "bullish_votes": bullish,
                        "bearish_votes": bearish,
                        "currencies": [c.get("code", "") for c in post.get("currencies", [])],
                    })
        except Exception as exc:
            logger.warning(f"research_news: CryptoPanic failed: {exc}")

    # NewsAPI fallback
    if settings.news_api_key and len(articles) < limit:
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.get(
                    NEWSAPI_URL,
                    params={
                        "q": query,
                        "apiKey": settings.news_api_key,
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": limit - len(articles),
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                for article in data.get("articles", []):
                    articles.append({
                        "source": "newsapi",
                        "title": article.get("title", ""),
                        "url": article.get("url", ""),
                        "published": article.get("publishedAt", ""),
                        "description": article.get("description", "")[:200],
                        "sentiment": "neutral",
                    })
        except Exception as exc:
            logger.warning(f"research_news: NewsAPI failed: {exc}")

    if not articles:
        logger.info("research_news: no API keys configured, returning mock data")
        articles = [{
            "source": "mock",
            "title": f"No news API configured — set CRYPTOPANIC_API_KEY or NEWS_API_KEY",
            "url": "",
            "published": "",
            "sentiment": "neutral",
        }]

    bullish_count = sum(1 for a in articles if a.get("sentiment") == "bullish")
    bearish_count = sum(1 for a in articles if a.get("sentiment") == "bearish")
    total = len(articles)

    if total > 0 and bullish_count / total > 0.6:
        overall_sentiment = "bullish"
    elif total > 0 and bearish_count / total > 0.6:
        overall_sentiment = "bearish"
    else:
        overall_sentiment = "mixed"

    result = {
        "query": query,
        "articles": articles,
        "total": total,
        "sentiment_summary": {
            "overall": overall_sentiment,
            "bullish": bullish_count,
            "bearish": bearish_count,
            "neutral": total - bullish_count - bearish_count,
        },
    }

    try:
        store = get_memory_store()
        summary = f"News research for '{query}': {overall_sentiment} sentiment. Top: {articles[0]['title'][:100] if articles else 'none'}"
        store.add_market_observation(
            symbol=query.upper().replace(" ", "_"),
            observation=summary,
            indicators={"sentiment": overall_sentiment, "article_count": total},
        )
    except Exception as e:
        logger.debug(f"research_news: memory store failed: {e}")

    logger.info(f"research_news: '{query}' — {total} articles, sentiment={overall_sentiment}")
    return result
