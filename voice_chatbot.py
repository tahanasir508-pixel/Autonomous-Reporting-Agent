"""
voice_chatbot.py
Lets a business owner ask a question about their report BY VOICE, in
any language, and get a spoken answer back in that SAME language.

How it works:
  1. Gemini listens to the recorded question audio directly (no
     separate speech-to-text step needed) and answers using the
     report's data as context — it only ever sees pre-computed facts,
     the same principle as the written daily summary.
  2. Gemini tells us which language it answered in.
  3. gTTS (Google Text-to-Speech, free, no API key needed) converts
     that answer back to spoken audio, in the correct language.
"""

import io
import json
import os
import re

from google import genai
from google.genai import types
from gtts import gTTS

MODEL = "gemini-3.6-flash"

# The AI and the voice engine sometimes use different codes for the same
# language (e.g. the AI says "he" for Hebrew, the voice engine wants "iw").
_LANG_CODE_FIXES = {"he": "iw", "fil": "tl", "jv": "jw", "nb": "no", "nn": "no"}


def _normalize_lang_code(code: str) -> str:
    code = (code or "").strip()
    if code in ("zh-CN", "zh-TW", "pt-PT"):
        return code
    base = code.lower().split("-")[0].split("_")[0]   # "ur-PK" -> "ur"
    return _LANG_CODE_FIXES.get(base, base)


def _build_context(parsed_report: dict, open_anomalies: dict = None) -> str:
    lines = [
        f"Revenue: {parsed_report.get('revenue', 'N/A')}",
        f"Summary: {parsed_report.get('summary', '')}",
        f"Findings: {parsed_report.get('findings', '')}",
    ]
    if open_anomalies:
        lines.append("\nCurrently open issues (across all history, not just today):")
        for key, info in open_anomalies.items():
            lines.append(f"  - {key}: open {info['days_open']} day(s), since {info['first_seen']}")
    return "\n".join(lines)


def _parse_model_response(raw_text: str) -> dict:
    """Models sometimes wrap JSON in ```json fences despite instructions —
    strip that defensively before parsing."""
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def ask_voice_question(audio_bytes: bytes, parsed_report: dict, open_anomalies: dict = None):
    """Never raises — every failure returns a clear message instead."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"ok": False, "error": "GEMINI_API_KEY is not set.",
                "question_text": None, "answer_text": None, "answer_audio": None, "language_name": None}

    context = _build_context(parsed_report, open_anomalies)

    prompt = f"""You are a helpful business assistant answering a question about a sales report.
A business owner just asked a SPOKEN question, in the attached audio. It could be in ANY language.

Here is the report data you must base your answer on — do not invent numbers not present here:
{context}

Instructions:
1. Understand the spoken question, in whatever language it was asked.
2. Answer clearly and briefly (2-4 sentences), using ONLY the data above. If the data doesn't answer the question, say so honestly rather than guessing.
3. Reply in the EXACT SAME language the question was asked in.
4. Respond ONLY with a JSON object in this exact shape, with no other text before or after it:
{{"language_code": "<two-letter ISO 639-1 code, e.g. en, ur, es, fr, hi, ar>", "language_name": "<language name written in English, e.g. Urdu>", "question": "<a transcription of what the person asked, in their own language>", "answer": "<your answer, written in that detected language>"}}
"""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                prompt,
                types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
            ],
        )
    except Exception as e:
        return {"ok": False, "error": f"Could not process the question: {e}",
                "question_text": None, "answer_text": None, "answer_audio": None, "language_name": None}

    try:
        parsed = _parse_model_response(response.text)
        lang_code = parsed["language_code"]
        lang_name = parsed.get("language_name", lang_code)
        answer_text = parsed["answer"]
        question_text = parsed.get("question", "")
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        return {"ok": False, "error": f"Got an unexpected response format: {e}",
                "question_text": None, "answer_text": None, "answer_audio": None, "language_name": None}

    try:
        tts = gTTS(text=answer_text, lang=_normalize_lang_code(lang_code))
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        answer_audio_bytes = audio_buffer.read()
    except Exception as e:
        # Voice failing shouldn't lose the written answer — degrade gracefully.
        return {"ok": True, "error": f"Got a text answer, but voice playback failed: {e}",
                "question_text": question_text, "answer_text": answer_text, "answer_audio": None, "language_name": lang_name}

    return {"ok": True, "error": None, "question_text": question_text,
            "answer_text": answer_text, "answer_audio": answer_audio_bytes,
            "language_name": lang_name}