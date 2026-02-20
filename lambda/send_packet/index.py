"""
POST /send-packet: return shareable link for interviewee; optionally send email via SES.
"""
import json
import os
import boto3

METADATA_TABLE = os.environ.get("METADATA_TABLE", "")
BASE_URL = os.environ.get("PACKET_BASE_URL", "")  # e.g. https://yourapp.amplifyapp.com
SES_FROM = os.environ.get("SES_FROM_EMAIL", "")  # optional verified sender

dynamodb = boto3.resource("dynamodb")
ses = boto3.client("ses") if SES_FROM else None


def handler(event, context):
    body = _parse_body(event)
    interview_id = (body.get("interview_id") or "").strip()
    email = (body.get("email") or "").strip()

    if not interview_id:
        return _response(400, {"error": "interview_id required"})

    # Verify interview exists
    if METADATA_TABLE:
        try:
            table = dynamodb.Table(METADATA_TABLE)
            r = table.get_item(Key={"interview_id": interview_id})
            if not r.get("Item"):
                return _response(404, {"error": "Interview not found"})
        except Exception as e:
            return _response(500, {"error": str(e)})

    shareable_path = f"/packet/{interview_id}"
    shareable_link = f"{BASE_URL.rstrip('/')}{shareable_path}" if BASE_URL else shareable_path

    out = {"interview_id": interview_id, "shareable_link": shareable_link, "shareable_path": shareable_path}

    if email and SES_FROM and ses:
        try:
            ses.send_email(
                Source=SES_FROM,
                Destination={"ToAddresses": [email]},
                Message={
                    "Subject": {"Data": "Your Pre-Interview Packet — Interview AI"},
                    "Body": {
                        "Text": {
                            "Data": f"Please review your pre-interview packet and tell us what we got wrong or which questions interest you most.\n\nOpen: {shareable_link}"
                        }
                    },
                },
            )
            out["email_sent"] = True
        except Exception as e:
            out["email_sent"] = False
            out["email_error"] = str(e)

    return _response(200, out)


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
