"""
Document Processor Lambda.
Extracts text from uploads: TXT/CSV read from S3; PDFs (all pages) and images via Textract.
Writes extracted text to cleaned/ for Kendra and brief generation.
"""
import json
import os
import time
import boto3
from botocore.exceptions import ClientError

TEXTRACT = boto3.client("textract")
S3 = boto3.client("s3")
SOURCE_BUCKET = os.environ.get("SOURCE_BUCKET", "")

# Polling for async Textract job (multi-page PDF). Keep under ~28s so API Gateway (29s limit) doesn't time out.
JOB_POLL_INTERVAL = 2
JOB_POLL_MAX_WAIT = 26


def handler(event, context):
    """Process S3 upload or direct invoke with bucket/key. Extracts text, writes to cleaned/, returns text."""
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
        text, err = extract_text(bucket, key)
        if err:
            return _response(400, {"error": err})
        # Write to cleaned/ so Kendra indexes it and brief generator can use it immediately
        cleaned_key = _cleaned_key(key)
        if cleaned_key and SOURCE_BUCKET and text.strip():
            S3.put_object(
                Bucket=SOURCE_BUCKET,
                Key=cleaned_key,
                Body=text.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )
        return _response(200, {"bucket": bucket, "key": key, "cleaned_key": cleaned_key, "extracted_text": text})
    except Exception as e:
        return _response(500, {"error": str(e)})


def _cleaned_key(upload_key):
    """Map uploads/.../file.pdf -> cleaned/uploads/.../file.txt for Kendra and brief context."""
    if not upload_key or not upload_key.startswith("uploads/"):
        return None
    base = upload_key.replace("uploads/", "cleaned/uploads/", 1)
    # Replace extension with .txt (handle .pdf, .PDF, etc.)
    if "." in base:
        base = base.rsplit(".", 1)[0] + ".txt"
    else:
        base = base + ".txt"
    return base


# Textract: PDF (all pages via async), images (sync). TXT/CSV read from S3.
TEXTRACT_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif"}  # sync API, single page
TEXTRACT_PDF_EXTENSION = ".pdf"  # async API, all pages


def extract_text(bucket, key):
    """Extract text: TXT/CSV from S3; images via sync Textract; PDF via async Textract (all pages). Returns (text, error)."""
    ext = ("." + key.rsplit(".", 1)[-1].lower()) if "." in key else ""
    if ext in (".txt", ".csv"):
        resp = S3.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read().decode("utf-8", errors="replace").strip(), None
    if ext == TEXTRACT_PDF_EXTENSION:
        return _extract_pdf_text(bucket, key)
    if ext in TEXTRACT_IMAGE_EXTENSIONS:
        return _extract_image_text(bucket, key)
    return "", f"Unsupported file type '{ext}'. Supported: PDF (all pages), JPEG, PNG, TIFF, and TXT, CSV."


def _extract_image_text(bucket, key):
    """Single-page image: sync DetectDocumentText."""
    try:
        response = TEXTRACT.detect_document_text(
            Document={"S3Object": {"Bucket": bucket, "Name": key}}
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "UnsupportedDocumentException":
            return "", "Unsupported image. Use JPEG, PNG, or TIFF."
        raise
    lines = [b["Text"] for b in response.get("Blocks", []) if b.get("BlockType") == "LINE"]
    return "\n".join(lines), None


def _extract_pdf_text(bucket, key):
    """Try sync DetectDocumentText first (fast, single-page); if unsupported or too large, use async (all pages)."""
    # 1) Try sync API first — works for many single-page PDFs and returns in a few seconds
    try:
        response = TEXTRACT.detect_document_text(
            Document={"S3Object": {"Bucket": bucket, "Name": key}}
        )
        lines = [b["Text"] for b in response.get("Blocks", []) if b.get("BlockType") == "LINE"]
        if lines:
            return "\n".join(lines), None
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code == "UnsupportedDocumentException":
            return "", "Unsupported PDF format. Try re-saving as PDF from Word/Google Docs, or use a .txt file."
        if code == "InvalidParameterException":
            pass
        elif code == "DocumentTooLargeException":
            pass
        else:
            pass
    # 2) Fall back to async (multi-page or when sync not supported)
    try:
        start_resp = TEXTRACT.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "UnsupportedDocumentException":
            return "", "Unsupported PDF. Use a standard PDF (e.g. export from Word) or upload a .txt file."
        raise
    job_id = start_resp["JobId"]
    elapsed = 0
    while elapsed < JOB_POLL_MAX_WAIT:
        time.sleep(JOB_POLL_INTERVAL)
        elapsed += JOB_POLL_INTERVAL
        get_resp = TEXTRACT.get_document_text_detection(JobId=job_id)
        status = get_resp.get("JobStatus")
        if status == "SUCCEEDED":
            lines = _collect_line_blocks_from_detection(get_resp, job_id)
            return "\n".join(lines), None
        if status == "FAILED":
            return "", "Textract could not read this PDF. Try a .txt file or a different PDF (not password-protected)."
    return "", "PDF took too long to process (30s limit). Use a shorter PDF or a .txt file for instant parsing."


def _collect_line_blocks_from_detection(first_response, job_id):
    """Collect all LINE block texts from GetDocumentTextDetection, following NextToken."""
    lines = []
    response = first_response
    while True:
        for block in response.get("Blocks", []):
            if block.get("BlockType") == "LINE" and "Text" in block:
                lines.append(block["Text"])
        next_token = response.get("NextToken")
        if not next_token:
            break
        response = TEXTRACT.get_document_text_detection(JobId=job_id, NextToken=next_token)
    return lines


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
