import unittest
import asyncio
from datetime import datetime, timezone

import lead_orchestrator as orch
from band.testing.fake_tools import FakeAgentTools
from lead_orchestrator import CORRECTNESS, SECURITY, LeadOrchestratorAdapter


class StubLLM:
    def __init__(self, content):
        self.content = content
        self.prompt = None

    async def ainvoke(self, prompt):
        self.prompt = prompt

        class Resp:
            pass

        resp = Resp()
        resp.content = self.content
        return resp


class LeadOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_active_review_event_wraps_round(self):
        event = asyncio.Event()
        adapter = LeadOrchestratorAdapter(
            llm=None, post_review_fn=lambda _text: "", active_review_event=event)
        seen = []

        async def fake_run_round(_tools, _room_id, _since):
            seen.append(event.is_set())

        adapter._run_round = fake_run_round

        class Msg:
            sender_type = "User"
            content = "please review"
            created_at = datetime(2026, 6, 14, 18, 30, tzinfo=timezone.utc)

        await adapter.on_message(
            Msg(), None, None, None, None, is_session_bootstrap=False, room_id="room-1")

        self.assertEqual(seen, [True])
        self.assertFalse(event.is_set())

    async def test_collect_ignores_stale_reports_and_reads_all_pages(self):
        adapter = LeadOrchestratorAdapter(llm=None, post_review_fn=lambda _text: "")
        since = datetime(2026, 6, 14, 11, 0, tzinfo=timezone.utc)

        stale = [
            {
                "sender_name": "Security Reviewer",
                "content": "stale security report from a previous room run",
                "inserted_at": "2026-06-14T10:00:00+00:00",
            }
            for _ in range(100)
        ]
        fresh = [
            {
                "sender_name": "Correctness Reviewer",
                "content": "fresh correctness report",
                "inserted_at": "2026-06-14T11:01:00+00:00",
            },
            {
                "sender_name": "Security Reviewer",
                "content": '{"name": "get_code_change"}',
                "message_type": "tool_call",
                "inserted_at": "2026-06-14T11:01:01+00:00",
            },
            {
                "sender_name": "Security Reviewer",
                "content": "fresh security report",
                "message_type": "text",
                "inserted_at": "2026-06-14T11:01:05+00:00",
            },
        ]
        tools = FakeAgentTools(room_context=stale + fresh)

        old_poll = orch.POLL_INTERVAL
        orch.POLL_INTERVAL = 0
        try:
            reports = await adapter._collect(
                tools,
                "room-1",
                [CORRECTNESS, SECURITY],
                ask_again=lambda _missing: self.fail("should not re-trigger"),
                since=since,
            )
        finally:
            orch.POLL_INTERVAL = old_poll

        self.assertEqual(reports[CORRECTNESS], "fresh correctness report")
        self.assertEqual(reports[SECURITY], "fresh security report")
        self.assertGreaterEqual(len(tools.context_calls), 2)

    async def test_started_reviewer_is_not_retriggered_before_started_timeout(self):
        adapter = LeadOrchestratorAdapter(llm=None, post_review_fn=lambda _text: "")
        since = datetime(2026, 6, 14, 13, 50, tzinfo=timezone.utc)
        tools = FakeAgentTools(room_context=[
            {
                "sender_name": "Security Reviewer",
                "content": '{"name": "get_code_change"}',
                "message_type": "tool_call",
                "inserted_at": "2026-06-14T13:50:50+00:00",
            },
            {
                "sender_name": "Security Reviewer",
                "content": "fresh security report",
                "message_type": "text",
                "inserted_at": "2026-06-14T13:51:20+00:00",
            },
        ])

        old_poll = orch.POLL_INTERVAL
        old_first = orch.FIRST_RETRIGGER_AFTER
        orch.POLL_INTERVAL = 0
        orch.FIRST_RETRIGGER_AFTER = 0
        try:
            reports = await adapter._collect(
                tools,
                "room-1",
                [SECURITY],
                ask_again=lambda _missing: self.fail("started reviewer should not re-trigger"),
                since=since,
            )
        finally:
            orch.POLL_INTERVAL = old_poll
            orch.FIRST_RETRIGGER_AFTER = old_first

        self.assertEqual(reports[SECURITY], "fresh security report")

    async def test_missing_report_forces_human_escalation(self):
        llm = StubLLM(
            "DECISION: REQUEST_CHANGES\n"
            "FINDINGS: correctness finding\n"
            "REMEDIATION: fix it\n"
            "RATIONALE: normal request changes."
        )
        adapter = LeadOrchestratorAdapter(llm=llm, post_review_fn=lambda _text: "")

        verdict = await adapter._synthesize({
            CORRECTNESS: "HIGH average_order_value - Division by zero.",
            SECURITY: None,
        })

        self.assertIn("DECISION: ESCALATE_TO_HUMAN", verdict)
        self.assertIn("security-reviewer", verdict)
        self.assertIn("any report is missing", llm.prompt)

    async def test_synthesis_prompt_blocks_false_missing_report_rationale(self):
        llm = StubLLM(
            "DECISION: ESCALATE_TO_HUMAN\n"
            "FINDINGS: critical security finding\n"
            "REMEDIATION: fix it\n"
            "RATIONALE: critical finding requires human review."
        )
        adapter = LeadOrchestratorAdapter(llm=llm, post_review_fn=lambda _text: "")

        await adapter._synthesize({
            CORRECTNESS: "HIGH average_order_value - Division by zero.",
            SECURITY: "CRITICAL Hardcoded Stripe API Key.",
            orch.TEST: "[TESTS] verdict - Missing tests.\ndef test_one(): pass\ndef test_two(): pass",
        })

        self.assertIn("Do not mention missing, absent, or unavailable reports", llm.prompt)
        report_block = "## " + llm.prompt.split("\n\n## ", 1)[1].split("\n\nReply EXACTLY", 1)[0]
        self.assertNotIn("(no report received)", report_block)

    async def test_collect_waits_for_complete_test_report(self):
        adapter = LeadOrchestratorAdapter(llm=None, post_review_fn=lambda _text: "")
        since = datetime(2026, 6, 14, 13, 20, tzinfo=timezone.utc)
        tools = FakeAgentTools(room_context=[
            {
                "sender_name": "Test Reviewer",
                "content": "@Lead Reviewer [TESTS] verdict - Missing tests.",
                "inserted_at": "2026-06-14T13:21:00+00:00",
            },
            {
                "sender_name": "Test Reviewer",
                "content": (
                    "def test_empty_orders_returns_zero():\n"
                    "    assert average_order_value([]) == 0\n"
                    "def test_refunds_do_not_share_default_list():\n"
                    "    assert record_refund(10) is not record_refund(20)"
                ),
                "inserted_at": "2026-06-14T13:21:03+00:00",
            },
        ])

        old_poll = orch.POLL_INTERVAL
        orch.POLL_INTERVAL = 0
        try:
            reports = await adapter._collect(
                tools,
                "room-1",
                [orch.TEST],
                ask_again=lambda _missing: self.fail("should not re-trigger"),
                since=since,
            )
        finally:
            orch.POLL_INTERVAL = old_poll

        self.assertIn("def test_empty_orders_returns_zero", reports[orch.TEST])


if __name__ == "__main__":
    unittest.main()
