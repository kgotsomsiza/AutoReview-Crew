"""AutoReview Crew - entry point.

Runs the multi-agent code review pipeline. Out of the box this runs in
SIMULATION MODE (no API keys needed) so you can see the whole flow:

    Correctness Reviewer ─┐
                          ├─►  findings posted to a Band room  ─►  Lead Reviewer ─► decision
    Security Reviewer  ───┘

During the hackathon you'll replace the stubbed parts with real model calls and
real Band SDK calls (search the code for "TODO").

Run it:   py main.py
"""
from config import BAND_API_KEY, BAND_ROOM_ID, have_real_credentials
from band_client import BandClient
from sample_data.sample_pull_request import SAMPLE_DIFF
from agents import correctness_reviewer, security_reviewer, lead_reviewer


def run(diff: str) -> None:
    simulate = not have_real_credentials()

    print("=" * 64)
    print("AutoReview Crew - multi-agent code review through Band")
    print("MODE:", "SIMULATION (no keys yet)" if simulate else "LIVE")
    print("=" * 64)

    band = BandClient(api_key=BAND_API_KEY, room_id=BAND_ROOM_ID, simulate=simulate)

    print("\n1) Specialist reviewers inspect the change and post findings to Band:\n")
    findings = []
    findings += correctness_reviewer.review(diff, band)
    findings += security_reviewer.review(diff, band)

    print("\n2) Lead Reviewer reads the shared findings from Band and decides:\n")
    result = lead_reviewer.decide(findings, band)

    print("\n" + "-" * 64)
    print(f"DECISION: {result.decision}")
    print(f"WHY:      {result.rationale}")
    print("-" * 64)


if __name__ == "__main__":
    run(SAMPLE_DIFF)
