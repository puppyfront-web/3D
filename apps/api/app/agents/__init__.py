"""Agents package — VisualConceptAgent for multi-turn workflows.

VisualConceptAgent (visual_concept.py):
  COLLECTING → PLANNING → PROMPTING → GENERATING → REVIEWING → COMPLETED
  Handles visual concept generation with version tree and branching.

The legacy ProposalAgent state machine was removed — the canvas orchestrator
(app.services.canvas_agent_orchestrator) is now the single planning path:
intent=sop_pipeline routes to _handle_auto_fill → fill_canvas, which runs the
planner → consistency → tone → ui_expert stages. Per-skill requests still go
through the Skill Runtime (proposal_generation skill), not a dedicated agent.

Agents are stateless — per-conversation state lives in Context objects
serialized into Message.metadata_json.
"""
