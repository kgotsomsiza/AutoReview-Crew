# AutoReview Crew

Four AI agents review a code change together in a Band room, recruit a test
specialist when they need one, and escalate risky changes to a human before
merge.

Built for the Band of Agents Hackathon, Track 2: Multi-Agent Software
Development. MIT licensed.

## What it does

You mention the Lead Reviewer in a Band room:

```text
@Lead Reviewer please review the latest code change
```

Then the crew takes over:

```text
Lead         -> asks Correctness and Security to review
Correctness  -> finds logic bugs and edge cases
Security     -> finds vulnerabilities, secrets, and unsafe patterns
Lead         -> requires test coverage before any decision
Lead         -> recruits Test Reviewer through Band
Test         -> proposes pytest coverage
Lead         -> aggregates findings and escalates to the human owner
```

The live run shown in the demo video completed in about 51 seconds. See
[SAMPLE_RUN.md](SAMPLE_RUN.md).

## Why Band matters

Band is the workflow, not a notification layer.

- Assignments happen through @mentions in the Band room.
- Reviewers report into shared room context.
- The Lead recruits the Test Reviewer with Band participant tools.
- Room events provide an audit trail of tool calls and decisions.
- The human owner is part of the room and receives the final escalation.

## The crew

| Agent | Role | Model | Provider |
| --- | --- | --- | --- |
| Lead Reviewer | Coordinates, recruits, synthesizes, escalates | gpt-4o | AI/ML API |
| Correctness Reviewer | Logic bugs and edge cases | gemini-2.5-flash | AI/ML API |
| Security Reviewer | Secrets and vulnerabilities | Qwen2.5-72B-Instruct | Featherless AI |
| Test Reviewer | Test coverage and pytest suggestions | gemini-2.5-flash | AI/ML API |

## Run it

Simulation mode works without keys:

```powershell
py main.py
```

Live Band mode requires provider keys and Band agent credentials:

```powershell
.\.venv\Scripts\python.exe run_crew.py
```

Streamlit companion app for local use:

```powershell
streamlit run app.py
```

The Streamlit app is intentionally simulation-only so the flow can be tried
without access to private credentials.

The public Application URL is hosted as a fast static companion page:
https://kgotsomsiza.github.io/AutoReview-Crew/

## Setup for live mode

1. Create a virtual environment and install dependencies.

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and add provider keys.
3. Register four external agents on Band.
4. Put Band agent credentials in `agent_config.yaml`.
5. Start the runner and leave it open while using the Band web app.

Never commit `.env`, `agent_config.yaml`, or `API keys.md`.

## Project layout

```text
run_crew.py              live entry point for Band agents
band_runner.py           Band adapter, common agent rules, dedupe guards
lead_orchestrator.py     deterministic Lead coordination
main.py                  no-key simulation entry point
app.py                   Streamlit companion demo
agents/                  role prompts and simulation functions
sample_data/             sample code change under review
tests/                   regression tests for orchestration and dedupe
deck/                    slide deck, PDF, and cover image
```

## License

MIT. See [LICENSE](LICENSE).
