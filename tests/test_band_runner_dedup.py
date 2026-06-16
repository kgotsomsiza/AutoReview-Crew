import unittest

from band_runner import _DedupTools


class FakeTools:
    def __init__(self):
        self.calls = 0

    async def execute_tool_call(self, tool_name, arguments):
        self.calls += 1
        return "real send result"


class DedupToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_reviewer_retry_after_retrigger_window_is_allowed(self):
        inner = FakeTools()
        state = {"_last_ok": 100.0}
        tools = _DedupTools(inner, state, reviewer_mode=True, trigger_id="new-trigger")

        import band_runner

        old_monotonic = band_runner.time.monotonic
        try:
            band_runner.time.monotonic = lambda: 130.0
            result = await tools.execute_tool_call("band_send_message", {"content": "report"})
        finally:
            band_runner.time.monotonic = old_monotonic

        self.assertEqual(result, "real send result")
        self.assertEqual(inner.calls, 1)

    async def test_reviewer_near_simultaneous_duplicate_is_suppressed(self):
        inner = FakeTools()
        state = {"_last_ok": 100.0}
        tools = _DedupTools(inner, state, reviewer_mode=True, trigger_id="same-trigger")

        import band_runner

        old_monotonic = band_runner.time.monotonic
        try:
            band_runner.time.monotonic = lambda: 101.0
            result = await tools.execute_tool_call("band_send_message", {"content": "report"})
        finally:
            band_runner.time.monotonic = old_monotonic

        self.assertEqual(result, "Message sent.")
        self.assertEqual(inner.calls, 0)

    async def test_reviewer_second_send_for_same_trigger_is_suppressed(self):
        inner = FakeTools()
        state = {"_sent_by_trigger": {"same-trigger": True}}
        tools = _DedupTools(inner, state, reviewer_mode=True, trigger_id="same-trigger")

        result = await tools.execute_tool_call("band_send_message", {"content": "No further issues."})

        self.assertEqual(result, "Message sent.")
        self.assertEqual(inner.calls, 0)

    async def test_reviewer_new_trigger_after_sent_trigger_is_allowed(self):
        inner = FakeTools()
        state = {"_sent_by_trigger": {"old-trigger": True}, "_last_ok": 100.0}
        tools = _DedupTools(inner, state, reviewer_mode=True, trigger_id="new-trigger")

        import band_runner

        old_monotonic = band_runner.time.monotonic
        try:
            band_runner.time.monotonic = lambda: 130.0
            result = await tools.execute_tool_call("band_send_message", {"content": "retry report"})
        finally:
            band_runner.time.monotonic = old_monotonic

        self.assertEqual(result, "real send result")
        self.assertEqual(inner.calls, 1)

    async def test_incomplete_test_report_is_rejected_until_two_pytest_functions(self):
        inner = FakeTools()
        state = {}
        tools = _DedupTools(
            inner, state, reviewer_mode=True,
            trigger_id="test-trigger", agent_key="test_reviewer",
        )

        incomplete = await tools.execute_tool_call(
            "band_send_message", {"content": "[TESTS] verdict - missing tests"}
        )
        complete = await tools.execute_tool_call(
            "band_send_message",
            {
                "content": (
                    "[TESTS] verdict - missing tests\n"
                    "def test_empty_orders_returns_zero():\n    assert True\n"
                    "def test_refunds_do_not_share_default_list():\n    assert True"
                )
            },
        )

        self.assertIn("Message not sent", incomplete)
        self.assertEqual(complete, "real send result")
        self.assertEqual(inner.calls, 1)


if __name__ == "__main__":
    unittest.main()
