from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests
from cryptography.fernet import Fernet, InvalidToken


TIMEOUT_SECONDS = 15


class NotifyError(RuntimeError):
    pass


def env_required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise NotifyError(f"{name} is not set")
    return value


def decrypt_payload(ciphertext: str) -> dict[str, Any]:
    try:
        fernet = Fernet(env_required("PAYLOAD_ENCRYPTION_KEY").encode("utf-8"))
        raw = fernet.decrypt(ciphertext.encode("utf-8"))
    except (ValueError, InvalidToken) as exc:
        raise NotifyError("Failed to decrypt payload") from exc
    return json.loads(raw.decode("utf-8"))


def load_event_payload() -> dict[str, Any]:
    event_path = env_required("GITHUB_EVENT_PATH")
    with open(event_path, encoding="utf-8") as f:
        event = json.load(f)

    client_payload = event.get("client_payload", {})
    if client_payload.get("encrypted") is not True or not isinstance(client_payload.get("ciphertext"), str):
        raise NotifyError("repository_dispatch payload is invalid")
    return decrypt_payload(client_payload["ciphertext"])


def source_name(target: dict[str, Any]) -> str:
    return str(target.get("source_label") or target.get("source_id", ""))


def render_summary(targets: list[dict[str, Any]]) -> list[str]:
    lines = ["=== Summary ===", ""]
    for target in targets:
        counts = target.get("counts", {})
        lines.extend(
            [
                source_name(target),
                f"  added: {counts.get('added', 0)}",
                f"  changed: {counts.get('changed', 0)}",
                f"  removed: {counts.get('removed', 0)}",
                f"  included: {target.get('included_count', 0)} / {target.get('total_count', 0)}",
                "",
            ]
        )
    lines.append("=================")
    return lines


def render_email(payload: dict[str, Any]) -> tuple[str, str]:
    targets = payload.get("targets", [])
    target_count = len(targets)
    subject = f"Monitor update for {target_count} target(s)"
    lines = [*render_summary(targets), "", "=== Details ===", "", "A monitored source changed.", "", f"Event ID: {payload.get('event_id', '')}"]

    detected_at = payload.get("detected_at")
    if detected_at:
        lines.append(f"Detected at: {detected_at}")

    for target in targets:
        lines.extend(
            [
                "",
                f"Source: {source_name(target)}",
                f"Mode: {target.get('mode', '')}",
                f"Counts: {json.dumps(target.get('counts', {}), sort_keys=True)}",
                f"Included: {target.get('included_count', 0)} / {target.get('total_count', 0)}",
            ]
        )
        if target.get("truncated"):
            lines.append("Some item details were omitted because the notification was truncated.")
        for index, item in enumerate(target.get("items", []), start=1):
            lines.append("")
            lines.append(f"Item {index}:")
            for key in ("change", "title", "spec", "price", "url"):
                if item.get(key):
                    lines.append(f"- {key}: {item[key]}")

    return subject, "\n".join(lines).strip() + "\n"


def send_email(subject: str, text: str, event_id: str) -> None:
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {env_required('MAIL_API_KEY')}",
            "Content-Type": "application/json",
            "Idempotency-Key": event_id,
        },
        json={
            "from": env_required("MAIL_FROM"),
            "to": [env_required("MAIL_TO")],
            "subject": subject,
            "text": text,
        },
        timeout=TIMEOUT_SECONDS,
    )
    try:
        response.raise_for_status()
    except requests.RequestException:
        raise NotifyError(f"Failed to send email: status={response.status_code}") from None


def main() -> None:
    payload = load_event_payload()
    event_id = str(payload.get("event_id") or "")
    if not event_id:
        raise NotifyError("Payload missing event_id")

    subject, text = render_email(payload)
    send_email(subject, text, event_id)
    print("Notification sent")


if __name__ == "__main__":
    try:
        main()
    except NotifyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
