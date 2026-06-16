"""Security Reviewer agent.

Role: read a code change and look for security problems — injection, unsafe
calls, hardcoded secrets, missing validation. Posts findings into the Band room.
"""
from models import Finding
from band_client import BandClient

NAME = "Security Reviewer"
CONFIG_NAME = "security_reviewer"  # block name in agent_config.yaml

# LIVE MODE role prompt (used by run_crew.py via band_runner.make_agent)
CUSTOM_SECTION = """You are the Security Reviewer on the AutoReview Crew.
When you are @mentioned with a review request:
1. Call get_code_change to fetch the code change (diff).
2. Review it ONLY for security: hardcoded secrets/API keys, injection, unsafe
   eval/exec, missing input validation, insecure defaults. Logic bugs are a
   colleague's job - skip them.
3. Report in ONE message that @mentions @kgotsonceba/lead-reviewer. For EACH
   issue, give two lines in EXACTLY this shape (fill in the angle-bracket parts;
   never write the literal words "SEVERITY" or "title"):
     [SEVERITY] <name the issue in a few words> - one-line detail
       (SEVERITY = CRITICAL/HIGH/MEDIUM/LOW; a hardcoded live secret is always CRITICAL)
     FIX: the exact change to make - a corrected line or a short code snippet.
   Correctly formatted example:
     [CRITICAL] Hardcoded Stripe API key - a live secret is committed in the source.
     FIX: load it from an environment variable: stripe.api_key = os.environ["STRIPE_KEY"]
   You are a fixer, not just a critic: every issue MUST come with a concrete
   FIX. If you find nothing, say exactly: "No security issues found."
DEDUPE: if you have ALREADY posted your findings report for this change, do NOT
report again and do NOT post anything at all - stay silent and end your turn.
Only produce a report if you have not yet reported this round."""

SYSTEM_PROMPT = """You are an application security engineer doing a SECURITY review.
Read the code change (diff) and find vulnerabilities: injection, unsafe eval/exec,
hardcoded secrets/API keys, missing input validation, and insecure defaults.
Return a list of findings; if you see nothing risky, return an empty list."""


def review(diff: str, band: BandClient) -> list[Finding]:
    band.join_room(NAME)

    # TODO (build phase): replace with a real model call (see correctness_reviewer.py).
    findings = [
        Finding(
            agent=NAME,
            severity="critical",
            title="Hardcoded API key committed in source",
            detail="A secret key is written directly in the code. Move it to an "
                   "environment variable and rotate the exposed key.",
            location="calc.py:1",
        ),
    ]

    band.post_findings(NAME, findings)
    return findings
