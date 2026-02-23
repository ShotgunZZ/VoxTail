"""Slack integration via Incoming Webhook."""
import json
import logging
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import config

logger = logging.getLogger(__name__)


def format_slack_blocks(summary: dict, audio_duration: float, created_at: float) -> list:
    """Build Slack Block Kit payload from meeting summary."""
    meeting_time = datetime.fromtimestamp(created_at).strftime("%B %d, %Y at %I:%M %p")
    duration_min = int(audio_duration // 60)
    duration_sec = int(audio_duration % 60)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":memo: Meeting Summary", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f":calendar: {meeting_time}  |  :stopwatch: {duration_min}m {duration_sec}s"}
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Executive Summary*\n{summary['executive_summary']}"}
        },
    ]

    # Action items
    if summary.get("action_items"):
        items_text = "\n".join(
            f"\u2022 {item['task']}" + (f" \u2014 _{item['assignee']}_" if item.get("assignee") else "")
            for item in summary["action_items"]
        )
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Action Items*\n{items_text}"}
        })

    # Key decisions
    if summary.get("key_decisions"):
        decisions_text = "\n".join(f"\u2022 {d}" for d in summary["key_decisions"])
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Key Decisions*\n{decisions_text}"}
        })

    # Topics as a compact context line
    if summary.get("topics_discussed"):
        topics_text = ", ".join(summary["topics_discussed"])
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f":speech_balloon: *Topics:* {topics_text}"}]
        })

    return blocks


def send_to_slack(summary: dict, audio_duration: float, created_at: float) -> dict:
    """Post meeting summary to Slack via webhook."""
    webhook_url = config.SLACK_WEBHOOK_URL
    if not webhook_url:
        raise ValueError("Slack webhook URL not configured")

    blocks = format_slack_blocks(summary, audio_duration, created_at)

    # Fallback text for notifications
    fallback = f"Meeting Summary: {summary['executive_summary'][:150]}..."

    payload = json.dumps({"text": fallback, "blocks": blocks}).encode("utf-8")
    req = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})

    try:
        with urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            logger.info("Slack webhook response: %s %s", resp.status, body)
            return {"success": True}
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        logger.error("Slack webhook HTTP error: %s %s", e.code, error_body)
        raise RuntimeError(f"Slack returned {e.code}: {error_body}")
    except URLError as e:
        logger.error("Slack webhook URL error: %s", e.reason)
        raise RuntimeError(f"Could not reach Slack: {e.reason}")
