"""
External Ingest Lambda — multi-source web/API data for Kendra + Glue.
Sources: Google CSE, Microsoft Bing Web, Bing News Search, DuckDuckGo (no key), News API.
Uses a "latest news" oriented query for recent company stories.
Writes raw JSON + Kendra-ready .txt to S3. Glue cleans raw; Kendra indexes external/kendra_docs/.
"""
import json
import os
import re
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

SOURCE_BUCKET = os.environ.get("SOURCE_BUCKET", "")
# Google Custom Search
GOOGLE_CSE_KEY = os.environ.get("GOOGLE_CSE_API_KEY", "")
GOOGLE_CSE_CX = os.environ.get("GOOGLE_CSE_CX", "")
# Microsoft Bing Web Search (Azure)
BING_SUBSCRIPTION_KEY = os.environ.get("BING_SUBSCRIPTION_KEY", "")
# DuckDuckGo Instant Answer — no API key
# News API
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

S3 = None  # lazy init


def _s3():
    global S3
    if S3 is None:
        import boto3
        S3 = boto3.client("s3")
    return S3


def _slug(name):
    """Safe key prefix from company name."""
    s = re.sub(r"[^\w\s-]", "", (name or "").strip())[:50]
    return re.sub(r"[-\s]+", "-", s).strip("-").lower() or "unknown"


def handler(event, context):
    """Ingest external data for a company. Body: { company_name, context? }."""
    body = _parse_body(event)
    company_name = (body.get("company_name") or "").strip()
    extra_context = (body.get("context") or "").strip()

    if not company_name:
        return _response(400, {"error": "company_name is required"})
    if not SOURCE_BUCKET:
        return _response(500, {"error": "SOURCE_BUCKET not configured"})

    slug = _slug(company_name)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    prefix_raw = f"external/raw/{slug}"
    prefix_kendra = "external/kendra_docs"
    # News-oriented query so Google/Bing/DuckDuckGo surface latest company stories
    query = (f"{company_name} latest news {extra_context}".strip() if extra_context else f"{company_name} latest news").strip()[:200] or f"{company_name} latest news"

    sources_used = []
    all_snippets = []

    # 1) Google Custom Search
    if GOOGLE_CSE_KEY and GOOGLE_CSE_CX:
        try:
            g_results = _fetch_google_cse(query, num=8)
            _write_raw(prefix_raw, f"google_{ts}.json", g_results)
            sources_used.append("google")
            for item in g_results.get("items", []):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                if snippet:
                    all_snippets.append(f"[Google] {title}\n{snippet}\nSource: {link}")
        except Exception as e:
            _write_raw(prefix_raw, f"google_{ts}_error.json", {"error": str(e), "items": []})

    # 2) Microsoft Bing Web Search
    if BING_SUBSCRIPTION_KEY:
        try:
            bing_results = _fetch_bing(query, count=8)
            _write_raw(prefix_raw, f"bing_{ts}.json", bing_results)
            sources_used.append("bing")
            for p in bing_results.get("webPages", {}).get("value", [])[:10]:
                name = p.get("name", "")
                snippet = p.get("snippet", "")
                url = p.get("url", "")
                if snippet:
                    all_snippets.append(f"[Bing] {name}\n{snippet}\nSource: {url}")
        except Exception as e:
            _write_raw(prefix_raw, f"bing_{ts}_error.json", {"error": str(e)})

    # 2b) Microsoft Bing News Search (same key; returns articles with datePublished)
    if BING_SUBSCRIPTION_KEY:
        try:
            bing_news_results = _fetch_bing_news(query, count=8)
            _write_raw(prefix_raw, f"bing_news_{ts}.json", bing_news_results)
            sources_used.append("bing_news")
            for art in bing_news_results.get("value", [])[:10]:
                name = art.get("name", "")
                desc = art.get("description", "") or ""
                url = art.get("url", "")
                date_pub = art.get("datePublished", "")
                if name or desc:
                    date_line = f"\nDate: {date_pub}" if date_pub else ""
                    all_snippets.append(f"[Bing News] {name}\n{desc}{date_line}\nSource: {url}")
        except Exception as e:
            _write_raw(prefix_raw, f"bing_news_{ts}_error.json", {"error": str(e)})

    # 3) DuckDuckGo Instant Answer (no API key)
    try:
        ddg_results = _fetch_duckduckgo(query)
        _write_raw(prefix_raw, f"duckduckgo_{ts}.json", ddg_results)
        sources_used.append("duckduckgo")
        abstract = (ddg_results.get("Abstract") or "").strip()
        abstract_url = ddg_results.get("AbstractURL", "")
        abstract_src = ddg_results.get("AbstractSource", "")
        if abstract:
            all_snippets.append(f"[DuckDuckGo] {abstract}\nSource: {abstract_url or abstract_src}")
        for topic in ddg_results.get("RelatedTopics", [])[:8]:
            if not isinstance(topic, dict):
                continue
            text = (topic.get("Text") or "").strip()
            url = topic.get("FirstURL") or ""
            if text:
                all_snippets.append(f"[DuckDuckGo] {text}\nSource: {url}")
    except Exception as e:
        _write_raw(prefix_raw, f"duckduckgo_{ts}_error.json", {"error": str(e)})

    # 4) News API (sorted by publishedAt; include date in snippet)
    if NEWS_API_KEY and company_name:
        try:
            news = _fetch_news_api(company_name, num=8)
            _write_raw(prefix_raw, f"news_{ts}.json", news)
            sources_used.append("news")
            for a in news.get("articles", [])[:8]:
                title = a.get("title", "")
                desc = a.get("description", "") or ""
                url = a.get("url", "")
                pub = a.get("publishedAt", "")
                if title or desc:
                    date_line = f"\nDate: {pub}" if pub else ""
                    all_snippets.append(f"[News] {title}\n{desc}{date_line}\nSource: {url}")
        except Exception as e:
            _write_raw(prefix_raw, f"news_{ts}_error.json", {"error": str(e)})

    if not all_snippets:
        all_snippets.append(f"Company: {company_name}. {extra_context}".strip())
        if not sources_used:
            sources_used.append("placeholder")

    # Single Kendra-ready document
    doc_text = f"# External research: {company_name}\n\n"
    doc_text += "\n\n---\n\n".join(all_snippets[:30])
    kendra_key = f"{prefix_kendra}/{slug}_{ts}.txt"
    _s3().put_object(
        Bucket=SOURCE_BUCKET,
        Key=kendra_key,
        Body=doc_text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )

    return _response(200, {
        "company_name": company_name,
        "sources": sources_used,
        "raw_prefix": prefix_raw,
        "kendra_doc_key": kendra_key,
        "snippet_count": len(all_snippets),
        "message": "External data ingested. Glue can clean raw; Kendra will index kendra_docs after sync.",
    })


