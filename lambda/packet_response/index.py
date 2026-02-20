"""
POST /interview/{id}/packet-response: save interviewee corrections and selected 2-3 question IDs.
"""
import json
import os
import boto3

METADATA_TABLE = os.environ.get("METADATA_TABLE", "")
dynamodb = boto3.resource("dynamodb")


def handler(event, context):
    path_params = event.get("pathParameters") or {}
    interview_id = (path_params.get("id") or "").strip()
    if not interview_id:
        return _response(400, {"error": "interview_id required"})

    body = _parse_body(event)
    corrections = body.get("corrections", "")
    selected_question_ids = body.get("selected_question_ids", [])
    if not isinstance(selected_question_ids, list):
        selected_question_ids = []

    if not METADATA_TABLE:
        return _response(503, {"error": "METADATA_TABLE not configured"})

    try:
        table = dynamodb.Table(METADATA_TABLE)
        table.update_item(
            Key={"interview_id": interview_id},
            UpdateExpression="SET packet_response_corrections = :c, packet_response_selected_ids = :s, packet_response_at = :t",
            ExpressionAttributeValues={
                ":c": (corrections or "")[:4000],
                ":s": selected_question_ids[:10],
                ":t": _now_iso(),
            },
            ConditionExpression="attribute_exists(interview_id)",
        )
        return _response(200, {"message": "Packet response saved.", "interview_id": interview_id})
    except Exception as e:
        if getattr(e, "response", {}).get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return _response(404, {"error": "Interview not found"})
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


def _now_iso():
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body),
    }
