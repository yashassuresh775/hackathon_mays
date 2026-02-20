"""
Document Processor Lambda.
Uses Textract to extract text from PDFs/images; optional Bedrock summarization.
"""
import json
import os
import boto3

TEXTRACT = boto3.client("textract")
S3 = boto3.client("s3")
SOURCE_BUCKET = os.environ.get("SOURCE_BUCKET", "")


def handler(event, context):
    """Process S3 upload or direct invoke with bucket/key. Returns extracted text."""
    # Support both S3 event and direct API invoke
    if "Records" in event and event["Records"]:
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
    else:
        body = _parse_body(event)
        bucket = body.get("bucket") or SOURCE_BUCKET
        key = body.get("key", "")

    if not bucket or not key:
        return _response(400, {"error": "bucket and key are required"})

    try:
        text = extract_text(bucket, key)
        return _response(200, {"bucket": bucket, "key": key, "extracted_text": text})
    except Exception as e:
        return _response(500, {"error": str(e)})


def extract_text(bucket, key):
    """Sync Textract detection for small docs; for large PDFs use StartDocumentAnalysis + job."""
    response = TEXTRACT.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    lines = [
        block["Text"]
        for block in response.get("Blocks", [])
        if block.get("BlockType") == "LINE"
    ]
    return "\n".join(lines)


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
