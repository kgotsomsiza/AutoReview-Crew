"""LIVE MODE: builds real Band agents from each agent module's role prompt.

This is the bridge between our agent role definitions (agents/*.py) and the
Band SDK. The simulation path (main.py + band_client.py) stays untouched and
never imports this file, so `py main.py` keeps working with zero dependencies.

Every hard-won lesson from the sandbox is encoded here ONCE:
- temperature=0            -> cheap models follow tool instructions reliably
- COMMON_RULES appended    -> replies MUST go through band_send_message
- custom_section, never system_prompt -> keeps Band's built-in instructions
"""
import logging
import shutil
import subprocess
import time
import asyncio

import httpx
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

# band-sdk 1.0.0 (released for the hackathon) imports as `band`.
# The old 0.2.x (still in the practice sandbox) imported as `thenvoi`.
from band import Agent, SessionConfig
from band.adapters.langgraph import LangGraphAdapter
from band.config import load_agent_config

from config import llm_settings, REVIEW_REPO, REVIEW_PR
from lead_orchestrator import LeadOrchestratorAdapter
from sample_data.sample_pull_request import SAMPLE_DIFF

logger = logging.getLogger(__name__)

# Keep agent messages manageable: cap a fetched diff so a huge PR can't blow up
# the model context or a Band message. Curated demo PRs are small; this is a guard.
_MAX_DIFF_CHARS = 8000


