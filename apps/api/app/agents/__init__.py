"""Agents package — ProposalAgent and VisualConceptAgent for multi-turn workflows.

ProposalAgent (proposal.py):
  COLLECTING → ANALYZING → GENERATING → REVIEWING → COMPLETED
  Handles company analysis + RAG retrieval + proposal generation with
  multi-turn interaction, quality self-check, and human review.

VisualConceptAgent (visual_concept.py):
  COLLECTING → PLANNING → PROMPTING → GENERATING → REVIEWING → COMPLETED
  Handles visual concept generation with version tree and branching.

Both agents are stateless — per-conversation state lives in Context objects
serialized into Message.metadata_json.
"""
