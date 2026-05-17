from src.clients.databricks import make_client


async def similarity_search(
    index_name: str,
    query: str,
    num_results: int = 5,
) -> list[dict]:
    """Query a Databricks Vector Search index."""
    payload = {"query_text": query, "num_results": num_results}

    async with make_client() as client:
        response = await client.post(
            f"/api/2.0/vector-search/indexes/{index_name}/query",
            json=payload,
        )
        response.raise_for_status()

    return response.json().get("result", {}).get("data_array", [])
