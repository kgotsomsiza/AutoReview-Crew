"""Deterministic Lead orchestrator - the architecturally-resilient coordinator.

The 3 reviewers stay fully autonomous LLM agents (cross-model, collaborating through
Band). The Lead's COORDINATION is code, so whole classes of failure are designed out
rather than patched. The Lead's LLM is used for exactly ONE thing per round: writing
the final verdict (synthesis) - the part LLMs are good at.

FAILURE MODES, AND HOW THIS DESIGN PREVENTS EACH (by construction):
  - Coordination loop / nudge-spam ...... impossible: the conductor is plain code.
  - Missing / lost report ............... poll with timeout, then RE-TRIGGER that
                                          agent (up to MAX_RETRIGGERS), then degrade
                                          gracefully - it never waits forever.
  - Recruitment race (agent added but    add participant, WAIT a grace period for it
    misses the request) ................. to subscribe, THEN ask; and re-trigger if
                                          the report still doesn't come.
  - Duplicate reports .................... take the FIRST report per sender; ignore rest.
  - One reviewer totally fails .......... after retries, synthesize with what we have,
                                          force ESCALATE_TO_HUMAN, and note the gap.
  - Network drop / process death ........ handled outside (run_crew: per-agent self-heal,
                                          supervisor restart) + Band persists messages.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from band.core.simple_adapter import SimpleAdapter

logger = logging.getLogger(__name__)

# Crew handles (without the leading @).
CORRECTNESS = "kgotsonceba/correctness-reviewer"
SECURITY = "kgotsonceba/security-reviewer"
TEST = "kgotsonceba/test-reviewer"
HUMAN = "kgotsonceba"

POLL_INTERVAL = 4.0             # seconds between room polls
# A reviewer on a slow/flaky provider (e.g. Qwen-72B on Featherless) can legitimately
# need up to ~90s to deliver - that includes self-healing one or two mid-stream stalls
# (each now caught in 25s by stream_chunk_timeout, then retried locally). So the Lead
# waits that long before assuming the message was lost and re-asking. This is what
# keeps a slow-but-working specialist from being visibly re-pinged in the room.
FIRST_RETRIGGER_AFTER = 90.0    # not started yet: wait this long before the first re-ask
RETRIGGER_AFTER = 45.0          # after the first nudge: recovery cadence
STARTED_RETRIGGER_AFTER = 90.0  # started (saw its tool call) but no report yet: re-ask after this
MAX_RETRIGGERS = 3              # then give up on that stage and degrade gracefully
SUBSCRIBE_GRACE = 5.0           # after add_participant, let the agent subscribe before we ask


def _sender_key(raw: dict) -> str:
    """Lowercased, hyphenated sender identity from a room-context message dict.
    Confirmed shape: messages have a 'sender_name' field (e.g. 'Correctness Reviewer')."""
    for k in ("sender_name", "sender_handle", "handle"):
        v = raw.get(k)
        if isinstance(v, str) and v:
            return v.lower().replace(" ", "-")
    return ""


def _content(raw: dict) -> str:
    v = raw.get("content")
    return v if isinstance(v, str) else ""


def _as_utc(value) -> datetime | None:
    """Convert Band timestamps (datetime or ISO string) to aware UTC datetimes."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _message_time(raw: dict) -> datetime | None:
    return _as_utc(raw.get("inserted_at") or raw.get("created_at"))


def _is_current_round(raw: dict, since: datetime) -> bool:
    ts = _message_time(raw)
    return ts is not None and ts >= since


def _is_text(raw: dict) -> bool:
    return raw.get("message_type", "text") == "text"


def _is_started_signal(raw: dict) -> bool:
    """Execution-reporting events tell us a reviewer received work and began."""
    if raw.get("message_type") != "tool_call":
        return False
    return "get_code_change" in _content(raw)


def _is_usable_report(handle: str, content: str) -> bool:
    """A Test report is not usable until the promised pytest functions are present."""
    if handle == TEST:
        return content.count("def test_") >= 2
    return bool(content.strip())


