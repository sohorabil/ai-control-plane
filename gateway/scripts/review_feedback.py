"""Part 12's feedback loop, step 2: human review of thumbs-down answers.

Shows each unreviewed thumbs-down case to a human (the trainee, per the
brief: "I review thumbs-down cases"), who decides whether it's worth
keeping as a permanent regression test. Approved cases become new "judged"
entries in evals/golden.jsonl (Part 6's eval format) — deliberately a
SEPARATE, explicit step from submitting feedback, so one bad thumbs-down
vote can never silently poison the golden set on its own; a human always
confirms first.

Usage: python -m scripts.review_feedback
"""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import Feedback, SessionLocal

GOLDEN_PATH = Path(__file__).parent.parent.parent / "evals" / "golden.jsonl"


def review_thumbs_down() -> None:
    session = SessionLocal()
    try:
        cases = (
            session.query(Feedback)
            .filter_by(rating="down", reviewed=False)
            .order_by(Feedback.created_at)
            .all()
        )

        if not cases:
            print("No unreviewed thumbs-down feedback.")
            return

        print(f"{len(cases)} unreviewed thumbs-down case(s):\n")
        added = 0
        for fb in cases:
            print(f"--- Question ---\n{fb.question}")
            print(f"--- Answer given (source: {fb.source}) ---\n{fb.answer}")
            decision = input(
                "\nAdd a CORRECTED version as a new golden case? "
                "[y / n / s(kip for now)]: "
            ).strip().lower()

            if decision == "y":
                corrected_rubric = input(
                    "What should a correct answer to this question look like "
                    "(brief rubric)?: "
                ).strip()
                golden_case = {
                    "id": f"feedback-{uuid.uuid4().hex[:8]}",
                    "type": "judged",
                    "prompt": fb.question,
                    "rubric": corrected_rubric,
                }
                with GOLDEN_PATH.open("a") as f:
                    f.write(json.dumps(golden_case) + "\n")
                fb.added_to_golden = True
                added += 1
                print(f"Added as golden case {golden_case['id']}.\n")
            elif decision == "n":
                print("Marked reviewed, not added.\n")
            else:
                print("Skipped — will show again next run.\n")
                continue

            fb.reviewed = True
            session.commit()

        print(f"Done. {added} new golden case(s) added to {GOLDEN_PATH}.")
    finally:
        session.close()


if __name__ == "__main__":
    review_thumbs_down()
