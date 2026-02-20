"""
Orchestrator Lambda.
API Gateway → Orchestrator → Data/Intelligence workers.
Routes: generate-brief, extract-document, upload-url, ingest-external, interview/{id}, packet-response, send-packet.
"""
import json
import os
import boto3

lambda_client = boto3.client("lambda")
BRIEF_GENERATOR = os.environ.get("BRIEF_GENERATOR_FUNCTION", "")
DOCUMENT_PROCESSOR = os.environ.get("DOCUMENT_PROCESSOR_FUNCTION", "")
UPLOAD_URL = os.environ.get("UPLOAD_URL_FUNCTION", "")
EXTERNAL_INGEST = os.environ.get("EXTERNAL_INGEST_FUNCTION", "")
GET_INTERVIEW = os.environ.get("GET_INTERVIEW_FUNCTION", "")
PACKET_RESPONSE = os.environ.get("PACKET_RESPONSE_FUNCTION", "")
SEND_PACKET = os.environ.get("SEND_PACKET_FUNCTION", "")


def handler(event, context):
    """Route request to the appropriate worker Lambda based on route key or path."""
    route_key = event.get("routeKey") or ""
    raw_path = (event.get("rawPath") or "").strip("/")
    method = (event.get("requestContext") or {}).get("http", {}).get("method", "") or event.get("httpMethod", "")

    if route_key == "POST /generate-brief" or raw_path == "generate-brief":
        return _invoke(BRIEF_GENERATOR, event, "Brief generator")
    if route_key == "POST /extract-document" or raw_path == "extract-document":
        return _invoke(DOCUMENT_PROCESSOR, event, "Document processor")
    if route_key == "POST /upload-url" or raw_path == "upload-url":
        return _invoke(UPLOAD_URL, event, "Upload URL")
    if route_key == "POST /ingest-external" or raw_path == "ingest-external":
        return _invoke(EXTERNAL_INGEST, event, "External ingest")
    if route_key == "POST /send-packet" or raw_path == "send-packet":
        return _invoke(SEND_PACKET, event, "Send packet")

    # GET /interview/{id} or GET /interview/xyz
    if raw_path.startswith("interview/") and method.upper() == "GET":
        return _invoke(GET_INTERVIEW, event, "Get interview")
    # POST /interview/{id}/packet-response
    if "interview/" in raw_path and "packet-response" in raw_path and method.upper() == "POST":
        return _invoke(PACKET_RESPONSE, event, "Packet response")

    return _response(404, {"error": "Not found", "route": route_key, "path": raw_path})


def _invoke(function_name, event, label):
    if not function_name:
        return _response(503, {"error": f"{label} function not configured"})
    try:
        payload = json.dumps(event) if isinstance(event, dict) else event
        resp = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=payload,
        )
        payload_out = resp["Payload"].read().decode("utf-8")
        result = json.loads(payload_out)

        # Worker Lambda threw an unhandled exception (FunctionError in response)
        if resp.get("FunctionError"):
            err_msg = result.get("errorMessage", "Worker Lambda failed")
            return _response(500, {"error": err_msg, "label": label})
        if "errorMessage" in result and "statusCode" not in result:
            return _response(500, {"error": result.get("errorMessage", "Worker failed"), "label": label})

        status = result.get("statusCode", 200)
        body = result.get("body", "{}")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                body = {"result": body}
        return _response(status, body if isinstance(body, dict) else {"result": body})
    except json.JSONDecodeError as e:
        return _response(500, {"error": f"Invalid response from worker: {e}", "label": label})
    except Exception as e:
        return _response(500, {"error": str(e), "label": label})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
