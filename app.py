"""Streamlit companion demo for AutoReview Crew.

This app is intentionally simulation-only: it gives judges an always-on
Application URL without requiring Band credentials, provider keys, or the
developer's laptop. The real Band run is shown in the video; this app explains
and replays the same workflow safely.
"""
from __future__ import annotations

import time

import streamlit as st


TRANSCRIPT = [
    ("13:02:23", "Lead Reviewer", "Delegates once to Correctness and Security.",
     """@Correctness Reviewer @Security Reviewer please review the latest code change now."""),
    ("13:02:33", "Correctness Reviewer", "Flags division by zero and a mutable default argument.",
     """@Lead Reviewer [HIGH] Division by zero in average_order_value - divides by len(orders) with no empty-list check.
FIX: if not orders: return 0

[HIGH] Mutable default argument in record_refund - default list refunds is shared across calls.
FIX: def record_refund(amount, refunds=None):
if refunds is None:
refunds = []
refunds.append(amount)
return refunds"""),
    ("13:02:48", "Security Reviewer", "Flags a hardcoded Stripe API key, SQL injection, and missing input validation.",
     """@Lead Reviewer [CRITICAL] Hardcoded Stripe API key - a live secret is committed in the source.
FIX: load it from an environment variable: STRIPE_API_KEY = os.environ["STRIPE_KEY"]

[HIGH] SQL Injection vulnerability - user input is directly used in SQL query.
FIX: use parameterized queries: cursor.execute("SELECT * FROM charges WHERE user_id = ?", (user_id,))

[MEDIUM] Missing input validation - no checks on the orders parameter in average_order_value.
FIX: validate orders is a non-empty list of dictionaries with an 'amount' key: assert isinstance(orders, list) and all(isinstance(o, dict) and 'amount' in o for o in orders)

[LOW] Potential side-effect in record_refund - modifying a default mutable argument.
FIX: use None as the default and initialize inside the function: def record_refund(amount, refunds=None): refunds = refunds or []"""),
    ("13:02:55", "Lead Reviewer", "Recruits the Test Reviewer because no decision is allowed without test coverage.",
     """@Test Reviewer please review the test coverage for the latest code change now."""),
    ("13:03:08", "Test Reviewer", "Posts pytest coverage for empty orders, SQL injection, and mutable defaults.",
     """@Lead Reviewer [TESTS] verdict - Missing tests for empty order list, SQL injection, and mutable default argument.

import sqlite3
import pytest
from payments import average_order_value, get_user_charges, record_refund

def test_average_order_value_empty_list_returns_zero():
    # Test that an empty list of orders returns 0 to avoid ZeroDivisionError.
    assert average_order_value([]) == 0

def test_get_user_charges_prevents_sql_injection():
    # Test that SQL injection attempts are blocked by parameterized queries.
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE charges (user_id TEXT, amount REAL)")
    cursor.execute("INSERT INTO charges VALUES ('user1', 100.0)")
    conn.commit()
    injected_user_id = "user1' OR '1'='1"
    assert len(get_user_charges(conn, injected_user_id)) == 0
    conn.close()

def test_record_refund_mutable_default_is_handled():
    # Test that the default 'refunds' list is not shared across calls.
    first_refunds = record_refund(10)
    second_refunds = record_refund(20)
    assert first_refunds == [10]
    assert second_refunds == [20]
    assert first_refunds is not second_refunds"""),
    ("13:03:13", "Lead Reviewer", "Escalates to the human owner with all findings aggregated.",
     """@Kgotso Msiza here is the crew's verdict:
DECISION: ESCALATE_TO_HUMAN
FINDINGS:
[CRITICAL] Hardcoded Stripe API key - a live secret is committed in the source.
[HIGH] Division by zero in average_order_value - divides by len(orders) with no empty-list check.
[HIGH] SQL Injection vulnerability - user input is directly used in SQL query.
[HIGH] Mutable default argument in record_refund - default list refunds is shared across calls.
[MEDIUM] Missing input validation - no checks on the orders parameter in average_order_value.

REMEDIATION: Implement environment variable for API key, add checks for empty lists, use parameterized queries, and handle mutable defaults. Tests for these issues are provided.

RATIONALE: The presence of a critical security issue with the hardcoded API key necessitates human intervention. Additionally, the high-severity issues related to division by zero, SQL injection, and mutable default arguments require immediate attention. The provided tests address these concerns, but human oversight is essential to ensure comprehensive resolution."""),
]

AGENTS = [
    ("Lead Reviewer", "Coordinates, recruits, decides", "gpt-4o", "AI/ML API"),
    ("Correctness Reviewer", "Logic bugs and edge cases", "gemini-2.5-flash", "AI/ML API"),
    ("Security Reviewer", "Secrets and vulnerabilities", "Qwen2.5-72B", "Featherless AI"),
    ("Test Reviewer", "Test gaps and pytest suggestions", "Gemini 2.5 Flash", "AI/ML API"),
]