class LeadOrchestratorAdapter(SimpleAdapter[list]):
    """Code-driven Lead. The LLM is called ONCE per round, only to write the verdict."""

    def __init__(self, llm, post_review_fn, active_review_event=None):
        super().__init__()
        self.llm = llm                        # strong model, for the single synthesis call
        self.post_review_fn = post_review_fn  # post_pr_review(text) -> str
        self._busy: set[str] = set()          # rooms with an active round (re-entrancy guard)
        self.active_review_event = active_review_event

    async def on_message(self, msg, tools, history, participants_msg, contacts_msg,
                         *, is_session_bootstrap, room_id):
        # Only a human review request starts a round. Reviewer reports also land here
        # (they @mention the Lead) - ignore them; the polling loop reads them.
        if getattr(msg, "sender_type", "") != "User":
            return
        if "review" not in (msg.content or "").lower():
            return
        if room_id in self._busy:
            return
        self._busy.add(room_id)
        if self.active_review_event is not None:
            self.active_review_event.set()
        try:
            msg_time = _as_utc(getattr(msg, "created_at", None))
            # Use the platform timestamp when available so a reused room cannot
            # satisfy this round with stale reviewer reports from earlier demos.
            since = (msg_time or datetime.now(timezone.utc)) - timedelta(seconds=2)
            await self._run_round(tools, room_id, since)
        except Exception:
            logger.exception("[ORCH] round failed")
            try:
                await tools.send_message(
                    f"@{HUMAN} the review hit an unexpected error and could not complete.",
                    mentions=[HUMAN])
            except Exception:
                pass
        finally:
            self._busy.discard(room_id)
            if self.active_review_event is not None and not self._busy:
                self.active_review_event.clear()

    async def _run_round(self, tools, room_id, since: datetime):
        logger.info("[ORCH] round start in %s", room_id)

        async def ask_specialists(targets=None):
            targets = targets or [CORRECTNESS, SECURITY]
            await tools.send_message(
                f"{' '.join('@' + h for h in targets)} please review the latest code change now.",
                mentions=targets)

        await ask_specialists()
        reports = await self._collect(
            tools, room_id, [CORRECTNESS, SECURITY], ask_specialists, since=since)

        # Recruit the Test Reviewer - the showstopper, done reliably. We add it,
        # GIVE IT TIME TO SUBSCRIBE, then ask (kills the join/ask race).
        logger.info("[ORCH] recruiting test reviewer")

        async def ask_test(targets=None):
            if targets is not None and TEST not in targets:
                return
            try:
                await tools.lookup_peers()
                await tools.add_participant(TEST)
            except Exception:
                logger.warning("[ORCH] add_participant issue (may already be present)")
            await asyncio.sleep(SUBSCRIBE_GRACE)
            await tools.send_message(
                f"@{TEST} please review the test coverage for the latest code change now.",
                mentions=[TEST])

        await ask_test()
        reports.update(await self._collect(tools, room_id, [TEST], ask_test, since=since))

        logger.info("[ORCH] synthesizing verdict")
        verdict = await self._synthesize(reports)
        await tools.send_message(verdict, mentions=[HUMAN])
        try:
            logger.info("[ORCH] %s", self.post_review_fn(verdict))
        except Exception:
            logger.warning("[ORCH] GitHub post failed", exc_info=True)
        logger.info("[ORCH] round complete")

    async def _fetch_current_context(self, tools, room_id, since: datetime):
        """Fetch all pages, then keep only messages created during this round.

        Band returns context oldest-first. In a reused demo room, page 1 can be
        entirely old messages, so a single default fetch can accidentally use a
        stale reviewer report and let the Lead decide too early.
        """
        messages = []
        page = 1
        total_pages = 1
        while page <= total_pages:
            ctx = await tools.fetch_room_context(room_id=room_id, page=page, page_size=100)
            data = ctx.get("data", []) if isinstance(ctx, dict) else []
            messages.extend(raw for raw in data if isinstance(raw, dict) and _is_current_round(raw, since))

            meta = ctx.get("meta", {}) if isinstance(ctx, dict) else {}
            try:
                total_pages = int(meta.get("total_pages") or total_pages)
            except (TypeError, ValueError):
                total_pages = page
            if not data:
                break
            page += 1
        return messages

    async def _collect(self, tools, room_id, wanted, ask_again, *, since: datetime):
        """Poll for each wanted sender's report (FIRST only).

        Tool-call events are treated as "started" signals. That avoids a visible
        duplicate nudge when a reviewer is already working but their final report
        has not landed yet. If a reviewer never starts, or starts then stalls for
        too long, recovery still kicks in and the round eventually completes.
        """
        got = {h: None for h in wanted}
        started = set()
        triggers = 0
        last = time.monotonic()
        while any(v is None for v in got.values()):
            await asyncio.sleep(POLL_INTERVAL)
            try:
                data = await self._fetch_current_context(tools, room_id, since)
            except Exception:
                logger.warning("[ORCH] fetch_room_context failed; will retry", exc_info=True)
                continue
            for raw in data:
                sk = _sender_key(raw)
                for h in wanted:
                    if h.split("/")[-1] not in sk:
                        continue
                    if h not in started and _is_started_signal(raw):
                        started.add(h)
                        logger.info("[ORCH] saw %s start review work", h.split("/")[-1])
                    if got[h] is None and _is_text(raw):
                        content = _content(raw)
                        if not _is_usable_report(h, content):
                            logger.info("[ORCH] ignored incomplete report from %s", h.split("/")[-1])
                            continue
                        got[h] = content
                        logger.info("[ORCH] collected current-round report from %s", h.split("/")[-1])

            missing = [h for h, v in got.items() if v is None]
            not_started = [h for h in missing if h not in started]
            wait_for = (
                FIRST_RETRIGGER_AFTER if not_started and triggers == 0
                else RETRIGGER_AFTER if not_started
                else STARTED_RETRIGGER_AFTER
            )
            if missing and (time.monotonic() - last) > wait_for:
                triggers += 1
                targets = not_started or missing
                if triggers > MAX_RETRIGGERS:
                    logger.warning("[ORCH] giving up on %s after %d re-triggers",
                                   missing, MAX_RETRIGGERS)
                    break
                last = time.monotonic()
                logger.info("[ORCH] re-triggering (attempt %d) for %s",
                            triggers, targets)
                try:
                    await ask_again(targets)
                except Exception:
                    logger.warning("[ORCH] re-trigger failed", exc_info=True)
        return got

    async def _synthesize(self, reports) -> str:
        missing = [h.split("/")[-1] for h, t in reports.items() if not t]
        joined = "\n\n".join(
            f"## {h.split('/')[-1]}\n{(t or '(no report received)')}" for h, t in reports.items()
        )
        prompt = (
            "You are the lead code reviewer. Below are the specialist reviewers' reports "
            "for a pull request. Write ONE final verdict for the human. Aggregate their "
            "findings; do not invent new ones. If two reviewers report the SAME underlying "
            "issue (for example both flag the SQL injection), MERGE it into a single finding "
            "and keep the HIGHEST severity. If a report says '(no report received)', "
            "note that reviewer was unavailable. You MUST choose ESCALATE_TO_HUMAN "
            "if any specialist report is missing or unavailable. Do not mention missing, absent, "
            "or unavailable reports unless a section literally says '(no report received)'.\n\n"
            f"{joined}\n\n"
            "Reply EXACTLY in this shape:\n"
            "DECISION: APPROVE or REQUEST_CHANGES or ESCALATE_TO_HUMAN "
            "(choose ESCALATE_TO_HUMAN if any finding is CRITICAL or any report is missing)\n"
            "FINDINGS: each DISTINCT finding exactly once, one per line (merge duplicates)\n"
            "REMEDIATION: one line noting the fixes and tests the crew provided\n"
            "RATIONALE: 2-3 plain sentences."
        )
        resp = await self.llm.ainvoke(prompt)
        body = resp.content if hasattr(resp, "content") else str(resp)
        if missing:
            body = self._force_missing_report_escalation(body, missing)
        return f"@{HUMAN} here is the crew's verdict:\n{body}"

    @staticmethod
    def _force_missing_report_escalation(body: str, missing: list[str]) -> str:
        """Safety rail: a missing specialist report is a human-escalation event.

        The Lead LLM should follow the prompt, but the demo cannot silently downgrade
        a missing Security report into an ordinary request-changes decision.
        """
        lines = str(body).splitlines()
        for i, line in enumerate(lines):
            if line.strip().upper().startswith("DECISION:"):
                lines[i] = "DECISION: ESCALATE_TO_HUMAN"
                break
        else:
            lines.insert(0, "DECISION: ESCALATE_TO_HUMAN")

        lowered = "\n".join(lines).lower()
        if "no report received" not in lowered and "unavailable" not in lowered:
            unavailable = ", ".join(missing)
            lines.append(
                f"RATIONALE: Missing specialist report(s): {unavailable}. "
                "Human review is required before merge."
            )
        return "\n".join(lines)
