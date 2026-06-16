"""A thin wrapper around Band - the layer your agents use to talk to each other.

WARNING: This is a SCAFFOLD. The real method bodies get filled in after you read
Band's "SDK Setup" and "Agent API" docs (and get your API key at kickoff).
Right now every method runs in "simulation mode": it just prints what it WOULD do,
so you can run and understand the whole flow before wiring up the real SDK.

During the hackathon, search this file for "TODO" to find what to replace.

------------------------------------------------------------------------------
HOW THIS FILE MAPS TO BAND'S ARCHITECTURE DIAGRAM
------------------------------------------------------------------------------
This whole class is your agents' connection to Band's INTEGRATION LAYER
(REST API + WebSocket). Each method below uses a PLATFORM CORE concept:

    join_room()              -> ROOMS       (the shared channel agents work in)
    post()                   -> MEMORY + AUDIT
    post_findings()          -> MEMORY + AUDIT
    read_findings()          -> MEMORY
    request_human_approval() -> HUMAN-IN-THE-LOOP (the "Human User" participant)

Not used yet - and good ways to score more "Band as the coordination layer"
points with the judges:
    REGISTRY  - discover what agents exist and what they can do
    CONTACTS  - invite / recruit a specific agent into the room
See the commented-out recruit_agent() idea at the bottom.
------------------------------------------------------------------------------
"""
from __future__ import annotations
from models import Finding


class BandClient:
    def __init__(self, api_key: str = "", room_id: str = "", simulate: bool = True):
        # Diagram: INTEGRATION LAYER - this is where you open the connection to
        # Band (over REST/WebSocket). Your api_key is your agent's identity.
        self.api_key = api_key
        self.room_id = room_id
        # If we don't have real credentials, stay in simulation mode no matter what.
        self.simulate = simulate or not (api_key and room_id)
        # TODO: when not simulating, create the real Band client here, e.g.:
        #   from band import Band                 # confirm import name in SDK Setup docs
        #   self._band = Band(api_key=api_key)

    def join_room(self, agent_name: str) -> None:
        """Have an agent join the shared Band room."""
        # Platform Core concept: ROOMS - the shared space where agents collaborate
        # (like a group-chat channel). All your reviewers join the SAME room.
        if self.simulate:
            print(f"  [Band] {agent_name} joined room '{self.room_id or 'demo-room'}'")
            return
        # TODO: real SDK call to join (or create) a room as `agent_name`.
        raise NotImplementedError("Wire up join_room after reading the SDK Setup docs.")

    def post(self, agent_name: str, message: str) -> None:
        """Post a plain message into the shared room so other agents can read it."""
        # Platform Core concepts: MEMORY (the message becomes shared room context
        # other agents can read) + AUDIT (every message is logged and traceable).
        if self.simulate:
            print(f"  [Band] {agent_name}: {message}")
            return
        # TODO: real SDK call to post a message to the room.
        raise NotImplementedError

    def post_findings(self, agent_name: str, findings: list[Finding]) -> None:
        """Share structured findings so the Lead can read them as context."""
        # Platform Core concepts: MEMORY (structured shared context, not just text)
        # + AUDIT (a traceable record of exactly what each agent flagged).
        if self.simulate:
            if not findings:
                print(f"  [Band] {agent_name}: no issues found")
            for f in findings:
                print(f"  [Band] {agent_name} -> [{f.severity.upper()}] {f.title}")
            return
        # TODO: real SDK call. Band can carry STRUCTURED context, not just text -
        # check the Agent API docs for the right message/context shape.
        raise NotImplementedError

    def read_findings(self) -> list[Finding]:
        """Read findings other agents posted to the room (used by the Lead)."""
        # Platform Core concept: MEMORY - reading the shared context other agents
        # wrote. This is what makes the Lead's decision genuinely collaborative.
        if self.simulate:
            # In simulation we pass findings directly in code, so nothing to fetch.
            return []
        # TODO: real SDK call to read the room's messages/context.
        raise NotImplementedError

    def request_human_approval(self, summary: str) -> None:
        """Escalate to a human (human-in-the-loop) for a risky decision."""
        # Diagram concept: HUMAN USER / human-in-the-loop - a person is just
        # another participant Band can pull into the room to make a decision.
        if self.simulate:
            print(f"  [Band] >> Escalating to a human for approval: {summary}")
            return
        # TODO: real SDK call for human-in-the-loop approval.
        raise NotImplementedError

    # ---------------------------------------------------------------------------
    # IDEA (optional, not required): use the REGISTRY + CONTACTS concepts to let an
    # agent DISCOVER and RECRUIT another agent at run time. Doing this well is a
    # strong way to show off "Band as the coordination layer" to the judges.
    #
    # def recruit_agent(self, capability: str) -> str:
    #     """Find an agent in the Registry that has `capability` and invite it
    #     into the room (Contacts). Returns the recruited agent's name/id."""
    #     # TODO: real SDK calls - search the Registry, then add the agent to the room.
    #     raise NotImplementedError
    # ---------------------------------------------------------------------------
