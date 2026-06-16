"""LIVE MODE: start the whole AutoReview Crew (all 4 agents) on Band.

Each agent gets its own Band identity (agent_config.yaml), its own role prompt
(agents/*.py), and its own MODEL on its own PROVIDER (.env / config.py) - that
is the cross-model review: four reviewers, four model families, two providers.

Run it:    .\\.venv\\Scripts\\python.exe run_crew.py
Stop it:   Ctrl+C
Demo:      in the Band web app, make a room with YOU + Lead + Correctness +
           Security (NOT the Test Reviewer - the Lead recruits that one), then:
           @Lead Reviewer please review the latest code change
"""
import asyncio
import logging
import random
import time

from dotenv import load_dotenv

load_dotenv()

import config
from agents import correctness_reviewer, security_reviewer, lead_reviewer, test_reviewer
from band_runner import make_agent, make_lead_orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# (module, provider, model) - one line per crew member, in start order.
ROSTER = [
    (lead_reviewer, config.LEAD_PROVIDER, config.LEAD_MODEL),
    (correctness_reviewer, config.CORRECTNESS_PROVIDER, config.CORRECTNESS_MODEL),
    (security_reviewer, config.SECURITY_PROVIDER, config.SECURITY_MODEL),
    (test_reviewer, config.TEST_PROVIDER, config.TEST_MODEL),
]


# Reconnect backoff. A one-off drop reconnects fast (~2s, still "immediately"),
# but if an agent keeps FLAPPING we back off exponentially with jitter instead of
# hammering Band - a tight 2s retry loop across 4 agents is exactly what trips
# Band's HTTP 429 rate-limiting and turns a blip into a self-sustaining outage. A
# run that stays healthy resets the backoff, so ordinary reconnects stay quick.
_BACKOFF_BASE = 2.0     # first retry waits ~2s
_BACKOFF_CAP = 60.0     # never wait longer than this between retries
_BACKOFF_RESET = 30.0   # a run that stayed up this long is healthy -> reset to fast
_BACKOFF_MAX_EXP = 5    # cap the exponent: 2, 4, 8, 16, 32, then 60s ceiling


async def _resilient_run(agent, name: str, delay: float):
    """Start staggered, then KEEP THE AGENT ALIVE across drops. The SDK auto-
    reconnects its WebSocket on transient blips; this is the outer net for when an
    agent's whole run loop ends on a network error - we restart it, forever. Band
    persists the room's messages, so on reconnect the agent re-fetches the pending
    work and the job CONTINUES where it left off; the dedup layer stops duplicates.

    Reconnects use EXPONENTIAL BACKOFF + JITTER (constants above): fast on a one-off
    drop, but it will NOT hammer Band into rate-limiting (429) when connectivity is
    genuinely down - it rides the outage out and resumes when the network returns.

    (Staggering the first start by `delay` avoids 4 agents joining room topics at
    the same instant, which timed out on Band under load - June 12.)"""
    await asyncio.sleep(delay)
    attempt = 0
    while True:
        started = time.monotonic()
        try:
            await agent.run()
            reason = "run loop ended"
        except Exception as e:
            reason = f"network/error ({type(e).__name__})"
        if time.monotonic() - started >= _BACKOFF_RESET:
            attempt = 0  # stayed healthy -> treat this as a fresh, fast reconnect
        wait = min(_BACKOFF_CAP, _BACKOFF_BASE * (2 ** attempt))
        wait *= 0.5 + random.random()  # +/-50% jitter so the 4 agents don't sync up
        attempt = min(attempt + 1, _BACKOFF_MAX_EXP)
        logger.warning("%s %s; reconnecting in %.1fs", name, reason, wait)
        await asyncio.sleep(wait)


async def _keep_warm(provider: str, model: str, interval: float = 120.0, active_review_event=None):
    """Keep a serverless (Featherless) model LOADED so real reviews never pay a cold
    start. Featherless unloads an idle model; the next request then waits ~56s for it
    to reload - long enough to trip the stream timeout and stall the Security Reviewer
    (the root cause of the June 14 stalls). A tiny periodic ping keeps it warm. The
    first ping (at startup) absorbs the initial cold load in the background, before any
    review arrives. During an active review, the pinger pauses so it cannot compete
    with Security for Featherless's low-concurrency slot."""
    from openai import AsyncOpenAI

    key, base_url = config.llm_settings(provider)
    client = AsyncOpenAI(api_key=key, base_url=base_url, timeout=70)
    while True:
        if active_review_event is not None and active_review_event.is_set():
            logger.info("[WARM] ping paused (active review)")
            while active_review_event.is_set():
                await asyncio.sleep(5)
            await asyncio.sleep(5)
        try:
            await client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": "ok"}],
                max_tokens=1, temperature=0,
            )
            logger.info("[WARM] %s ready", model)
        except Exception as e:
            logger.info("[WARM] ping skipped (%s)", type(e).__name__)
        await asyncio.sleep(interval)


async def main():
    print("=" * 64)
    print("AutoReview Crew - LIVE on Band (Ctrl+C to stop)")
    print("=" * 64)
    agents = []
    active_review_event = asyncio.Event()
    for module, provider, model in ROSTER:
        kind = "orchestrator" if module is lead_reviewer else "reviewer"
        print(f"  {module.NAME:22s} brain: {model}  ({provider})  [{kind}]")
        if module is lead_reviewer:
            agent = make_lead_orchestrator(provider, model, active_review_event=active_review_event)
        else:
            agent = make_agent(module.CONFIG_NAME, provider, model, module.CUSTOM_SECTION)
        agents.append((agent, module.NAME))
    print("-" * 64)
    # Each agent keeps its own WebSocket, self-heals on drops, starts staggered 4s apart.
    # A keep-warm pinger runs alongside so Featherless never cold-starts under a review.
    await asyncio.gather(
        _keep_warm(config.SECURITY_PROVIDER, config.SECURITY_MODEL, active_review_event=active_review_event),
        *(_resilient_run(a, name, i * 4.0) for i, (a, name) in enumerate(agents))
    )


if __name__ == "__main__":
    # SUPERVISOR: auto-restart the crew if it exits (a prolonged network outage can
    # kill the agents and end the process). When connectivity returns this reconnects
    # and stays up on its own - so the crew is always live for a demo/test, no
    # babysitting. Ctrl+C still stops it cleanly.
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\nCrew stopped.")
            break
        except Exception as e:
            print(f"\nCrew exited ({type(e).__name__}); restarting in 5s...")
            time.sleep(5)
        else:
            print("\nCrew exited; restarting in 5s...")
            time.sleep(5)
