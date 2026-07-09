# Plan: wx Orchestrate Integration

## Top-Level Overview

Add IBM Watsonx Orchestrate as an optional orchestration runtime alongside LangGraph.
When `ORCHESTRATOR=wxorchestrate` is set in `.env`, the three agents (tutorial, news, validator) are
deployed to the Watsonx Orchestrate platform as registered skills/tools, and the platform manages
routing and the validator revision loop. When the env var is absent or set to `langgraph`, the
existing LangGraph pipeline runs exactly as today — no behaviour change.

The approach is:
1. Extend settings to capture the orchestrator choice and any wx Orchestrate credentials.
2. Expose each agent node as a decorated `@tool` skill compatible with the `ibm-watsonx-orchestrate` SDK.
3. Write a wx Orchestrate runner that registers the skills, defines the routing flow, and invokes the pipeline.
4. Wire the entrypoint (`run.py`) to branch between the LangGraph runner and the wx Orchestrate runner based on the setting.

---

## Sub-Tasks

---

### Sub-task 1 — Extend Settings & Dependencies

**Intent**
Capture the orchestrator choice and wx Orchestrate-specific credentials in settings so
the rest of the codebase can read them cleanly. Add the SDK as an optional dependency.

**Expected Outcomes**
- `Settings` has a new `ORCHESTRATOR` field (default `"langgraph"`, accepts `"wxorchestrate"`).
- `WatsonxOrchestrateSettings` has any extra fields needed (e.g. `SPACE_ID`, `INSTANCE_URL`) beyond what `WatsonxSettings` already has.
- `ibm-watsonx-orchestrate` added as an optional dependency in `pyproject.toml`.
- Existing behaviour when `ORCHESTRATOR` is unset is completely unchanged.

**Todo List**
1. Research the exact credential fields required by `ibm-watsonx-orchestrate` SDK at runtime (API key, project_id, URL, and whether a `space_id` is also needed).
2. Add a `WatsonxOrchestrateSettings` model to `blogboard/config/settings.py` (reuse `watsonx.*` fields where possible to avoid duplication).
3. Add `ORCHESTRATOR: str = "langgraph"` to the top-level `Settings` model.
4. Add `ibm-watsonx-orchestrate` to `[project.optional-dependencies]` in `pyproject.toml` under an `orchestrate` extras group.

**Relevant Context**
- `blogboard/config/settings.py` — `WatsonxSettings`, `Settings`
- `pyproject.toml` — existing dependency declarations

**Status**: [ ] pending

---

### Sub-task 2 — Define Skill Wrappers for Each Agent

**Intent**
Wrap each of the three existing agent node functions as wx Orchestrate skills.
The skills must accept and return data compatible with `BlogState` so the platform can
pass state between them. Each wrapper is a thin adapter — the underlying node logic
(`tutorial_node`, `news_node`, `validator_node`) is not changed.

**Expected Outcomes**
- New file `blogboard/orchestrate/skills.py` containing three skill-decorated functions:
  `tutorial_skill`, `news_skill`, `validator_skill`.
- Each skill accepts a `BlogState`-shaped dict as input and returns an updated dict.
- Skills are importable without side effects (no LangGraph import required when this module is loaded).

**Todo List**
1. Create `blogboard/orchestrate/` package directory with `__init__.py`.
2. Create `blogboard/orchestrate/skills.py` — import the three node functions and wrap each
   with the `@tool` / skill decorator from `ibm-watsonx-orchestrate` SDK.
3. Ensure the skill signatures accept a plain dict (or typed Pydantic model) matching `BlogState` fields.
4. Verify no circular imports are introduced (skills.py must not import from `blogboard.graph`).

**Relevant Context**
- `blogboard/agents/tutorial_agent/agent.py` — `tutorial_node`
- `blogboard/agents/news_agent/agent.py` — `news_node`
- `blogboard/agents/validator_agent/agent.py` — `validator_node`
- `blogboard/graph/state.py` — `BlogState` TypedDict

