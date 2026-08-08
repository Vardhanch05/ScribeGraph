import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from quantinsight.agent.llm import call_groq, extract_json, is_mock_enabled
from quantinsight.agent.state import GraphState
from quantinsight.schemas.models import AgentTraceStep, QueryResponse

logger = logging.getLogger(__name__)


async def synthesizer_node(state: GraphState | dict[str, Any]) -> dict[str, Any]:
    """
    Synthesizer node: Generates a draft answer with citations, or packages
    the final QueryResponse depending on the execution path.
    """
    # Extract state fields robustly (handles both Pydantic model and dict)
    query = state.query if hasattr(state, "query") else state.get("query", "")
    paper_ids = (
        state.paper_ids
        if hasattr(state, "paper_ids")
        else state.get("paper_ids", [])
    )
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
        else state.get("draft_answer")
    )
    verification_notes = (
        state.verification_notes
        if hasattr(state, "verification_notes")
        else state.get("verification_notes", [])
    )
    needs_revision = (
        state.needs_revision
        if hasattr(state, "needs_revision")
        else state.get("needs_revision", False)
    )
    revision_count = (
        state.revision_count
        if hasattr(state, "revision_count")
        else state.get("revision_count", 0)
    )
    trace = state.trace if hasattr(state, "trace") else state.get("trace", [])

    step_index = len(trace)

    # Check if we are running in Final Mode or Draft Mode
    # We run in Final Mode if draft_answer is present AND (needs_revision is False OR revision_count >= 2)
    # Note: If no evidence is found, we can handle it directly.
    is_final = draft_answer is not None and (
        not needs_revision or revision_count >= 2
    )

    if not retrieved_chunks and not retrieved_tables and not retrieved_equations:
        # No evidence pathway
        no_evidence_msg = "No supporting evidence found in the ingested papers to answer this query."
        if is_final:
            final_ans = QueryResponse(
                answer=no_evidence_msg,
                citations=[],
                trace=trace,  # Will be updated below
                self_correction_applied=revision_count > 0,
                confidence_note="No retrieved chunks.",
            )
            trace_step = AgentTraceStep(
                step_index=step_index,
                node_name="Synthesizer",
                input_summary="No retrieved evidence (Final Mode)",
                output_summary="Emitted empty evidence response.",
                tool_calls=[],
                timestamp=datetime.now(timezone.utc),
            )
            final_ans.trace = list(trace) + [trace_step]
            return {
                "final_answer": final_ans,
                "trace": final_ans.trace,
            }
        else:
            trace_step = AgentTraceStep(
                step_index=step_index,
                node_name="Synthesizer",
                input_summary="No retrieved evidence (Draft Mode)",
                output_summary="Set draft answer to empty evidence message.",
                tool_calls=[],
                timestamp=datetime.now(timezone.utc),
            )
            return {
                "draft_answer": no_evidence_msg,
                "trace": list(trace) + [trace_step],
            }

    if is_final:
        # Final mode: Package the existing draft answer into QueryResponse
        # Retrieve cited IDs from the draft_answer or the state
        # Let's extract any UUIDs present in the draft_answer as citations
        import re

        uuid_pattern = re.compile(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
        )
        cited_uuids = [UUID(u) for u in uuid_pattern.findall(draft_answer)]
        # Unique citations preserving order
        unique_citations = []
        seen = set()
        for u in cited_uuids:
            if u not in seen:
                seen.add(u)
                unique_citations.append(u)

        final_ans = QueryResponse(
            answer=draft_answer,
            citations=unique_citations,
            trace=trace,  # Will be populated completely
            self_correction_applied=revision_count > 0,
            confidence_note=(
                "Answer compiled and verified."
                if revision_count == 0
                else "Answer corrected and verified."
            ),
        )

        # Update trace for final answer
        # Since this is the final step, we also want this trace step inside final_answer.trace.
        trace_step = AgentTraceStep(
            step_index=step_index,
            node_name="Synthesizer",
            input_summary=f"Finalizing draft answer. Revisions: {revision_count}",
            output_summary=f"Final answer packaged with {len(unique_citations)} citations.",
            tool_calls=[],
            timestamp=datetime.now(timezone.utc),
        )

        final_ans.trace = list(trace) + [trace_step]

        return {
            "final_answer": final_ans,
            "trace": final_ans.trace,
        }

    # Draft Mode: Call LLM to generate or revise the draft answer
    # Format the evidence
    evidence_parts = []
    valid_ids = set()

    for chunk in retrieved_chunks:
        evidence_parts.append(
            f"--- PROSE CHUNK ID: {chunk.id} (Page {chunk.page_number}) ---\n{chunk.content}"
        )
        valid_ids.add(chunk.id)

    for table in retrieved_tables:
        evidence_parts.append(
            f"--- TABLE ID: {table.chunk_id} (Page {table.page_number}) ---\n"
            f"Caption: {table.caption or ''}\n"
            f"Headers: {table.headers}\n"
            f"Rows: {table.rows}"
        )
        valid_ids.add(table.chunk_id)

    for eq in retrieved_equations:
        evidence_parts.append(
            f"--- EQUATION ID: {eq.chunk_id} (Page {eq.page_number}) ---\n"
            f"Latex: {eq.latex}\n"
            f"Context: {eq.surrounding_context}"
        )
        valid_ids.add(eq.chunk_id)

    evidence_text = "\n\n".join(evidence_parts)

    system_prompt = (
        "You are the Synthesizer node in an agentic RAG system for research papers.\n"
        "Your task is to generate a draft answer to the user's query based ONLY on the provided evidence.\n\n"
        "Guidelines:\n"
        "1. Every factual claim or number you state MUST be directly supported by the evidence.\n"
        "2. You MUST cite the source of every claim inline using the format: [UUID]. Use the exact UUID of the supporting chunk/table/equation.\n"
        "   Example: 'ResNet-50 achieves 76% top-1 accuracy [12345678-abcd-1234-abcd-1234567890ab].'\n"
        "3. Keep equations in LaTeX form, e.g. $$E = mc^2$$ or inline $E = mc^2$. Do not flatten them.\n"
        "4. Render tables as structured markdown tables. Do not flatten them.\n"
        "5. If a previous draft and verification notes (critique) are provided, you MUST revise the draft to address all the verification notes, correcting any errors or unsupported statements.\n\n"
        "You MUST respond ONLY with a JSON object matching this schema:\n"
        "{\n"
        '  "answer": "your detailed draft answer with inline citations",\n'
        '  "citations": ["list of UUID strings you cited"]\n'
        "}"
    )

    user_prompt_lines = [
        f"User Query: {query}",
        f"Retrieved Evidence:\n{evidence_text}",
    ]

    if draft_answer and verification_notes:
        user_prompt_lines.append(
            f"Previous Draft Answer:\n{draft_answer}\n\n"
            f"Verification Critique/Notes:\n"
            + "\n".join(f"- {note}" for note in verification_notes)
        )

    user_prompt = "\n\n".join(user_prompt_lines)

    if is_mock_enabled():
        logger.info("Synthesizer: using mock synthesizer response.")
        # Create a mock answer citing one of the IDs
        cited_id = list(valid_ids)[0] if valid_ids else None
        citation_str = f" [{cited_id}]" if cited_id else ""
        ans = (
            f"Mock draft answer for query: '{query}'. This is supported by the evidence{citation_str}."
        )
        if retrieved_tables:
            ans += (
                "\n\n| Model | Score |\n|---|---|\n"
                f"| {retrieved_tables[0].headers[0]} | Mock Value |"
            )
        if retrieved_equations:
            ans += f"\n\nEquation: {retrieved_equations[0].latex}"

        synth_data = {
            "answer": ans,
            "citations": [str(cited_id)] if cited_id else [],
        }
    else:
        try:
            raw_response = await call_groq(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_json=True,
            )
            synth_data = extract_json(raw_response)
        except Exception as e:
            logger.error(f"Synthesizer failed to call LLM: {e}")
            # Fallback draft answer
            cited_id = list(valid_ids)[0] if valid_ids else None
            citation_str = f" [{cited_id}]" if cited_id else ""
            synth_data = {
                "answer": f"Fallback draft answer for query: '{query}' due to API issue.{citation_str}",
                "citations": [str(cited_id)] if cited_id else [],
            }

    new_draft = synth_data.get("answer", "")
    citations_list = synth_data.get("citations", [])

    # Filter out any citations not in the evidence to prevent hallucinations
    valid_citations = []
    for cid in citations_list:
        try:
            uuid_val = UUID(cid)
            if uuid_val in valid_ids:
                valid_citations.append(uuid_val)
        except ValueError:
            continue

    # Record trace step
    trace_step = AgentTraceStep(
        step_index=step_index,
        node_name="Synthesizer",
        input_summary=f"Query: {query}. Evidence count: {len(retrieved_chunks)} chunks, {len(retrieved_tables)} tables, {len(retrieved_equations)} equations.",
        output_summary=f"Generated draft answer (length: {len(new_draft)}) with {len(valid_citations)} valid citations.",
        tool_calls=[],
        timestamp=datetime.now(timezone.utc),
    )

    return {
        "draft_answer": new_draft,
        "trace": list(trace) + [trace_step],
    }
