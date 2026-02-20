# Glue ETL: (1) uploads/ -> cleaned/  (2) external/raw/*.json -> external/kendra_docs/ for Kendra
# Run with --source_bucket and --clean_output_prefix (set in Terraform default_arguments).
import sys
import json
import boto3
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, ["source_bucket", "clean_output_prefix", "JOB_NAME"])
bucket = args["source_bucket"]
prefix_out = args["clean_output_prefix"]
s3 = boto3.client("s3")

# -----------------------------------------------------------------------------
# 1) Uploads: normalize text, write to cleaned/
# -----------------------------------------------------------------------------
paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=bucket, Prefix="uploads/"):
    for obj in page.get("Contents") or []:
        key = obj["Key"]
        if not key.endswith((".txt", ".csv")):
            continue
        try:
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            text = body.decode("utf-8", errors="replace").strip()
            text_clean = " ".join(text.split())
            out_key = prefix_out + key.replace("uploads/", "")
            s3.put_object(Bucket=bucket, Key=out_key, Body=text_clean.encode("utf-8"), ContentType="text/plain; charset=utf-8")
        except Exception:
            pass

# -----------------------------------------------------------------------------
# 2) External ingest: raw JSON (Google CSE, News API) -> Kendra-ready .txt
#    Writes to external/kendra_docs/ so Kendra S3 data source can index.
# -----------------------------------------------------------------------------
KENDRA_PREFIX = "external/kendra_docs"
seen_slugs = set()
for page in paginator.paginate(Bucket=bucket, Prefix="external/raw/"):
    for obj in page.get("Contents") or []:
        key = obj["Key"]
        if not key.endswith(".json") or "_error.json" in key:
            continue
        try:
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            data = json.loads(body.decode("utf-8", errors="replace"))
            parts = []
            # Google CSE: { "items": [ { "title", "snippet", "link" } ] }
            for item in data.get("items", []):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                if snippet:
                    parts.append(f"[Google] {title}\n{snippet}\nSource: {link}")
            # Microsoft Bing Web: { "webPages": { "value": [ { "name", "snippet", "url" } ] } }
            for p in data.get("webPages", {}).get("value", [])[:10]:
                name = p.get("name", "")
                snippet = p.get("snippet", "")
                url = p.get("url", "")
                if snippet:
                    parts.append(f"[Bing] {name}\n{snippet}\nSource: {url}")
            # Microsoft Bing News: { "value": [ { "name", "description", "url", "datePublished" } ] }
            for art in data.get("value", [])[:10]:
                if isinstance(art, dict) and art.get("datePublished") is not None:
                    name = art.get("name", "")
                    desc = art.get("description", "") or ""
                    url = art.get("url", "")
                    date_pub = art.get("datePublished", "")
                    if name or desc:
                        parts.append(f"[Bing News] {name}\n{desc}\nDate: {date_pub}\nSource: {url}")
            # DuckDuckGo: { "Abstract", "AbstractURL", "RelatedTopics": [ { "Text", "FirstURL" } ] }
            abstract = (data.get("Abstract") or "").strip()
            if abstract:
                parts.append(f"[DuckDuckGo] {abstract}\nSource: {data.get('AbstractURL') or data.get('AbstractSource')}")
            for t in data.get("RelatedTopics", [])[:8]:
                if isinstance(t, dict) and (t.get("Text") or "").strip():
                    parts.append(f"[DuckDuckGo] {t.get('Text')}\nSource: {t.get('FirstURL', '')}")
            # News API: { "articles": [ { "title", "description", "url", "publishedAt" } ] }
            for art in data.get("articles", [])[:10]:
                title = art.get("title", "")
                desc = art.get("description", "") or ""
                url = art.get("url", "")
                pub = art.get("publishedAt", "")
                if title or desc:
                    date_line = f"\nDate: {pub}" if pub else ""
                    parts.append(f"[News] {title}\n{desc}{date_line}\nSource: {url}")
            if not parts:
                continue
            # One doc per company slug (from path: external/raw/<slug>/...)
            slug = key.split("/")[2] if len(key.split("/")) > 2 else "external"
            text = "\n\n---\n\n".join(parts)
            out_key = f"{KENDRA_PREFIX}/glue_{slug}_{key.split('/')[-1].replace('.json', '')}.txt"
            s3.put_object(Bucket=bucket, Key=out_key, Body=text.encode("utf-8"), ContentType="text/plain; charset=utf-8")
            seen_slugs.add(slug)
        except Exception:
            pass
