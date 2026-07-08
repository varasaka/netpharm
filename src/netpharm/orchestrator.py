"""Pipeline orchestrator.

Wires the ordered agents into a LangGraph StateGraph. Each node runs one agent
via its BaseAgent.execute, which itself skips work already completed (the Store
records step status and caches tables). That gives the two required properties:

  * No manual intervention after 'Run Pipeline' — the graph runs end to end.
  * Restartable from any completed step — with resume=True, done steps are
    skipped and execution continues from the first incomplete one.

LangGraph is used for the state machine + checkpointer. If LangGraph is not
installed, a plain sequential runner with identical semantics is used as a
fallback, so the pipeline is never blocked on that dependency.
"""
from __future__ import annotations

from typing import Any, Callable, TypedDict

from .agents import AGENT_SEQUENCE
from .config import Config
from .db import Store
from .logging_setup import get_logger, setup_logging

log = get_logger("orchestrator")


class PipelineState(TypedDict, total=False):
    completed: list[str]
    failed: str | None


def _make_node(agent_cls, store: Store, config: Config, force: bool) -> Callable:
    def node(state: PipelineState) -> PipelineState:
        agent = agent_cls()
        agent.execute(store, config, force=force)
        completed = list(state.get("completed", [])) + [agent.name]
        return {"completed": completed, "failed": None}
    return node


def build_graph(store: Store, config: Config, force: bool = False):
    """Construct a compiled LangGraph, or None if LangGraph is unavailable."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        log.warning("langgraph not installed — using sequential fallback runner.")
        return None

    graph = StateGraph(PipelineState)
    names = [a.name for a in AGENT_SEQUENCE]
    for agent_cls in AGENT_SEQUENCE:
        graph.add_node(agent_cls.name, _make_node(agent_cls, store, config, force))
    graph.add_edge(START, names[0])
    for a, b in zip(names, names[1:]):
        graph.add_edge(a, b)
    graph.add_edge(names[-1], END)
    return graph.compile()


def run_pipeline(config: Config, force: bool = False) -> dict[str, Any]:
    """Execute the full pipeline. Honours config.run.resume for restartability."""
    setup_logging(config.output_dir)
    store = Store(config.db_path, config.output_dir)
    resume = config.get("run", {}).get("resume", True)
    force = force or not resume

    log.info("=" * 60)
    log.info("Network Pharmacology pipeline — plant=%r disease=%r",
             config["run"]["plant"], config["run"]["disease"])
    log.info("resume=%s force=%s", resume, force)
    log.info("=" * 60)

    app = build_graph(store, config, force=force)
    if app is not None:
        final = app.invoke({"completed": []})
        completed = final.get("completed", [])
    else:
        completed = _sequential(store, config, force)

    log.info("pipeline complete — steps run: %s", ", ".join(completed))
    return {"completed": completed, "status": store.all_status().to_dict("records")}


def _sequential(store: Store, config: Config, force: bool) -> list[str]:
    completed = []
    for agent_cls in AGENT_SEQUENCE:
        agent_cls().execute(store, config, force=force)
        completed.append(agent_cls.name)
    return completed


def run_single(config: Config, step: str, force: bool = True) -> None:
    """Run just one agent by name (useful for re-running a single step)."""
    setup_logging(config.output_dir)
    store = Store(config.db_path, config.output_dir)
    for agent_cls in AGENT_SEQUENCE:
        if agent_cls.name == step:
            agent_cls().execute(store, config, force=force)
            return
    raise ValueError(f"Unknown step {step!r}. Known: {[a.name for a in AGENT_SEQUENCE]}")