def _write_raw(prefix, filename, data):
    _s3().put_object(
        Bucket=SOURCE_BUCKET,
        Key=f"{prefix}/{filename}",
        Body=json.dumps(data, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def _fetch_google_cse(query, num=8):
    """Google Custom Search JSON API."""
    params = {"key": GOOGLE_CSE_KEY, "cx": GOOGLE_CSE_CX, "q": query, "num": min(num, 10)}
    url = "https://www.googleapis.com/customsearch/v1?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "InterviewAI-Ingest/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_bing(query, count=8):
    """Microsoft Bing Web Search API v7. Requires BING_SUBSCRIPTION_KEY (Azure)."""
    url = "https://api.bing.microsoft.com/v7.0/search?" + urllib.parse.urlencode({"q": query, "count": min(count, 50)})
    req = urllib.request.Request(url, headers={
        "Ocp-Apim-Subscription-Key": BING_SUBSCRIPTION_KEY,
        "User-Agent": "InterviewAI-Ingest/1.0",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_bing_news(query, count=8):
    """Microsoft Bing News Search API v7. Same subscription key as Web Search. Returns articles with datePublished."""
    params = {"q": query, "count": min(count, 50), "sortBy": "Date"}
    url = "https://api.bing.microsoft.com/v7.0/news/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Ocp-Apim-Subscription-Key": BING_SUBSCRIPTION_KEY,
        "User-Agent": "InterviewAI-Ingest/1.0",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_duckduckgo(query):
    """DuckDuckGo Instant Answer API. No API key required."""
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({"q": query[:200], "format": "json", "no_html": "1"})
    req = urllib.request.Request(url, headers={"User-Agent": "InterviewAI-Ingest/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_news_api(q, num=8):
    """NewsAPI.org. Sorted by publishedAt for latest stories."""
    params = {"q": q[:100], "pageSize": min(num, 10), "apiKey": NEWS_API_KEY, "language": "en", "sortBy": "publishedAt"}
    url = "https://newsapi.org/v2/everything?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "InterviewAI-Ingest/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_body(event):
    if not event.get("body"):
        return {}
    body = event["body"]
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
    return body or {}


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body),
    }
