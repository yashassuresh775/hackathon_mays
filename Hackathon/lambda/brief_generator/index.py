"""
Interviewer Brief Generator Lambda.
Data enrichment: Comprehend (entities, key phrases) + optional Kendra search.
Intelligence: Bedrock → 2-3 page brief + 1-page pre-interview packet.
"""
import json
import os
import boto3
from datetime import datetime

BEDROCK_REGION = os.environ.get("AWS_REGION", "us-east-1")
BRIEFS_BUCKET = os.environ.get("BRIEFS_BUCKET", "")
PACKETS_BUCKET = os.environ.get("PACKETS_BUCKET", "")
METADATA_TABLE = os.environ.get("METADATA_TABLE", "")
SOURCE_BUCKET = os.environ.get("SOURCE_BUCKET", "")
KENDRA_INDEX_ID = os.environ.get("KENDRA_INDEX_ID", "")
EXTERNAL_INGEST_FUNCTION = os.environ.get("EXTERNAL_INGEST_FUNCTION", "")

# Nova can take longer; Lambda timeout is 120s, use 100s read timeout to stay under
from botocore.config import Config
_bedrock_config = Config(read_timeout=100, retries={"max_attempts": 1})
bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION, config=_bedrock_config)
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
comprehend = boto3.client("comprehend", region_name=BEDROCK_REGION)
kendra = boto3.client("kendra", region_name=BEDROCK_REGION) if KENDRA_INDEX_ID else None
lambda_client = boto3.client("lambda", region_name=BEDROCK_REGION)


def handler(event, context):
    """Generate interviewer brief and pre-interview packet from company name / context."""
    body = _parse_body(event)
    company_name = body.get("company_name", "").strip()
    extra_context = body.get("context", "").strip()

    if not company_name:
        return _response(400, {"error": "company_name is required"})

    # Optional: use extracted text from an uploaded document (in cleaned/) for brief context
    document_key = (body.get("document_key") or "").strip()
    uploaded_doc_text = _get_uploaded_document_text(document_key) if document_key else ""

    # Optional: company insights from external API (e.g. CloudFront insights endpoint)
    insights_raw = body.get("insights")
    insights_text = _format_insights(insights_raw) if insights_raw else ""

    # Optional: fetch external data (Google/News) first so Kendra can index it for this request or next sync
    if body.get("ingest_first") and EXTERNAL_INGEST_FUNCTION:
        try:
            lambda_client.invoke(
                FunctionName=EXTERNAL_INGEST_FUNCTION,
                InvocationType="RequestResponse",
                Payload=json.dumps({"body": json.dumps({"company_name": company_name, "context": extra_context})}),
            )
        except Exception:
            pass  # proceed with brief even if ingest fails

    interview_id = f"int-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{company_name[:20].replace(' ', '-')}"

    try:
        # Data enrichment: Comprehend (NLP) + optional Kendra search
        combined_text = f"{company_name}. {extra_context}".strip()[:5000]
        nlp_insights = _enrich_with_comprehend(combined_text)
        kendra_snippets = _search_kendra(company_name, extra_context) if KENDRA_INDEX_ID else ""

        brief_text = _generate_brief_with_bedrock(
            company_name, extra_context, nlp_insights, kendra_snippets, uploaded_doc_text, insights_text
        )
        packet_text = _generate_packet_with_bedrock(company_name, brief_text)

        # Store in S3
        if BRIEFS_BUCKET:
            s3.put_object(
                Bucket=BRIEFS_BUCKET,
                Key=f"{interview_id}/brief.txt",
                Body=brief_text.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )
        if PACKETS_BUCKET:
            s3.put_object(
                Bucket=PACKETS_BUCKET,
                Key=f"{interview_id}/packet.txt",
                Body=packet_text.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )

        # Store metadata in DynamoDB
        if METADATA_TABLE:
            table = dynamodb.Table(METADATA_TABLE)
            table.put_item(
                Item={
                    "interview_id": interview_id,
                    "company_name": company_name,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "status": "completed",
                }
            )

        return _response(
            200,
            {
                "interview_id": interview_id,
                "company_name": company_name,
                "brief_preview": brief_text[:500] + "..." if len(brief_text) > 500 else brief_text,
                "message": "Brief and packet generated successfully.",
            },
        )
    except Exception as e:
        return _response(500, {"error": str(e)})


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


def _enrich_with_comprehend(text):
    """Extract entities and key phrases with Comprehend for evidence-based brief."""
    if not text or len(text.strip()) < 3:
        return ""
    try:
        entities = comprehend.detect_entities(Text=text[:5000], LanguageCode="en")
        key_phrases = comprehend.detect_key_phrases(Text=text[:5000], LanguageCode="en")
        entity_list = [e.get("Text", "") for e in entities.get("Entities", [])[:20] if e.get("Type") in ("ORGANIZATION", "LOCATION", "COMMERCIAL_ITEM", "TITLE")]
        phrases = [p.get("Text", "") for p in key_phrases.get("KeyPhrases", [])[:15]]
        parts = []
        if entity_list:
            parts.append("Entities: " + ", ".join(set(entity_list)))
        if phrases:
            parts.append("Key themes: " + ", ".join(phrases))
        return " | ".join(parts) if parts else ""
    except Exception:
        return ""


