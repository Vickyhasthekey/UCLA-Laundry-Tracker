"""Member C integration fixture, not Member B's status/undo implementation."""
import base64
import hashlib
import hmac
import json
import os
import uuid
import time
from decimal import Decimal
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

db = boto3.resource("dynamodb")
secrets = boto3.client("secretsmanager")
secret = None
ISSUES = {"WONT_START", "NOT_DRYING", "LEAKING", "OTHER"}


def response(code, data):
    return {"statusCode": code, "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"}, "body": json.dumps(data, default=lambda value: int(value) if isinstance(value, Decimal) else str(value))}


def fingerprint(value):
    global secret
    if secret is None:
        secret = secrets.get_secret_value(SecretId=os.environ["DEVICE_HASH_SECRET_ARN"])["SecretString"].encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def transaction(item, device_hash, ip_hash, now):
    """Atomic sliding machine cooldown + UTC day counters + report save.

    TTL is cleanup only. Conditions enforce expiry even before DynamoDB removes it.
    Raw device IDs and IPs are never stored.
    """
    table = os.environ["RATE_LIMIT_TABLE"]
    day = now // 86400
    expiry = (day + 1) * 86400
    writes = [{"Put": {"TableName": table,
        "Item": {"bucketKey": f"machine:{device_hash}:{item['machineId']}", "expiresAt": now + 180},
        "ConditionExpression": "attribute_not_exists(bucketKey) OR expiresAt <= :now",
        "ExpressionAttributeValues": {":now": now}}}]
    for kind, identity, maximum in [("device", device_hash, 30), ("ip", ip_hash, 300)]:
        writes.append({"Update": {"TableName": table,
            "Key": {"bucketKey": f"{kind}:{identity}:{day}"},
            "UpdateExpression": "SET expiresAt = :expiry ADD #count :one",
            "ConditionExpression": "attribute_not_exists(#count) OR #count < :maximum",
            "ExpressionAttributeNames": {"#count": "count"},
            "ExpressionAttributeValues": {":expiry": expiry, ":one": 1, ":maximum": maximum}}})
    writes.append({"Put": {"TableName": os.environ["REPORTS_TABLE"], "Item": item}})
    db.meta.client.transact_write_items(TransactItems=writes, ClientRequestToken=item["reportId"])


def public_report(item):
    return {k: v for k, v in item.items() if k not in {"deviceHash", "reportKey"}}


def handler(event, context):
    route = event.get("routeKey", "")
    params = event.get("pathParameters") or {}
    if route == "GET /health":
        return response(200, {"status": "ok", "dataMode": "demo", "implementation": "member-c-infrastructure-fixture"})
    rooms = db.Table(os.environ["ROOMS_TABLE"])
    machines = db.Table(os.environ["MACHINES_TABLE"])
    reports = db.Table(os.environ["REPORTS_TABLE"])
    if route == "GET /rooms":
        # Small seeded directory. Add pagination before expanding campus-wide.
        return response(200, {"items": rooms.scan().get("Items", [])})
    if route == "GET /rooms/{roomId}/machines":
        return response(200, {"items": machines.query(KeyConditionExpression=Key("roomId").eq(params["roomId"]), ConsistentRead=True).get("Items", [])})
    if route not in {"GET /machines/{machineId}/reports", "POST /machines/{machineId}/reports"}:
        return response(404, {"error": "Route not found"})
    machine_id = params["machineId"]
    room_id, separator, label = machine_id.partition(":")
    if not separator or not label or not machines.get_item(Key={"roomId": room_id, "machineId": machine_id}, ConsistentRead=True).get("Item"):
        return response(404, {"error": "Unknown machine"})
    if route.startswith("GET"):
        try:
            limit = int((event.get("queryStringParameters") or {}).get("limit", "20"))
            if not 1 <= limit <= 100:
                raise ValueError()
        except (TypeError, ValueError):
            return response(400, {"error": "limit must be between 1 and 100"})
        result = reports.query(KeyConditionExpression=Key("machineId").eq(machine_id), ScanIndexForward=False, Limit=limit, ConsistentRead=True)
        return response(200, {"items": [public_report(item) for item in result.get("Items", [])]})
    try:
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode()
        if len(raw) > 2048:
            raise ValueError()
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise ValueError()
        issue = body.get("issueType")
        if set(body) - {"issueType", "website"} or body.get("website") or not isinstance(issue, str) or issue not in ISSUES:
            raise ValueError()
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        device_id = headers.get("x-device-id", "")
        uuid.UUID(device_id)
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return response(400, {"error": "Use a fixed issueType, no free text, and X-Device-Id UUID"})
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    report_id = str(uuid.uuid4())
    device_hash = fingerprint("device:" + str(uuid.UUID(device_id)))
    ip = event.get("requestContext", {}).get("http", {}).get("sourceIp")
    if not ip:
        return response(400, {"error": "Missing gateway source IP"})
    item = {"machineId": machine_id, "reportKey": f"{now}#{report_id}", "reportId": report_id, "createdAt": now, "issueType": issue, "source": "demo", "dataMode": "demo", "deviceHash": device_hash}
    try:
        transaction(item, device_hash, fingerprint("ip:" + ip), int(time.time()))
    except db.meta.client.exceptions.TransactionCanceledException as error:
        reasons = error.response.get("CancellationReasons", [])
        if any(reason.get("Code") == "ConditionalCheckFailed" for reason in reasons[:3]):
            return response(429, {"error": "Report limit reached. Wait 3 minutes for this machine; daily limits also apply."})
        raise
    return response(201, public_report(item))
