"""
GET /interview/{id}: return brief, packet, and packet_response (corrections + selected questions) for interviewer or interviewee view.
"""
import json
import os
import boto3

BRIEFS_BUCKET = os.environ.get("BRIEFS_BUCKET", "")
PACKETS_BUCKET = os.environ.get("PACKETS_BUCKET", "")
METADATA_TABLE = os.environ.get("METADATA_TABLE", "")

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    interview_id = (path_params.get("id") or "").strip()
    if not interview_id:
        return _response(400, {"error": "interview_id required"})

    try:
        meta = _get_metadata(interview_id)
        if not meta:
            return _response(404, {"error": "Interview not found"})

        brief_text = _get_s3_text(BRIEFS_BUCKET, f"{interview_id}/brief.txt")
        packet_text = _get_s3_text(PACKETS_BUCKET, f"{interview_id}/packet.txt")

        out = {
            "interview_id": interview_id,
            "company_name": meta.get("company_name", ""),
            "created_at": meta.get("created_at", ""),
            "status": meta.get("status", ""),
            "brief_text": brief_text or "",
            "packet_text": packet_text or "",
            "packet_response": {
                "corrections": meta.get("packet_response_corrections", "") or "",
                "selected_question_ids": meta.get("packet_response_selected_ids", []) or [],
            }
            if meta.get("packet_response_corrections") or meta.get("packet_response_selected_ids")
            else None,
        }
        return _response(200, out)
    except Exception as e:
        return _response(500, {"error": str(e)})


def _get_metadata(interview_id):
    if not METADATA_TABLE:
        return None
    table = dynamodb.Table(METADATA_TABLE)
    r = table.get_item(Key={"interview_id": interview_id})
    return r.get("Item")


def _get_s3_text(bucket, key):
    if not bucket:
        return ""
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read().decode("utf-8")
    except Exception:
        return ""


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body),
    }
