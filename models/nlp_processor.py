"""
models/nlp_processor.py
NLP Processing Pipeline:
  1. Summarization      — T5-based abstractive summarization
  2. Task Extraction    — Keyword + pattern-based action item detection
  3. Deadline Detection — Rule-based temporal expression extraction
"""

import re
import json
import logging
from typing import Optional
import os
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# ── Lazy-load heavy models ────────────────────────────────────────────────────
_summarizer = None


def _get_summarizer():
    """Load the T5 summarization pipeline (cached after first load)."""
    global _summarizer
    if _summarizer is None:
        try:
            from transformers import pipeline
            logger.info("[NLP] Loading T5 summarization model...")
            # Using facebook/bart-large-cnn as it outperforms t5-small on summarization
            # and is well-supported; falls back to t5-base if preferred
            _summarizer = pipeline(
                "summarization",
                model="sshleifer/distilbart-cnn-12-6",  # Fast, good quality
                tokenizer="sshleifer/distilbart-cnn-12-6",
                device=-1  # CPU; change to 0 for GPU
            )
            logger.info("[NLP] Summarization model loaded.")
        except Exception as e:
            logger.warning(f"[NLP] Could not load transformer model: {e}. Using extractive fallback.")
            _summarizer = "extractive"
    return _summarizer


# ─────────────────────────────────────────────────────────────────────────────
# 1. SUMMARIZATION
# ─────────────────────────────────────────────────────────────────────────────

