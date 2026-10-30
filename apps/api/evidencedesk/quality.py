"""Deterministic review flags for a validated answer.

Validators already guarantee that every quote is copied verbatim from a retrieved passage. These
checks look for the cheap, common ways a well-formed answer can still be wrong: a claim that
states a number or drops a negation its quote does not support, a claim that shares little with
its quote, a note that adds details, citations of outdated or conflicting sources, and weak
retrieval. They cost no model call and run on every analysis; a flag asks a person to look, it
does not block the answer.
"""

import re
from typing import Any

# A flag at "review" severity marks the answer for a closer look; "info" is context only.
FLAGS: dict[str, tuple[str, str]] = {
    "number_mismatch": ("review", "A claim states a number its quote does not contain."),
    "negation_dropped": ("review", "A quote is negative but the claim drawn from it is not."),
    "weak_quote_support": ("review", "A claim shares little wording with its quote."),
    "note_adds_number": ("review", "The draft note adds a number no claim or quote contains."),
    "outdated_source": ("review", "The answer cites a superseded or obsolete passage."),
    "conflicting_sources": ("review", "The answer cites a passage that conflicts with another."),
    "weak_retrieval": ("review", "The retrieved passages only loosely match the question."),
    "fallback_model": ("info", "The fallback model answered instead of the primary model."),
}
SUPPORT_THRESHOLD = 0.4
# Measured with bge-small: answerable eval questions retrieve at <= 0.31, out-of-scope ones
# mostly at >= 0.35 (see reports/answer-checks.md).
WEAK_DISTANCE = 0.34
NUMBER_WORDS = {
    # "one" is left out: "the old one" is far more common than the number.
    "zero": 0, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "ninety": 90, "hundred": 100,
}
# Negative or restrictive wording, including common paraphrases ("rather than" for "not").
NEGATIONS = re.compile(
    r"\b(not|never|no|cannot|can't|cant|won't|don't|doesn't|isn't|aren't|without|none|"
    r"neither|nor|unless|only|rather|instead|except|avoid|unable|prohibited|forbidden|"
    r"reject|rejected|disallowed|until)\b|n't\b",
    re.IGNORECASE,
)
STOPWORDS = frozenset(
    "about after also because before being between both could does each from have into "
    "more most must only other over same should such than that their them then there these "
    "they this those through under until using very what when where which while will with "
    "within would your relaynest".split()
)


def digits(text: str) -> set[float]:
    return {float(x.replace(",", "")) for x in re.findall(r"\d+(?:[.,]\d+)*", text)}


def numbers(text: str) -> set[float]:
    found = digits(text)
    found |= {
        float(NUMBER_WORDS[word])
        for word in re.findall(r"[a-z]+", text.lower())
        if word in NUMBER_WORDS
    }
    return found


def stems(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9_-]+", text.lower())
    return {word[:5] for word in words if len(word) >= 4 and word not in STOPWORDS}


def negated(text: str) -> bool:
    return bool(NEGATIONS.search(text))


def negated_subjects(text: str) -> list[set[str]]:
    """The words each negation in `text` applies to: up to three content words after it."""
    subjects = []
    for sentence in re.split(r"(?<=[.;!?])\s+", text):
        for match in NEGATIONS.finditer(sentence):
            following = re.findall(r"[a-z][a-z0-9_-]+", sentence[match.end() :].lower())
            words = [w[:5] for w in following if len(w) >= 4 and w not in STOPWORDS][:3]
            if len(words) >= 2:
                subjects.append(set(words))
    return subjects


def review_flags(
    answer: dict[str, Any],
    evidence: list[dict[str, Any]],
    question: str = "",
    *,
    fell_back: bool = False,
) -> list[dict[str, str]]:
    """Return ordered, de-duplicated flags; empty means nothing looked unusual."""
    codes: list[str] = []
    claims = answer.get("claims") or []
    rows = {str(row.get("id")): row for row in evidence}
    asked = numbers(question)
    # Claims may paraphrase across all of the answer's quotes, so support is measured
    # against every quote plus the question.
    supported = stems(
        " ".join(c.get("quote", "") for claim in claims for c in claim.get("citations", []))
        + " "
        + question
    )
    # The note may summarize anything retrieved, so passage numbers count as supported too.
    passages = " ".join(row.get("body", "") for row in evidence)
    quoted_numbers: set[float] = set(asked) | numbers(passages)
    claimed_numbers: set[float] = set()
    for claim in claims:
        text = claim.get("text", "")
        quotes = " ".join(c.get("quote", "") for c in claim.get("citations", []))
        quoted_numbers |= numbers(quotes)
        claimed_numbers |= numbers(text)
        if numbers(text) - numbers(quotes) - asked:
            codes.append("number_mismatch")
        # Leaving out a negative clause is fine; restating its subject without the negation is
        # the dangerous inversion ("cannot be extended" -> "can be extended").
        if not negated(text) and any(
            len(subject & stems(text)) >= 2 for subject in negated_subjects(quotes)
        ):
            codes.append("negation_dropped")
        wanted = stems(text)
        if wanted and len(wanted & supported) / len(wanted) < SUPPORT_THRESHOLD:
            codes.append("weak_quote_support")
        for citation in claim.get("citations", []):
            row = rows.get(str(citation.get("source_id")), {})
            relations = {r.get("relation") for r in row.get("relations", [])}
            if row.get("status") == "obsolete" or "superseded_by" in relations:
                codes.append("outdated_source")
            if "conflicts_with" in relations:
                codes.append("conflicting_sources")
    note = answer.get("proposed_note") or ""
    # Only written digits: notes often count items in words ("three permission types").
    if digits(note) - quoted_numbers - claimed_numbers:
        codes.append("note_adds_number")
    if answer.get("status") == "answered":
        distances = [
            float(row["distance"])
            for row in evidence
            if isinstance(row.get("distance"), (int, float))
        ]
        if not distances or min(distances) > WEAK_DISTANCE:
            codes.append("weak_retrieval")
    if fell_back:
        codes.append("fallback_model")
    return [
        {"code": code, "severity": FLAGS[code][0], "message": FLAGS[code][1]}
        for code in dict.fromkeys(codes)
    ]


def needs_review(flags: list[dict[str, str]]) -> bool:
    return any(flag["severity"] == "review" for flag in flags)
