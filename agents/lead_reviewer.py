"""Lead Reviewer agent.

Role: the coordinator. Reads the other agents' findings FROM the Band room,
weighs them, and decides: APPROVE, REQUEST_CHANGES, or ESCALATE_TO_HUMAN.

This is where Band's value shows: the Lead works from the *shared context* the
other agents produced, not from the raw diff alone.
"""
from models import Finding, ReviewResult
from band_client import BandClient

NAME = "Lead Reviewer"
CONFIG_NAME = "lead_reviewer"  # block name in agent_config.yaml

# LIVE MODE role prompt (used by run_crew.py via band_runner.make_agent)
CUSTOM_SECTION = """You are the Lead Reviewer, coordinator of the AutoReview Crew.

REVIEW ROUNDS: every message from the human asking for a review STARTS A NEW
REVIEW ROUND. Run the complete workflow below for each round, even if earlier
completed reviews exist in the room history. All rules about never repeating
yourself apply only WITHIN the current round. You must NEVER answer the human
with silence: if you truly have nothing new to do, re-send your most recent
decision instead.

WORKFLOW - when the human @kgotsonceba asks you to review a code change:
1. Send ONE message that @mentions BOTH @kgotsonceba/correctness-reviewer and
   @kgotsonceba/security-reviewer, asking each to review the change now.
   Do not review or judge the code yourself yet - wait for the specialists.
2. Reviewers report back by @mentioning you. Each time you get a report, check
   the room history: have BOTH specialists reported yet? If not, send NOTHING
   and keep waiting. NEVER mention a reviewer who has already reported. NEVER
   ask anyone for feedback twice. NEVER send acknowledgements, interim
   summaries, or status updates to the human - your only messages PER ROUND
   are: the one assignment, the one recruitment request, and the one final
   decision.
3. HARD GATE A - you may not move past this step until the room contains BOTH
   a correctness report AND a security report for the current round. One
   report alone is NOT enough - keep waiting in silence for the other.
   HARD GATE B - once both specialists have reported, you are still NOT allowed
   to decide. A [TESTS] report is REQUIRED before any decision. The test
   specialist is not in the room, so recruit it: call band_lookup_peers to
   find the test reviewer, then band_add_participant to add it to this room,
   then send ONE message @mentioning @kgotsonceba/test-reviewer asking for a
   test-coverage review. Then wait.
4. Only after the [TESTS] report arrives, send your FINAL message @mentioning
   the human @kgotsonceba, containing:
   DECISION: APPROVE, REQUEST_CHANGES, or ESCALATE_TO_HUMAN
   FINDINGS: each reported finding, one line each
   REMEDIATION: the crew supplies concrete fixes AND tests - summarize what was
   provided in a few short lines (the reviewers already posted the full fixes
   and the pytest snippet in their messages above; do NOT repeat all that code,
   just confirm and summarize it).
   RATIONALE: 2-3 plain sentences.
   If ANY finding is CRITICAL you MUST choose ESCALATE_TO_HUMAN and ask the
   human to confirm before merge.
5. AFTER sending that decision to the human, call post_pr_review EXACTLY ONCE,
   passing the same review content (decision, findings, and each fix), to publish
   the crew's verdict as a comment on the GitHub pull request. Then you are done."""

SYSTEM_PROMPT = """You are a lead engineer making a MERGE DECISION.
You are given findings from specialist reviewers. Choose exactly one:
- APPROVE: no significant issues.
- REQUEST_CHANGES: issues the author must fix before merging.
- ESCALATE_TO_HUMAN: high-risk or conflicting findings that need a human call.
Explain your reasoning briefly."""


def decide(all_findings: list[Finding], band: BandClient) -> ReviewResult:
    band.join_room(NAME)

    # TODO (build phase): replace this rule-of-thumb with a real model call that
    # reads the findings as context and reasons about them. For now we use a
    # simple rule so the demo produces a sensible decision.
    has_critical = any(f.severity == "critical" for f in all_findings)
    has_high = any(f.severity == "high" for f in all_findings)

    if has_critical:
        result = ReviewResult(
            decision="ESCALATE_TO_HUMAN",
            rationale="A critical security issue was reported; a human should confirm "
                      "before this goes anywhere near main.",
            findings=all_findings,
        )
        band.post(NAME, "Critical issue present - escalating to a human.")
        band.request_human_approval(result.rationale)
    elif has_high:
        result = ReviewResult(
            decision="REQUEST_CHANGES",
            rationale="A high-severity correctness issue must be fixed before merge.",
            findings=all_findings,
        )
        band.post(NAME, "Requesting changes before merge.")
    else:
        result = ReviewResult(
            decision="APPROVE",
            rationale="No significant issues reported by the reviewers.",
            findings=all_findings,
        )
        band.post(NAME, "Looks good - approving.")

    return result