def _extractive_summary(text: str, max_sentences: int = 5) -> str:
    """
    Simple extractive summarization fallback:
    Score sentences by word frequency and pick top N.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) <= max_sentences:
        return text

    # Word frequency scoring
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    def score(sentence):
        ws = re.findall(r'\b[a-z]{3,}\b', sentence.lower())
        return sum(freq.get(w, 0) for w in ws) / max(len(ws), 1)

    ranked = sorted(sentences, key=score, reverse=True)[:max_sentences]
    # Preserve original order
    top = set(ranked)
    ordered = [s for s in sentences if s in top]
    return ' '.join(ordered)


def summarize(transcript: str, max_length: int = 400, min_length: int = 100) -> str:
    from groq import Groq
    
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are an expert meeting summarizer. Create a clear structured "
                           "summary covering: key discussion points, decisions made, and next steps."
            },
            {
                "role": "user",
                "content": f"Summarize this meeting transcript:\n\n{transcript[:6000]}"
            }
        ],
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

# ─────────────────────────────────────────────────────────────────────────────
# 2. TASK EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

# Keywords that signal an action item
TASK_PATTERNS = [
    r'\b(will|should|must|need to|needs to|have to|has to|going to|plan to|'
    r'responsible for|assigned to|take care of|make sure|ensure|follow up|'
    r'schedule|prepare|send|review|update|complete|finish|deliver|'
    r'create|build|implement|fix|resolve|check|confirm|coordinate|'
    r'arrange|organize|set up|reach out|contact|notify|inform|'
    r'submit|approve|sign off|verify|test|deploy)\b',
]

TASK_NEGATIVE = re.compile(
    r'\b(was|were|had|has been|have been|did|already|done|completed|finished)\b',
    re.IGNORECASE
)

# Compiled combined pattern
TASK_REGEX = re.compile('|'.join(TASK_PATTERNS), re.IGNORECASE)

# Minimum meaningful task length
MIN_TASK_LENGTH = 15


def extract_tasks(transcript: str) -> list[str]:
    """
    Extract action items / tasks from transcript.
    Uses keyword matching + basic NLP filtering.

    Returns:
        List of task strings (deduplicated, cleaned)
    """
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+|\n', transcript)

    tasks = []
    seen = set()

    for sent in sentences:
        sent = sent.strip()
        if len(sent) < MIN_TASK_LENGTH:
            continue

        # Check for task-indicating keywords
        if not TASK_REGEX.search(sent):
            continue

        # Skip past-tense sentences (already done)
        if TASK_NEGATIVE.search(sent):
            # Only skip if negative matches at the start
            first_match = TASK_NEGATIVE.search(sent)
            if first_match and first_match.start() < 10:
                continue

        # Normalize whitespace
        clean = re.sub(r'\s+', ' ', sent).strip()

        # Deduplicate (case-insensitive)
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            tasks.append(clean)

    logger.info(f"[NLP] Extracted {len(tasks)} tasks.")
    return tasks


# ─────────────────────────────────────────────────────────────────────────────
# 3. DEADLINE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

# Temporal expression patterns
DEADLINE_PATTERNS = [
    # Relative expressions
    r'\b(today|tonight|this morning|this afternoon|this evening)\b',
    r'\b(tomorrow|the day after tomorrow)\b',
    r'\b(this week|next week|end of week|end of this week|eow)\b',
    r'\b(this month|next month|end of month|eom)\b',
    r'\b(this (monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
    r'\b(next (monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
    r'\b(in \d+ (minutes?|hours?|days?|weeks?|months?))\b',
    r'\b(within \d+ (minutes?|hours?|days?|weeks?|months?))\b',
    r'\b(by (monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
    r'\b(by end of (day|week|month|the week|the month|today|tomorrow))\b',
    r'\b(before the next meeting|next meeting|next session|next call)\b',
    r'\b(before (monday|tuesday|wednesday|thursday|friday|end of))\b',
    # Absolute date-like patterns
    r'\b\d{1,2}[\/\-]\d{1,2}([\/\-]\d{2,4})?\b',
    r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(st|nd|rd|th)?\b',
    r'\b\d{1,2}(st|nd|rd|th)?\s+of\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b',
    r'\b(q[1-4]|first quarter|second quarter|third quarter|fourth quarter)\b',
    # Sprint/Deadline jargon
    r'\b(asap|as soon as possible|immediately|urgent|urgently)\b',
    r'\b(deadline is|due date is|due by|due on|must be done by|complete by)\b',
]

DEADLINE_REGEX = re.compile('|'.join(DEADLINE_PATTERNS), re.IGNORECASE)


def extract_deadlines(transcript: str) -> list[dict]:
    """
    Detect deadline/time expressions from transcript.
    Returns structured list of {sentence, expression} dicts.
    """
    sentences = re.split(r'(?<=[.!?])\s+|\n', transcript)
    deadlines = []
    seen_sents = set()

    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 10:
            continue

        matches = DEADLINE_REGEX.findall(sent)
        if not matches:
            continue

        # Flatten tuple matches from alternation groups
        expressions = []
        for m in matches:
            if isinstance(m, tuple):
                expr = next((x for x in m if x), None)
            else:
                expr = m
            if expr:
                expressions.append(expr.strip())

        if not expressions:
            continue

        clean_sent = re.sub(r'\s+', ' ', sent).strip()
        key = clean_sent.lower()

        if key not in seen_sents:
            seen_sents.add(key)
            deadlines.append({
                "sentence": clean_sent,
                "expressions": list(set(expressions))
            })

    logger.info(f"[NLP] Detected {len(deadlines)} deadline sentences.")
    return deadlines


# ─────────────────────────────────────────────────────────────────────────────
# 4. FULL PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def process_transcript(transcript: str) -> dict:
    """
    Run the full NLP pipeline on a transcript.
    Returns dict with summary, tasks (JSON), deadlines (JSON).
    """
    logger.info("[NLP] Starting NLP processing pipeline...")

    summary = summarize(transcript)
    tasks = extract_tasks(transcript)
    deadlines = extract_deadlines(transcript)

    return {
        "summary": summary,
        "tasks": json.dumps(tasks, ensure_ascii=False),
        "deadlines": json.dumps(deadlines, ensure_ascii=False),
    }
