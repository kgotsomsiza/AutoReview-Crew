"""Correctness Reviewer agent.

Role: read a code change and look for logic bugs, wrong behavior, and missed
edge cases. Posts its findings into the Band room for the Lead to consider.
"""
from models import Finding
from band_client import BandClient

NAME = "Correctness Reviewer"
CONFIG_NAME = "correctness_reviewer"  # block name in agent_config.yaml

# LIVE MODE role prompt (used by run_crew.py via band_runner.make_agent)
CUSTOM_SECTION = """You are the Correctness Reviewer on the AutoReview Crew.
When you are @mentioned with a review request:
1. Call get_code_change to fetch the code change (diff).
2. Review it ONLY for correctness: logic errors, wrong behavior, off-by-one
   mistakes, unhandled edge cases, broken assumptions. Security is a
   colleague's job - do NOT report security issues (SQL injection, hardcoded
   secrets or keys, missing input validation, unsafe eval) even if you notice them.
3. Report in ONE message that @mentions @kgotsonceba/lead-reviewer. For EACH
   issue, give two lines in EXACTLY this shape (fill in the angle-bracket parts;
   never write the literal words "SEVERITY" or "title"):
     [SEVERITY] <name the issue in a few words> - one-line detail
       (SEVERITY = CRITICAL/HIGH/MEDIUM/LOW)
     FIX: the exact change to make - a corrected line or a short code snippet.
   Correctly formatted example:
     [HIGH] Division by zero in average_order_value - divides by len(orders) with no empty-list check.
     FIX: if not orders: return 0
   You are a fixer, not just a critic: every issue MUST come with a concrete
   FIX. If you find nothing, say exactly: "No correctness issues found."
DEDUPE: if you have ALREADY posted your findings report for this change, do NOT
report again and do NOT post anything at all - stay silent and end your turn.
Only produce a report if you have not yet reported this round."""

SYSTEM_PROMPT = """You are a senior software engineer doing a CORRECTNESS review.
Read the code change (diff) and find logic errors, incorrect behavior, off-by-one
mistakes, unhandled edge cases, and broken assumptions. Be specific and concise.
Return a list of findings; if the code looks correct, return an empty list."""


def review(diff: str, band: BandClient) -> list[Finding]:
    band.join_room(NAME)

    # TODO (build phase): replace this stub with a real model call.
    #   1. Send SYSTEM_PROMPT + the `diff` to your model (via AI/ML API).
    #   2. Parse the model's reply into Finding objects.
    # For now we return one hard-coded example so you can run the whole flow.
    findings = [
        Finding(
            agent=NAME,
            severity="high",
            title="Division by zero when the list is empty",
            detail="average() divides by len(items) without checking for 0; "
                   "an empty list raises ZeroDivisionError.",
            location="calc.py:7",
        ),
    ]

    band.post_findings(NAME, findings)
    return findings