**Status**: [ ] pending

---

### Sub-task 3 — Write the wx Orchestrate Runner

**Intent**
Implement a runner module that registers the three skills with the wx Orchestrate platform,
defines the routing flow (domain routing + validator revision loop), and invokes the pipeline —
mirroring the same control flow that `blogboard/graph/graph.py` implements in LangGraph.

**Expected Outcomes**
- New file `blogboard/orchestrate/runner.py` with a single `run(initial_state: dict) -> dict` function.
- The function registers skills, constructs the wx Orchestrate pipeline/flow, runs it, and returns the final state dict.
- Routing logic mirrors `_route_start` and `_route_after_validator` from `graph.py`.
- Credentials are read from `app_settings.watsonx_orchestrate`.

**Todo List**
1. Research the `ibm-watsonx-orchestrate` SDK's `Pipeline`/`Flow` construction API (add_node, add_edge, conditional routing, compile, run).
2. Implement `runner.py`:
   - Authenticate using settings.
   - Register `tutorial_skill`, `news_skill`, `validator_skill`.
   - Define routing: START → domain router → tutorial or news → validator → revision loop or END.
   - Invoke the pipeline with `initial_state` and return the result dict.
3. Add a `__init__.py` export so callers import `from blogboard.orchestrate import run`.

**Relevant Context**
- `blogboard/graph/graph.py` — `_route_start`, `_route_after_validator`, `build_graph` (exact logic to replicate)
- `blogboard/orchestrate/skills.py` — skills defined in sub-task 2
- `blogboard/config/settings.py` — credentials

**Status**: [ ] pending

---

### Sub-task 4 — Wire the Entrypoint

**Intent**
Make `run.py` check the `ORCHESTRATOR` setting and delegate to either the existing LangGraph
graph or the new wx Orchestrate runner. No LangGraph code changes; the branch is purely in
the entrypoint.

**Expected Outcomes**
- `blogboard/run.py` imports and calls `from blogboard.orchestrate import run as orchestrate_run` only when `ORCHESTRATOR=wxorchestrate`.
- Default path (LangGraph) is completely unchanged.
- The final summary printed to console is identical regardless of which runner was used.

**Todo List**
1. In `run.py`, after loading settings, read `app_settings.ORCHESTRATOR`.
2. Add an `if/else` branch: if `"wxorchestrate"`, call `orchestrate_run(initial_state)` and assign to `final_state`; otherwise call `graph.invoke(...)` as today.
3. Guard the LangGraph import (`from blogboard.graph.graph import graph`) inside the `else` branch so that `ibm-watsonx-orchestrate` users do not need LangGraph installed.
4. Confirm that `final_state` from both paths has the same keys used in the summary block (`domain`, `title`, `md_path`, `read_time`, `topic`, `slug`).

**Relevant Context**
- `blogboard/run.py` — existing entrypoint, summary block lines 98–118
- `blogboard/orchestrate/runner.py` — runner from sub-task 3

**Status**: [ ] pending

---

### Sub-task 5 — Documentation & .env Example

**Intent**
Document the new option so it is clear how to switch between runtimes.

**Expected Outcomes**
- `README.md` (or a new `ORCHESTRATE.md` if no README exists) has a section explaining the `ORCHESTRATOR` flag, required `.env` keys for wx Orchestrate, and the `uv sync --extra orchestrate` install step.
- `.env.example` (or equivalent) includes the new keys commented out.

**Todo List**
1. Check whether a `README.md` or `.env.example` file already exists at the repo root.
2. Add the wx Orchestrate configuration block to whichever doc file is appropriate.
3. List the exact `.env` variables needed: `ORCHESTRATOR`, `WATSONX_ORCHESTRATE_*` fields.

**Relevant Context**
- `pyproject.toml` — optional extras group added in sub-task 1
- `blogboard/config/settings.py` — `WatsonxOrchestrateSettings` fields

**Status**: [ ] pending
