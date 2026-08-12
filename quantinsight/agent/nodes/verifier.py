import logging
from datetime import datetime, timezone
from typing import Any

from quantinsight.agent.llm import call_groq, extract_json, is_mock_enabled
from quantinsight.agent.state import GraphState
from quantinsight.schemas.models import AgentTraceStep

logger = logging.getLogger(__name__)


async def verifier_node(state: GraphState | dict[str, Any]) -> dict[str, Any]:
    """
    Verifier node: Performs self-correction by checking the draft answer
    against retrieved evidence, determining if revision is needed.
    """
    # Extract state fields robustly (handles both Pydantic model and dict)
    query = state.query if hasattr(state, "query") else state.get("query", "")
    retrieved_chunks = (
        state.retrieved_chunks
        if hasattr(state, "retrieved_chunks")
        else state.get("retrieved_chunks", [])
    )
    retrieved_tables = (
        state.retrieved_tables
        if hasattr(state, "retrieved_tables")
        else state.get("retrieved_tables", [])
    )
    retrieved_equations = (
        state.retrieved_equations
        if hasattr(state, "retrieved_equations")
        else state.get("retrieved_equations", [])
    )
    draft_answer = (
        state.draft_answer
        if hasattr(state, "draft_answer")
        else state.get("draft_answer", "")
    )
    revision_count = (
        state.revision_count
        if hasattr(state, "revision_count")
        else state.get("revision_count", 0)
    )
    trace = state.trace if hasattr(state, "trace") else state.get("trace", [])

    step_index = len(trace)

    # Format and truncate the evidence to prevent Verifier context overflow
    evidence_parts = []
    for chunk in retrieved_chunks[:8]:  # Limit to top 8 prose chunks
        evidence_parts.append(
            f"--- PROSE CHUNK ID: {chunk.id} ---\n{chunk.content}"
        )
    for table in retrieved_tables[:4]:  # Limit to top 4 tables
        evidence_parts.append(
            f"--- TABLE ID: {table.chunk_id} ---\n"
            f"Caption: {table.caption or ''}\n"
            f"Headers: {table.headers}\n"
            f"Rows: {table.rows}"
        )
    for eq in retrieved_equations[:4]:  # Limit to top 4 equations
        evidence_parts.append(
            f"--- EQUATION ID: {eq.chunk_id} ---\n"
            f"Latex: {eq.latex}\n"
            f"Context: {eq.surrounding_context}"
        )
    evidence_text = "\n\n".join(evidence_parts)
    if len(evidence_text) > 10000:
        evidence_text = evidence_text[:10000] + "\n... [Evidence truncated for verification]"

    system_prompt = (
        "You are the Verifier node in an agentic RAG system for research papers.\n"
        "Your task is to self-check a draft answer against the retrieved evidence.\n\n"
        "Critique criteria:\n"
        "1. Is every factual claim, number, or equation in the draft answer fully supported by the provided evidence?\n"
        "2. Are there any contradictions or unsupported extrapolations between the draft answer and the evidence?\n"
        "3. Does the draft answer correctly cite the supporting chunk IDs using the format [UUID]?\n"
        "4. Are there any claims without any citations?\n"
        "5. If the draft answer correctly states that no supporting evidence was found (and thus contains no citations), and the evidence indeed does not support the query, then this is correct. In this case, 'needs_revision' MUST be false.\n\n"
        "You MUST respond ONLY with a JSON object matching this schema:\n"
        "{\n"
        '  "needs_revision": boolean,\n'
        '  "verification_notes": [\n'
        '    "note 1 describing what is missing, incorrect, or contradictory",\n'
        '    "note 2 ..."\n'
        "  ]\n"
        "}"
    )

    user_prompt = (
        f"User Query: {query}\n\n"
        f"Draft Answer under verification:\n{draft_answer}\n\n"
        f"Retrieved Evidence:\n{evidence_text}"
    )

    if is_mock_enabled():
        logger.info("Verifier: using mock verifier response.")
        if "revise" in query.lower() and revision_count == 0:
            needs_revision = True
            verification_notes = ["Mock revision requested because query contains 'revise'."]
        else:
            needs_revision = False
            verification_notes = ["Mock verification: Draft answer is fully supported by the evidence."]
    else:
        try:
            raw_response = await call_groq(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_json=True,
            )
            data = extract_json(raw_response)
            needs_revision = bool(data.get("needs_revision", False))
            verification_notes = data.get("verification_notes", [])
            if not isinstance(verification_notes, list):
                verification_notes = [str(verification_notes)]
        except Exception as e:
            logger.error(f"Verifier failed to call LLM: {e}")
            needs_revision = False
            verification_notes = [f"⚠️ DEGRADED VERIFICATION MODE: Verifier check bypassed due to API error ({e}). Draft accepted without verification."]

    # Record trace step
    trace_step = AgentTraceStep(
        step_index=step_index,
        node_name="Verifier",
        input_summary=f"Verifying draft answer (length: {len(draft_answer)}).",
        output_summary=f"Needs revision: {needs_revision}. Notes: {verification_notes}",
        tool_calls=[],
        timestamp=datetime.now(timezone.utc),
    )

    return {
        "needs_revision": needs_revision,
        "verification_notes": verification_notes,
        "revision_count": revision_count + 1 if needs_revision else revision_count,
        "trace": list(trace) + [trace_step],
    }