FINDINGS = [
    ("CRITICAL", "Hardcoded Stripe API key", "Store secrets in environment variables or a vault."),
    ("HIGH", "SQL injection in get_user_charges", "Use parameterized SQL queries."),
    ("HIGH", "Division by zero in average_order_value", "Return 0 or a safe value for an empty order list."),
    ("MEDIUM", "Mutable default argument in record_refund", "Use None, then allocate a new list per call."),
    ("LOW", "Missing input validation for refunds", "Reject non-positive refund amounts."),
    ("TESTS", "Coverage missing for risky paths", "Add pytest tests for the fixes above."),
]


def card(title: str, body: str, accent: str = "#14b8a6") -> None:
    st.markdown(
        f"""
        <div class="card" style="border-top-color:{accent}">
          <h3>{title}</h3>
          <p>{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="AutoReview Crew", page_icon="AC", layout="wide")

st.markdown(
    """
    <style>
      .stApp { background: #f7fbfa; color: #0b3b40; }
      .hero {
        background: #06343d;
        color: white;
        padding: 34px 38px;
        border-radius: 8px;
        margin-bottom: 22px;
      }
      .hero h1 { margin: 0 0 10px 0; font-size: 46px; letter-spacing: 0; }
      .hero p { margin: 0; color: #b8ebe4; font-size: 20px; max-width: 920px; }
      .card {
        background: white;
        border-radius: 8px;
        border-top: 5px solid #14b8a6;
        padding: 18px 18px 16px 18px;
        box-shadow: 0 8px 24px rgba(6, 52, 61, 0.08);
        min-height: 138px;
      }
      .card h3 { margin: 0 0 8px 0; font-size: 18px; color: #06343d; }
      .card p { margin: 0; line-height: 1.45; color: #33524f; }
      .pill {
        display: inline-block;
        background: #dff8f4;
        color: #0b6f68;
        padding: 5px 9px;
        border-radius: 999px;
        font-size: 13px;
        margin-right: 6px;
      }
      .danger { color: #b4232a; font-weight: 700; }
      .ok { color: #0b6f68; font-weight: 700; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="hero">
      <h1>AutoReview Crew</h1>
      <p>Four AI agents review a code change together in Band, recruit a test specialist mid-review, and escalate risky changes to a human before merge.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(["Live Run Replay", "Crew", "Findings", "Architecture"])

with tabs[0]:
    st.subheader("Recorded take: June 15, 2026, 13:02 UTC")
    st.write("This replay mirrors the real Band transcript used for the demo video - expand any line to read the exact message the agent posted. The live system runs through `run_crew.py`; this app is a safe no-key companion.")
    speed = st.slider("Replay speed", min_value=0.0, max_value=1.0, value=0.25, step=0.05)
    if st.button("Replay the review", type="primary"):
        for timestamp, speaker, message, full in TRANSCRIPT:
            with st.chat_message("assistant" if speaker != "Lead Reviewer" else "user"):
                st.caption(timestamp)
                st.markdown(f"**{speaker}**")
                st.write(message)
                with st.expander("Full message the agent posted in the room"):
                    st.code(full, language="text")
            time.sleep(speed)
        st.success("Decision: ESCALATE_TO_HUMAN. All specialist reports arrived before the Lead finalized.")
    else:
        for timestamp, speaker, message, full in TRANSCRIPT:
            st.markdown(f"**{timestamp} - {speaker}:** {message}")
            with st.expander("Full message the agent posted in the room"):
                st.code(full, language="text")

with tabs[1]:
    st.subheader("The agents")
    cols = st.columns(4)
    for col, (name, role, model, provider) in zip(cols, AGENTS):
        with col:
            card(name, f"{role}<br><br><span class='pill'>{model}</span><span class='pill'>{provider}</span>")
    st.info("The Test Reviewer is not needed at room start. The Lead discovers and recruits it when the quality gate requires test coverage.")

with tabs[2]:
    st.subheader("What the crew caught")
    for severity, title, remediation in FINDINGS:
        color = "#f96167" if severity in {"CRITICAL", "HIGH"} else "#14b8a6"
        card(f"{severity}: {title}", remediation, accent=color)

with tabs[3]:
    st.subheader("How the system is wired")
    col1, col2 = st.columns(2)
    with col1:
        card("Band is the coordination layer", "Assignments, reports, recruitment, shared context, and human escalation all happen through Band room messages and platform tools.")
        card("Deterministic Lead coordination", "The Lead waits for current-round reports, ignores stale context, recruits Test only when needed, and escalates risky changes.")
    with col2:
        card("Cross-provider reviewers", "AI/ML API powers the Lead, Correctness, and Test agents; Featherless powers the Security Reviewer with Qwen2.5-72B.")
        card("Human-in-the-loop merge gate", "The crew does not approve risky code silently. Critical findings are aggregated and sent back to the human owner.")

