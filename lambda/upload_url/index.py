"""
Generate presigned PUT URL for S3 uploads (document upload in frontend).
Key: uploads/{prefix}/{filename}
"""
import json
import os
import uuid
import boto3
from urllib.parse import unquote_plus

SOURCE_BUCKET = os.environ.get("SOURCE_BUCKET", "")
S3 = boto3.client("s3")
EXPIRES_IN = 3600  # 1 hour


def handler(event, context):
    body = _parse_body(event)
    filename = (body.get("filename") or "").strip() or "document.pdf"
    prefix = (body.get("prefix") or "").strip() or str(uuid.uuid4())[:8]
    # Sanitize filename: keep extension, safe base
    safe_name = "".join(c for c in filename if c.isalnum() or c in ".-_ ") or "upload"
    key = f"uploads/{prefix}/{safe_name}"

    if not SOURCE_BUCKET:
        return _response(503, {"error": "SOURCE_BUCKET not configured"})

    try:
        url = S3.generate_presigned_url(
            "put_object",
            Params={"Bucket": SOURCE_BUCKET, "Key": key, "ContentType": body.get("content_type") or "application/octet-stream"},
            ExpiresIn=EXPIRES_IN,
        )
        return _response(200, {"upload_url": url, "key": key, "bucket": SOURCE_BUCKET})
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


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body),
    }
