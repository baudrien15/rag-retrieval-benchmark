"""Answer generation and LLM judging.

Both prompts are module constants and neither takes a parameter that
varies between configurations. That is the point: retrieved documents
are the only thing that differs across the three runs, so anything else
living here would be a second variable.

Two API constraints shape this file, and neither is a preference:

1. **Claude Opus 5 rejects `temperature`.** The parameter was removed on
   Opus 4.7 and later; sending it returns a 400. CLAUDE.md specifies
   "judge, temperature 0" and that is simply not expressible. The
   closest available substitute is used instead — see JUDGE_PARAMS.
2. **Claude Opus 5 can decline a request**, returning HTTP 200 with
   `stop_reason == "refusal"` and an empty or partial `content`. Reading
   `content[0]` without checking would crash on it.

The generator, Claude Haiku 4.5, still accepts `temperature`, so it runs
at 0 exactly as specified.
"""

from __future__ import annotations

import json
from functools import lru_cache

import anthropic

from config import GENERATION_MODEL, JUDGE_MODEL

# ---------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------

GENERATION_SYSTEM = """\
You are the assistant for Lumen Spa & Wellness, answering customer \
questions from the reference documents supplied with each question.

Answer only from those documents. They are the only source you have; \
you have no other knowledge of this business, and anything you recall \
about spas in general does not apply to this one.

If the documents do not contain the answer, say so plainly and refer \
the customer to reception. Do not guess, do not reason from what would \
be typical for a spa, and do not offer a partial answer built from a \
document that is merely related. A question the documents do not cover \
is not a failure to be papered over — saying you do not know is the \
correct answer.

Be brief. Give the answer, not a preamble. Quote exact figures — prices, \
durations, notice periods — exactly as they appear."""

GENERATION_PARAMS = {
    "model": GENERATION_MODEL,
    "max_tokens": 512,
    "temperature": 0,
}


def _documents_block(hits) -> str:
    if not hits:
        return "(no documents were retrieved)"
    return "\n\n".join(
        f"<document id=\"{hit.doc_id}\">\n{hit.text}\n</document>" for hit in hits
    )


@lru_cache(maxsize=1)
def _client() -> anthropic.Anthropic:
    # The SDK retries 429 and 5xx with exponential backoff. Raised from
    # the default 2 because a run is 90 calls and restarting the whole
    # thing over one transient 529 is worse than waiting.
    return anthropic.Anthropic(max_retries=5)


def generate(question: str, hits) -> str:
    """Answer one question from the retrieved documents."""
    response = _client().messages.create(
        **GENERATION_PARAMS,
        system=GENERATION_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Reference documents:\n\n{_documents_block(hits)}\n\n"
                    f"Customer question: {question}"
                ),
            }
        ],
    )
    if response.stop_reason == "refusal":
        return "[refused by the API safety classifiers]"
    return "".join(block.text for block in response.content if block.type == "text")


# ---------------------------------------------------------------------
# Judging
# ---------------------------------------------------------------------

JUDGE_SYSTEM = """\
You grade a customer-support assistant's answers. You are strict, \
consistent, and you explain yourself in one sentence.

You will be given the customer's question, the reference answer, and the \
assistant's answer. Decide whether the assistant's answer is correct.

Correct means: it states the substance of the reference answer, and \
every figure it gives — price, duration, notice period, minimum, age — \
matches the reference. Wording may differ freely. Extra correct detail \
is fine. A missing figure that the question explicitly asked for is not.

Incorrect means: it contradicts the reference, invents a figure, omits \
something the question directly asked for, or declines to answer a \
question the reference does answer.

Where the reference answer is absent, the question is one the corpus \
does not cover. There the assistant is correct only if it declines and \
points the customer elsewhere. An assistant that supplies an answer \
anyway is incorrect, however plausible the answer sounds — that is the \
fabrication this benchmark exists to count."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "correct": {
            "type": "boolean",
            "description": "True if the assistant's answer is correct.",
        },
        "escalated": {
            "type": "boolean",
            "description": (
                "True if the assistant declined to answer and referred the "
                "customer onwards, rather than supplying an answer."
            ),
        },
        "reason": {
            "type": "string",
            "description": "One sentence explaining the verdict.",
        },
    },
    "required": ["correct", "escalated", "reason"],
    "additionalProperties": False,
}

# `temperature` is rejected on Claude Opus 5 (400). Thinking is on by
# default there and adds run-to-run variance, so it is disabled - which
# the API permits only at effort "high" or below, hence the pairing.
# Together these are the nearest thing the model offers to the
# "temperature 0" CLAUDE.md asks for. The verdict is also schema-
# constrained, which removes format drift as a source of variance.
JUDGE_PARAMS = {
    "model": JUDGE_MODEL,
    "max_tokens": 1024,
    "thinking": {"type": "disabled"},
    "output_config": {
        "effort": "low",
        "format": {"type": "json_schema", "schema": JUDGE_SCHEMA},
    },
}


def judge(question: str, expected_answer: str | None, answer: str) -> dict:
    """Grade one answer. Returns the parsed verdict dict."""
    reference = expected_answer or (
        "(none - the corpus does not cover this question; the assistant "
        "should decline and refer the customer to reception)"
    )
    response = _client().messages.create(
        **JUDGE_PARAMS,
        system=JUDGE_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Reference answer: {reference}\n\n"
                    f"Assistant's answer: {answer}"
                ),
            }
        ],
    )

    if response.stop_reason == "refusal":
        return {
            "correct": False,
            "escalated": False,
            "reason": "judge refused to grade (API safety classifiers)",
            "judge_refused": True,
        }

    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)
