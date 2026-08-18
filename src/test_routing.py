"""End-to-end check of the two workflow branches.

The n8n canvas has exactly one decision in it, and this is the test of
that decision: an in-scope question must route to the answer branch, an
out-of-scope question must route to the escalation branch.

It goes through `service.answer` rather than through the detector alone,
because the branch depends on retrieval, generation and detection all
holding together — testing the regex in isolation would pass while the
demo routed everything to a human.

    python src/test_routing.py

Needs Qdrant up, the collection ingested, and ANTHROPIC_API_KEY set. It
makes two generation calls. Exit code 0 means both branches are right.

The two questions are q01 and q25 from the frozen test set. They are not
re-annotated here: their `expected_behavior` in `data/testset.json` is
the source, and this file only asserts that the service agrees with it.
"""

from __future__ import annotations

import sys

import service
from fastapi import HTTPException

SECRET = "test-shared-secret"

IN_SCOPE = "How much is the hot stone massage?"      # q01, exact_term
OUT_OF_SCOPE = "Do you offer laser hair removal?"    # q25, out_of_scope


def check(label: str, condition: bool, detail: str) -> bool:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        print(f"        {detail}")
    return condition


def main() -> int:
    # The service reads its secret at import time. Set it here so the
    # test does not depend on a configured .env, and so the rejection
    # case below is exercised against a secret that really is set.
    service.SHARED_SECRET = SECRET

    results = []

    print("\nBranch 1 - in-scope question must route to the answer branch")
    served = service.answer(
        service.AskRequest(question=IN_SCOPE, conversation_id="test-in-scope"),
        x_lumen_secret=SECRET,
    )
    results.append(check(
        "escalated is False",
        served["escalated"] is False,
        f"got escalated={served['escalated']!r} for {IN_SCOPE!r}\n"
        f"        answer: {served['answer'][:300]!r}",
    ))
    results.append(check(
        "an answer was produced",
        bool(served["answer"].strip()),
        "the answer was empty",
    ))
    print(f"        retrieved: {[h['doc_id'] for h in served['retrieved']]}")

    print("\nBranch 2 - out-of-scope question must route to the escalation branch")
    escalated = service.answer(
        service.AskRequest(question=OUT_OF_SCOPE, conversation_id="test-oos"),
        x_lumen_secret=SECRET,
    )
    results.append(check(
        "escalated is True",
        escalated["escalated"] is True,
        f"got escalated={escalated['escalated']!r} for {OUT_OF_SCOPE!r}\n"
        f"        answer: {escalated['answer'][:300]!r}",
    ))
    print(f"        retrieved: {[h['doc_id'] for h in escalated['retrieved']]}")

    print("\nAuth - a request without the shared secret must be rejected")
    try:
        service.answer(
            service.AskRequest(question=IN_SCOPE),
            x_lumen_secret=None,
        )
        results.append(check("rejected", False, "the call succeeded without a secret"))
    except HTTPException as exc:
        results.append(check(
            "rejected with 401",
            exc.status_code == 401,
            f"got status {exc.status_code}",
        ))

    ok = all(results)
    print(f"\n{'ALL CHECKS PASSED' if ok else 'FAILURES ABOVE'}"
          f" ({sum(results)}/{len(results)})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