def _fetch_github_pr_diff(repo: str, pr: str) -> str | None:
    """Fetch a PUBLIC GitHub PR's unified diff. No auth/token needed for public
    repos. Returns None on any failure so the caller can fall back to the sample."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr}"
    headers = {"Accept": "application/vnd.github.v3.diff", "User-Agent": "AutoReview-Crew"}
    try:
        r = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
        if r.status_code == 200 and r.text.strip():
            diff = r.text
            if len(diff) > _MAX_DIFF_CHARS:
                diff = diff[:_MAX_DIFF_CHARS] + "\n\n[... diff truncated for review ...]"
            return diff
    except Exception:
        pass
    return None

# Appended to EVERY agent's custom_section. On Band, plain LLM text is silently
# discarded - replying means CALLING the send-message tool. Cheap models skip
# that unless told in no uncertain terms.
COMMON_RULES = """
HOW TO BE HEARD: band_send_message is the ONLY way anyone hears you. Anything you
produce as plain text (outside a tool call) is silently discarded - so when you
DO respond, you MUST do it by calling band_send_message. Keep messages short,
structured, plain-text (no markdown tables).
DO NOT REPEAT YOURSELF: if you are triggered again about something you have
ALREADY answered or handled in this room, send NOTHING - make no tool call at all
and end your turn. Never re-post a report or a message you already sent, and never
post "see my earlier report above" or any acknowledgement. Silence is the CORRECT
response to a duplicate trigger; an extra message is spam.
HANDLE SECRETS SAFELY: if you reference a secret, API key, token, or password you
found, you MUST MASK it - show only the first ~4 and last ~4 characters with the
middle hidden (e.g. report the key sk-live-1234567890abcdef as "sk-live-12...cdef").
NEVER write a full secret value in a message: repeating a live secret into the room
is itself a security leak, and a security tool must not commit the leak it reports.
STOP AFTER SENDING: after one band_send_message succeeds for the current request,
do not call any tool again; end your turn."""


@tool
def get_code_change() -> str:
    """Fetch the code change (diff) that is currently under review."""
    # Increment 2: review a REAL GitHub PR when one is configured (REVIEW_REPO +
    # REVIEW_PR in .env); otherwise fall back to the built-in sample so the demo
    # still runs offline / before a target repo exists.
    if REVIEW_REPO and REVIEW_PR:
        diff = _fetch_github_pr_diff(REVIEW_REPO, REVIEW_PR)
        if diff:
            return diff
    return SAMPLE_DIFF


# Full path to gh.exe (installed via winget; may not be on the agent process's PATH).
_GH_EXE = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"


@tool
def post_pr_review(review: str) -> str:
    """Post the final code review as a comment on the GitHub pull request under review.
    Pass the COMPLETE review text (decision, findings, fixes). Call this exactly once,
    after you have decided, to deliver the crew's verdict back onto the PR."""
    if not (REVIEW_REPO and REVIEW_PR):
        return "No PR configured - skipped posting."
    try:
        r = subprocess.run(
            [_GH_EXE, "pr", "comment", REVIEW_PR, "--repo", REVIEW_REPO, "--body", review],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return f"Posted the review to {REVIEW_REPO} PR #{REVIEW_PR}."
        return f"Could not post the review: {r.stderr.strip()[:200]}"
    except Exception as e:
        return f"Could not post the review: {e}"


class _DedupTools:
    """Proxy over the platform tools that drops an agent's REDUNDANT sends, so
    re-delivered triggers / message retries / accidental LLM loops cannot spam the
    room - WITHOUT removing any autonomy. All platform tools route through
    execute_tool_call (verified in the SDK), so that is the single interception point.

      reviewer_mode=True  -> drop only near-simultaneous duplicate sends from the
                             same trigger. The Lead may legitimately re-trigger a
                             missing reviewer 30s later if the first message was
                             not visible in the room.
      reviewer_mode=False -> drop only EXACT-duplicate sends. The Lead legitimately
                             sends several DIFFERENT messages (delegate, recruit, decide).

    A send is recorded only AFTER it succeeds, so a genuinely failed send can still be
    re-sent - lost-message resilience is preserved. A new round (window elapsed) is free."""

    _WINDOW = 90.0  # seconds, for exact duplicate Lead sends
    _REVIEWER_RACE_WINDOW = 2.0  # seconds, for duplicate tool calls in one reviewer turn
    _SEND_TOOLS = {"band_send_message", "send_message", "thenvoi_send_message"}
    # FIX 1: a dropped send returns a SUCCESS-looking result. A "duplicate
    # suppressed" note made the LLM think the send failed -> it looped, retrying
    # (20 recursion errors in one run). Reading "sent" makes it stop.
    _OK = "Message sent."
    _INCOMPLETE_TEST = (
        "Message not sent: include the [TESTS] verdict and at least two "
        "pytest functions named def test_... in one band_send_message call."
    )

    def __init__(self, inner, state: dict, reviewer_mode: bool, on_sent=None,
                 trigger_id=None, agent_key: str | None = None):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_state", state)
        object.__setattr__(self, "_reviewer", reviewer_mode)
        object.__setattr__(self, "_on_sent", on_sent)
        object.__setattr__(self, "_trigger_id", trigger_id)
        object.__setattr__(self, "_agent_key", agent_key)

    @staticmethod
    def _norm_content(arguments: dict) -> str:
        return " ".join(str(arguments.get("content") or "").split())

    def _test_report_is_complete(self, arguments: dict) -> bool:
        return str(arguments.get("content") or "").count("def test_") >= 2

    async def execute_tool_call(self, tool_name, arguments):
        if tool_name in self._SEND_TOOLS and isinstance(arguments, dict):
            lock = self._state.setdefault("_send_lock", asyncio.Lock())
            async with lock:
                now = time.monotonic()
                if self._reviewer:
                    trigger_id = str(self._trigger_id) if self._trigger_id is not None else None
                    sent_by_trigger = self._state.setdefault("_sent_by_trigger", {})
                    if trigger_id and sent_by_trigger.get(trigger_id):
                        logger.info("[DEDUP] reviewer already sent for trigger %s; dropping extra send",
                                    trigger_id[:8])
                        return self._OK
                    if self._agent_key == "test_reviewer" and not self._test_report_is_complete(arguments):
                        logger.info("[DEDUP] suppressed incomplete Test report without pytest functions")
                        return self._INCOMPLETE_TEST
                    last = self._state.get("_last_ok")
                    if last is not None and (now - last) < self._REVIEWER_RACE_WINDOW:
                        logger.info("[DEDUP] reviewer duplicate send race; dropping extra send")
                        return self._OK
                    result = await self._inner.execute_tool_call(tool_name, arguments)
                    self._state["_last_ok"] = time.monotonic()  # record AFTER success
                    if trigger_id:
                        sent_by_trigger[trigger_id] = True
                    if self._on_sent:
                        self._on_sent()
                    return result
                text = self._norm_content(arguments)[:600].lower()
                if text:
                    last = self._state.get(text)
                    if last is not None and (now - last) < self._WINDOW:
                        logger.info("[DEDUP] suppressed a duplicate send (same text within %ds)",
                                    int(self._WINDOW))
                        return self._OK
                    result = await self._inner.execute_tool_call(tool_name, arguments)
                    self._state[text] = time.monotonic()  # record AFTER success
                    if self._on_sent:
                        self._on_sent()
                    return result
        return await self._inner.execute_tool_call(tool_name, arguments)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class DedupLangGraphAdapter(LangGraphAdapter):
    """LangGraph adapter that makes an agent's outgoing messages idempotent per room -
    the network-independent fix for duplicate reports and nudge-spam, while the agents
    stay fully autonomous. reviewer_mode is True for reviewers, False for the Lead."""

    def __init__(self, *args, reviewer_mode: bool = True, agent_key: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._reviewer_mode = reviewer_mode
        self._agent_key = agent_key
        self._state_by_room: dict = {}
        self._answered_by_room: dict = {}

    async def on_message(self, msg, tools, history, participants_msg, contacts_msg,
                         *, is_session_bootstrap, room_id):
        answered = self._answered_by_room.setdefault(room_id, set())
        mid = getattr(msg, "id", None)
        # FIX 2 - IDEMPOTENT INTAKE (reviewers): if this exact trigger message was
        # already answered, skip re-processing it. This beats a re-delivered trigger
        # at ANY timing (the time window alone missed a 2m47s-late re-delivery).
        if self._reviewer_mode and mid is not None and mid in answered:
            logger.info("[DEDUP] already answered trigger %s; skipping re-delivery", str(mid)[:8])
            return
        state = self._state_by_room.setdefault(room_id, {})
        wrapped = _DedupTools(
            tools, state, self._reviewer_mode,
            on_sent=(lambda: answered.add(mid)) if mid is not None else None,
            trigger_id=mid,
            agent_key=self._agent_key,
        )
        return await super().on_message(
            msg, wrapped, history, participants_msg, contacts_msg,
            is_session_bootstrap=is_session_bootstrap, room_id=room_id,
        )


def make_agent(config_name: str, provider: str, model: str, role_section: str) -> Agent:
    """Wire one reviewer (or the Lead): role prompt + its own model/provider + Band
    identity. Uses DedupLangGraphAdapter so duplicate sends are dropped automatically."""
    llm_key, base_url = llm_settings(provider)
    # Only the Lead may publish the verdict to GitHub. Reviewers must NOT have the
    # tool - one called it and posted its own partial findings to the PR (June 13).
    tools = [get_code_change]
    if config_name == "lead_reviewer":
        tools.append(post_pr_review)
    # Featherless serverless models COLD-START: the first request after idle waits
    # ~56s while the (e.g. 72B) model loads onto a GPU. Aborting mid-load just spawns
    # retries that pile up against Featherless's low concurrency cap and cascade into
    # the "no streaming chunk" stalls we saw (June 14). So Featherless calls get enough
    # patience to ride out a cold load in a SINGLE request, and fewer retries so they
    # never overlap; the keep-warm pinger in run_crew.py keeps the model loaded so a
    # cold start is the rare fallback, not the norm. AIML models are always-on, so they
    # keep a tight stall timeout that self-heals a genuinely dead stream fast.
    is_featherless = (provider == "featherless")
    chunk_timeout = 80 if is_featherless else 40
    req_timeout = 120 if is_featherless else 90
    n_retries = 2 if is_featherless else 3
    adapter = DedupLangGraphAdapter(
        # LAG RESILIENCE: a slow/stalled call self-heals rather than killing the message.
        #   stream_chunk_timeout -> abandon a truly dead stream (sized to survive a cold
        #                           start on Featherless; tight on always-on AIML)
        #   request_timeout      -> no single call can hang forever
        # NOTE: hardens against LAG (slow-but-connected). A total internet OUTAGE still
        # stops everything - the only fix there is a backup connection.
        llm=ChatOpenAI(
            model=model, temperature=0, api_key=llm_key, base_url=base_url,
            max_retries=n_retries, request_timeout=req_timeout, stream_chunk_timeout=chunk_timeout,
        ),
        checkpointer=InMemorySaver(),
        additional_tools=tools,
        # Reviewers: exact-trigger intake dedup + short send-race guard. Lead:
        # exact-duplicate dedup only (it sends several different messages legitimately).
        reviewer_mode=(config_name != "lead_reviewer"),
        agent_key=config_name,
        custom_section=role_section + "\n" + COMMON_RULES,
        # New in SDK 1.0: every tool call/result is posted to the room as an
        # event - makes the agents' work visible in the UI (audit trail, demo!).
        enable_execution_reporting=True,
        # Loop ceiling: a healthy turn needs ~6 steps (think, fetch diff, send,
        # stop). The default 50 let a looping agent burn 41 LLM calls (June 12).
        recursion_limit=12,
    )
    agent_id, band_key = load_agent_config(config_name)
    # max_message_retries=3 for lost-message resilience. This is SAFE even though a
    # retry re-runs the agent and re-sends, because DedupLangGraphAdapter drops the
    # duplicate send: retries protect against lost messages without spamming the room.
    return Agent.create(
        adapter=adapter, agent_id=agent_id, api_key=band_key,
        session_config=SessionConfig(max_message_retries=3),
    )


def make_lead_orchestrator(provider: str, model: str, active_review_event=None) -> Agent:
    """Build the Lead as the DETERMINISTIC orchestrator (lead_orchestrator.py). The
    strong `model` is used ONLY for the one synthesis call per round - coordination is
    code, so it cannot loop, stall, or lose a recruitment race. The reviewers stay
    autonomous agents; the Lead still posts and recruits visibly through Band."""
    llm_key, base_url = llm_settings(provider)
    llm = ChatOpenAI(
        model=model, temperature=0, api_key=llm_key, base_url=base_url,
        max_retries=3, request_timeout=90, stream_chunk_timeout=40,
    )
    adapter = LeadOrchestratorAdapter(
        llm=llm,
        post_review_fn=lambda text: post_pr_review.func(text),
        active_review_event=active_review_event,
    )
    agent_id, band_key = load_agent_config("lead_reviewer")
    return Agent.create(
        adapter=adapter, agent_id=agent_id, api_key=band_key,
        session_config=SessionConfig(max_message_retries=2),
    )
