"""LLM-powered meeting summary generation using OpenAI."""
import logging
from typing import Optional
from dataclasses import dataclass

from openai import OpenAI

import config

logger = logging.getLogger(__name__)

# Lazy-loaded OpenAI client
_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Get or create the OpenAI client."""
    global _client
    if _client is None:
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


@dataclass
class MeetingSummary:
    """Structured meeting summary."""
    executive_summary: str
    action_items: list[dict]  # [{task, assignee}]
    key_decisions: list[str]
    topics_discussed: list[str]

    def to_dict(self) -> dict:
        return {
            "executive_summary": self.executive_summary,
            "action_items": self.action_items,
            "key_decisions": self.key_decisions,
            "topics_discussed": self.topics_discussed
        }


SUMMARY_SYSTEM_PROMPT = """You are a meeting notes assistant. Extract important information concisely, ordered by priority.

Analyze the transcript and provide:

1. **Executive Summary**: Covering the main purpose and key outcomes. adjust the length based on topics covered in the transcript.

2. **Action Items**: List tasks in order of importance (most critical first).
   Format as JSON array:
   [{"assignee": "Name","task": "concise description with key details"}]
   - Assignee = whoever volunteered, was asked to do it, or proposed it, it can be more than one person.
   - If a speaker says "I'll do X", assign to that speaker
   - Skip trivial tasks
   - If no action items, return []

3. **Key Decisions**: List decisions in order of impact (most significant first).
   Return as JSON array of concise strings (under 15 words each).
   Skip minor or procedural decisions.

4. **Topics Discussed**: List main topics as short phrases (2-4 words each).

IMPORTANT: Prioritize quality over quantity. Be concise.
IMPORTANT: Speaker names appear before the colon (e.g., "Shaun:"). Always use that exact spelling for names — never use phonetic variants from the transcript text.

Respond in JSON format:
{
  "executive_summary": "...",
  "action_items": [...],
  "key_decisions": [...],
  "topics_discussed": [...]
}"""


def format_transcript_for_llm(utterances: list) -> str:
    """Format utterances into a readable transcript for the LLM."""
    lines = []
    for utt in utterances:
        speaker = utt.get("speaker_name", utt.get("speaker", "Unknown"))
        text = utt.get("text", "")
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def generate_summary(utterances: list, language: str = "en") -> MeetingSummary:
    """Generate a meeting summary from utterances.

    Args:
        utterances: List of utterance dicts with speaker_name and text
        language: Language code (for future multi-language support)

    Returns:
        MeetingSummary object with structured summary data
    """
    client = get_openai_client()

    # Format transcript
    transcript = format_transcript_for_llm(utterances)

    if not transcript.strip():
        raise ValueError("No transcript content to summarize")

    # Truncate if too long (GPT-5.2 has 400K context, but let's be reasonable)
    max_chars = 50000  # ~12K tokens
    if len(transcript) > max_chars:
        original_length = len(transcript)
        transcript = transcript[:max_chars] + "\n\n[Transcript truncated due to length...]"
        logger.warning(f"Transcript truncated from {original_length} to {max_chars} chars")

    logger.info(f"Generating summary for transcript ({len(transcript)} chars)")

    try:
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Please summarize this meeting transcript:\n\n{transcript}"}
            ],
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content
        logger.info(f"LLM response received ({len(result_text)} chars)")

        # Parse JSON response
        import json
        result = json.loads(result_text)

        summary = MeetingSummary(
            executive_summary=result.get("executive_summary", ""),
            action_items=result.get("action_items", []),
            key_decisions=result.get("key_decisions", []),
            topics_discussed=result.get("topics_discussed", [])
        )

        logger.info(f"Summary generated: {len(summary.action_items)} action items, "
                    f"{len(summary.key_decisions)} decisions")

        return summary

    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        raise