def _get_uploaded_document_text(document_key):
    """Read extracted text from cleaned/ for an uploaded document (key e.g. uploads/abc/file.pdf)."""
    if not SOURCE_BUCKET or not document_key or not document_key.startswith("uploads/"):
        return ""
    cleaned_key = document_key.replace("uploads/", "cleaned/uploads/", 1)
    if "." in cleaned_key:
        cleaned_key = cleaned_key.rsplit(".", 1)[0] + ".txt"
    else:
        cleaned_key = cleaned_key + ".txt"
    try:
        resp = s3.get_object(Bucket=SOURCE_BUCKET, Key=cleaned_key)
        text = resp["Body"].read().decode("utf-8", errors="replace").strip()
        return text[:12000] if text else ""  # cap for prompt size
    except Exception:
        return ""


def _search_kendra(company_name, extra_context):
    """Query Kendra index for public/proprietary snippets (e.g. Texas business)."""
    if not KENDRA_INDEX_ID or not kendra:
        return ""
    try:
        query = f"{company_name} {extra_context}".strip()[:200] or company_name
        resp = kendra.query(IndexId=KENDRA_INDEX_ID, QueryText=query, PageSize=5)
        snippets = []
        for r in resp.get("ResultItems", []):
            ex = r.get("DocumentExcerpt") or {}
            text = ex.get("Text") or ex.get("Excerpt") or ""
            if text and text.strip():
                snippets.append(text.strip())
        return "\n".join(snippets[:5]) if snippets else ""
    except Exception:
        return ""


# Amazon Nova model IDs (Bedrock). Try in order; first available wins.
# In AWS Console: Amazon Bedrock → Model access → Request access to Nova Lite/Micro/Pro.
BEDROCK_MODEL_IDS = [
    "amazon.nova-lite-v1:0",
    "amazon.nova-micro-v1:0",
    "amazon.nova-pro-v1:0",
]


def _invoke_bedrock(prompt, max_tokens=2048):
    """Invoke Amazon Nova via Bedrock Converse API. Raises on failure with a clear message."""
    last_error = None
    messages = [{"role": "user", "content": [{"text": prompt}]}]
    inference_config = {"maxTokens": max_tokens, "temperature": 0.3, "topP": 0.9}
    for model_id in BEDROCK_MODEL_IDS:
        try:
            response = bedrock.converse(
                modelId=model_id,
                messages=messages,
                inferenceConfig=inference_config,
            )
            content = response.get("output", {}).get("message", {}).get("content", [])
            text = (content[0].get("text", "") if content else "").strip()
            if text:
                return text
        except Exception as e:
            last_error = e
            continue
    hint = "In AWS Console: Amazon Bedrock → Model access → Request access to Amazon Nova Lite/Micro/Pro."
    raise RuntimeError(f"Bedrock unavailable. {hint} Last error: {last_error}") from last_error


def _format_insights(insights_raw):
    """Turn insights payload (list of strings or dicts) into a single string for the prompt."""
    if not insights_raw:
        return ""
    if isinstance(insights_raw, str):
        return insights_raw.strip()[:8000]
    if not isinstance(insights_raw, list):
        return str(insights_raw)[:8000]
    lines = []
    for i, item in enumerate(insights_raw[:100]):
        if isinstance(item, str):
            lines.append(item.strip())
        elif isinstance(item, dict):
            lines.append(json.dumps(item, default=str))
        else:
            lines.append(str(item))
    return "\n".join(lines).strip()[:8000]


def _generate_brief_with_bedrock(company_name, extra_context, nlp_insights="", kendra_snippets="", uploaded_doc_text="", insights_text=""):
    """Call Bedrock to generate interviewer brief with enriched context."""
    context_parts = []
    if extra_context:
        context_parts.append(f"Additional context: {extra_context}")
    if insights_text:
        context_parts.append(
            f"Company insights (key facts, recent news, products, leadership, culture, strategy—use these in the brief):\n{insights_text}"
        )
    if uploaded_doc_text:
        context_parts.append(
            f"Uploaded document content (primary source—use its specific facts, numbers, dates, and product names in the brief):\n{uploaded_doc_text}"
        )
    if nlp_insights:
        context_parts.append(f"NLP insights (entities and key themes): {nlp_insights}")
    if kendra_snippets:
        context_parts.append(f"Relevant search results (use to deepen context):\n{kendra_snippets}")
    context_block = "\n".join(context_parts) if context_parts else ""

    prompt = f"""Generate a 2-3 page Interviewer Brief for: {company_name}.
{context_block}

Include:
1. Company overview and market context—when uploaded document content is provided above, base the overview on it and cite specific details (e.g. founding year, location, product names, team size).
2. 8-10 well-crafted, open-ended, non-leading questions
3. Suggested conversation flow and follow-up stems (e.g. "Tell me more about...")
4. Key knowledge gaps for the interviewer to explore

Format as clear sections with headers."""
    return _invoke_bedrock(prompt, max_tokens=2048)


def _generate_packet_with_bedrock(company_name, brief_text):
    """Generate 1-page pre-interview packet for interviewee."""
    prompt = f"""Create a 1-page Pre-Interview Packet for the interviewee at: {company_name}.

Based on this interviewer brief summary:
{brief_text[:2000]}

Include:
1. "Here's what we learned about your organization" summary
2. "What did we get wrong?" - invite corrections
3. 5-6 foundational questions for them to review
4. Invitation: "Which of these questions interest you most?"
Keep it warm and concise."""
    return _invoke_bedrock(prompt, max_tokens=1024)


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
