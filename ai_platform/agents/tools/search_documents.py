"""SearchDocumentsTool — semantic search over ShopStream documents via Vector Search.

Used by the agent when the user asks questions like:
  - 'What is the return policy?'
  - 'Does the Alpine Pro Tent have a warranty?'
  - 'How do I initiate a return?'

Queries the Mosaic AI Vector Search index built by create_index.py.
"""

from __future__ import annotations

from typing import Any

from databricks.sdk import WorkspaceClient


VS_ENDPOINT = "helix-vs-endpoint"
VS_INDEX = "helix_databricks.default.document_chunks_index"
DEFAULT_NUM_RESULTS = 4


class SearchDocumentsTool:
    name = "search_documents"
    description = (
        "Semantic search over ShopStream's product documentation, policies, and FAQs. "
        "Use this tool for questions about return policies, warranties, shipping, "
        "product guides, or any question that requires looking up written documentation. "
        "Returns the most relevant document excerpts."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The question or topic to search for in the document store.",
            },
            "num_results": {
                "type": "integer",
                "default": DEFAULT_NUM_RESULTS,
                "description": f"Number of document chunks to return. Default {DEFAULT_NUM_RESULTS}.",
            },
        },
        "required": ["query"],
    }

    def run(self, args: dict[str, Any]) -> str:
        query = args.get("query", "").strip()
        if not query:
            return "Error: 'query' argument is required."

        num_results = int(args.get("num_results", DEFAULT_NUM_RESULTS))

        w = WorkspaceClient()

        results = w.vector_search_indexes.query_index(
            index_name=VS_INDEX,
            columns=["chunk_id", "source_file", "section", "chunk_text"],
            query_text=query,
            num_results=num_results,
        )

        rows = results.result.data_array if results.result else []
        if not rows:
            return f"No documents found for query: '{query}'."

        lines = [f"Document search results for: '{query}'", "=" * 50]
        for i, row in enumerate(rows, 1):
            chunk_id, source_file, section, chunk_text = row[0], row[1], row[2], row[3]
            lines.append(f"[{i}] {source_file} — {section} (id: {chunk_id})")
            lines.append(chunk_text)
            lines.append("")

        return "\n".join(lines)
