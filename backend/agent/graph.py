"""LangGraph wiring: nodes, edges, and the conditional retry loop.

Topology:

    analyze_repo → run_tests → (failing → diagnose | passing → END)
        diagnose → generate_fixes → commit_fixes → monitor_ci
        monitor_ci → (loop → run_tests | end → END)

The graph is pure orchestration: it knows nothing about FastAPI, the DB, or
WebSockets. `agent_graph` is the compiled singleton callers invoke.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent.nodes.analyze import analyze_repo
from agent.nodes.commit import commit_fixes
from agent.nodes.diagnose import diagnose_failures
from agent.nodes.fix import generate_fixes
from agent.nodes.monitor_ci import monitor_ci
from agent.nodes.run_tests import run_tests_node
from agent.state import AgentState


def analyze_ok(state: AgentState) -> str:
    """Route after analyze_repo: 'stop' if setup failed, else 'continue'.

    analyze_repo sets should_stop on a clone error or unknown stack without
    populating test_command/detected_stack, so run_tests must be skipped.
    """
    return "stop" if state.get("should_stop") else "continue"


def has_failures(state: AgentState) -> str:
    """Route after run_tests: exit the loop ('passing' → END) when the tests
    are green OR run_tests asked to stop (e.g. a timeout); otherwise 'failing'.
    """
    if state.get("all_tests_passing") or state.get("should_stop"):
        return "passing"
    return "failing"


def should_stop(state: AgentState) -> str:
    """Route after monitor_ci: 'end' when the loop is done, else 'loop'."""
    return "end" if state.get("should_stop") else "loop"


def build_graph():
    """Construct and compile the agent StateGraph."""
    graph = StateGraph(AgentState)

    graph.add_node("analyze_repo", analyze_repo)
    graph.add_node("run_tests", run_tests_node)
    graph.add_node("diagnose", diagnose_failures)
    graph.add_node("generate_fixes", generate_fixes)
    graph.add_node("commit_fixes", commit_fixes)
    graph.add_node("monitor_ci", monitor_ci)

    graph.set_entry_point("analyze_repo")

    graph.add_conditional_edges(
        "analyze_repo",
        analyze_ok,
        {"continue": "run_tests", "stop": END},
    )
    graph.add_conditional_edges(
        "run_tests",
        has_failures,
        {"failing": "diagnose", "passing": END},
    )
    graph.add_edge("diagnose", "generate_fixes")
    graph.add_edge("generate_fixes", "commit_fixes")
    graph.add_edge("commit_fixes", "monitor_ci")
    graph.add_conditional_edges(
        "monitor_ci",
        should_stop,
        {"loop": "run_tests", "end": END},
    )

    return graph.compile()


agent_graph = build_graph()
