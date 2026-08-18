"""Escalation detector.

The benchmark's `escalated` flag is produced by the judge, after the
fact, from the reference answer. At serving time there is no reference
answer, so that flag does not exist and the workflow cannot route on it.

This module supplies the serving-time substitute: a pure function that
reads the generated answer and decides whether the assistant declined.

Three constraints shape it, and none is a preference:

1. **It does not touch generation.** `GENERATION_SYSTEM` and
   `GENERATION_PARAMS` are the constants held identical across the three
   benchmark runs. Asking the generator for a structured field would
   change them, and every published number would stop being
   reproducible. This function observes an output already produced; it
   cannot vary a result.

2. **It is tuned on `dense` artefacts only.** The `hybrid` and
   `hybrid_rerank` artefacts are the held-out evaluation set - see
   `docs/escalation-detector.md`. Fitting on all three and reporting
   agreement on all three would measure nothing.

3. **Ambiguity resolves to True.** An uncertain case escalates to a
   human. The failure that matters is serving a fabricated answer to a
   customer, not putting one answerable question in front of an agent.

Why not a substring match on prose like "sorry" or "I don't know": it
breaks the first time the model rephrases. The rules below do not match
politeness or refusal *of a request*; they match a statement that the
knowledge source does not hold the answer, which is the thing the
generation prompt actually instructs the model to say.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------
#
# One family of patterns, expressed four ways: the answer states that
# the *source* does not hold the answer.
#
# What is deliberately NOT matched, because the dense artefacts contain
# all of these inside answers the judge scored as answered:
#
#   - "Contact reception to book"        - a next step, not a refusal
#   - "We cannot extend a card"          - a negative fact about the spa
#   - "we do not admit anyone under 16"  - a negative fact about the spa
#   - "we cannot promise it"             - hedging a positive answer
#
# The distinction is the subject of the negation: the documents or the
# assistant's own knowledge, never the spa's policy.

_NEGATION = r"(?:do(?:es)?n't|do(?:es)? not|aren't|are not|isn't|is not)"

_PATTERNS = (
    # "the documents don't cover / contain / mention / specify ..."
    re.compile(
        rf"\bdocuments?\b[^.!?]{{0,80}}?\b{_NEGATION}\b[^.!?]{{0,40}}?"
        r"\b(?:cover|contain|mention|specify|include|have|say|state|address|provide|list)\b",
        re.IGNORECASE,
    ),
    # "... which aren't covered in these documents"
    re.compile(
        rf"\b{_NEGATION}\b[^.!?]{{0,40}}?\b(?:covered|mentioned|specified|included|addressed)\b"
        r"[^.!?]{0,30}?\bdocuments?\b",
        re.IGNORECASE,
    ),
    # "The documents provided only cover X. They don't mention Y."
    # The subject is a pronoun standing in for the documents, and it sits
    # in a later sentence, so the two patterns above cannot reach it.
    # Restricted to knowledge verbs: "they don't include VAT" is a fact
    # about a price, not a statement about the source.
    re.compile(
        rf"\bthey\b\s*{_NEGATION}\b[^.!?]{{0,20}}?"
        r"\b(?:cover|contain|mention|specify|say|state|address|list)\b",
        re.IGNORECASE,
    ),
    # "I don't have information / details / anything about ..."
    re.compile(
        rf"\bI\b[^.!?]{{0,20}}?\b{_NEGATION}\b[^.!?]{{0,20}}?"
        r"\b(?:information|details|anything|data)\b",
        re.IGNORECASE,
    ),
    # "I can't answer that", "I cannot tell you", "I'm not qualified to"
    re.compile(
        r"\bI(?:'m| am)? ?(?:can't|cannot|can not|am not able to|'m not qualified|am not qualified)\b"
        r"[^.!?]{0,30}?\b(?:answer|tell|say|advise|diagnose|help|qualified)\b",
        re.IGNORECASE,
    ),
)

# `generation.generate()` returns this marker when the API declines the
# request outright. It is not an answer, so it escalates.
_API_REFUSAL = "[refused by the API safety classifiers]"


def is_escalation(answer: str | None) -> bool:
    """True if the generated answer declines rather than answers.

    Pure: no I/O, no state, no model call. The same string always gives
    the same verdict, which is what makes it testable and what makes the
    measurement in `docs/escalation-detector.md` meaningful.
    """
    # Nothing to serve is not an answer. Ambiguity resolves to escalation.
    if not answer or not answer.strip():
        return True
    if _API_REFUSAL in answer:
        return True

    return any(pattern.search(answer) for pattern in _PATTERNS)
