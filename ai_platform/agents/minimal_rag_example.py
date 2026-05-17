"""
Minimal ShopStream RAG example — embed, store, retrieve, answer.

This file is a learning exercise. It has NO real vector database.
All "documents" are a Python list at the top of this file.
Replace that list + the search function with a real vector store later —
nothing else changes.

RAG = Retrieval-Augmented Generation.
The 3 steps:
    1. At ingest time:  split documents into chunks -> embed each chunk -> store
    2. At query time:   embed the question -> find closest chunks -> retrieve
    3. At answer time:  send question + retrieved chunks to LLM -> generate answer

INGEST FLOW  (runs once, offline)
    Document -> Read -> Chunk -> Embed -> Store in Vector DB
    |           |        |         |         |
    PDF/text    raw    FAKE_     embed_    build_
    file        text  DOCUMENT_  text()   index()
                      CHUNKS

QUERY FLOW  (runs on every user question)
    Question -> Embed -> Search -> Retrieve -> Generate -> Answer
    |            |         |          |           |           |
    user       embed_   cosine_    retrieve() build_      generate_
    input      text()  similarity()           prompt()    answer()

Run with:
    pip install openai numpy
    export OPENAI_API_KEY=sk-...
    python minimal_rag_example.py

Or swap to Databricks (see comment inside build_client()).
"""

import os

import numpy as np
from openai import OpenAI


# =============================================================================
# FAKE DOCUMENTS -- replace this with real PDFs or Delta table rows later
#
# Imagine these are chunks extracted from ShopStream's product documentation.
# In production, Step 01 (embed_documents.py) writes these to a Delta table
# and Databricks Vector Search builds the index automatically.
# =============================================================================

FAKE_DOCUMENT_CHUNKS = [
    {
        "chunk_id": 1,
        "source_file": "return-policy.pdf",
        "page": 1,
        "text": (
            "ShopStream accepts returns within 30 days of delivery. "
            "Items must be in original condition with tags attached. "
            "Electronics have a 14-day return window."
        ),
    },
    {
        "chunk_id": 2,
        "source_file": "return-policy.pdf",
        "page": 2,
        "text": (
            "To initiate a return, visit My Orders in the ShopStream app and select Return Item. "
            "You will receive a prepaid shipping label by email within 24 hours. "
            "Refunds are processed within 5 business days of receiving the item."
        ),
    },
    {
        "chunk_id": 3,
        "source_file": "alpine-pro-tent-guide.pdf",
        "page": 1,
        "text": (
            "The Alpine Pro Tent is a 4-season tent rated for temperatures down to -20C. "
            "It supports up to 3 people and weighs 2.8 kg. "
            "Setup time is approximately 15 minutes with two people."
        ),
    },
    {
        "chunk_id": 4,
        "source_file": "alpine-pro-tent-guide.pdf",
        "page": 3,
        "text": (
            "Known issue: some early production batches (lot codes A100-A340) had seam sealing defects. "
            "If your tent leaks at the seams, contact support for a free replacement. "
            "Lot code is printed on the inner label near the door zipper."
        ),
    },
    {
        "chunk_id": 5,
        "source_file": "warranty-policy.pdf",
        "page": 1,
        "text": (
            "All ShopStream products carry a 2-year manufacturer warranty. "
            "Warranty covers manufacturing defects but not damage from misuse. "
            "Outdoor gear used beyond rated conditions voids the warranty."
        ),
    },
]


# =============================================================================
# CHUNKING STRATEGIES -- four approaches, pick one based on your content
#
# The FAKE_DOCUMENT_CHUNKS above already have chunks pre-split.
# These functions show HOW you would create those chunks from raw text.
# In production, one of these runs before embed_text().
# =============================================================================

def chunk_by_sentence(text: str) -> list[str]:
    """
    Strategy 1: Sentence-based — split on sentence boundaries.

    Best for: Q&A over short factual documents (policies, FAQs).
    Each chunk = one complete sentence. No sentence is ever cut in half.

    Example:
        text = "Returns take 5 days. Electronics have 14 days. Contact support."
        chunks = [
            "Returns take 5 days.",
            "Electronics have 14 days.",
            "Contact support.",
        ]

    Weakness: very short chunks lose context
    ("Electronics have 14 days." — 14 days for WHAT?)
    """
    import re
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in sentences if s]


def chunk_by_paragraph(text: str) -> list[str]:
    """
    Strategy 2: Paragraph-based — split on double newlines.

    Best for: documents with clear paragraph structure (reports, manuals).
    Each chunk = one paragraph. Preserves topic coherence naturally.

    Example:
        text = "Returns policy:\\n\\nShopStream accepts returns within 30 days.
                Items must be in original condition.\\n\\nFor electronics,
                the return window is 14 days."
        chunks = [
            "Returns policy:",
            "ShopStream accepts returns within 30 days. Items must be in original condition.",
            "For electronics, the return window is 14 days.",
        ]

    Weakness: paragraph length varies wildly — one chunk may be 10 words,
    the next 500 words.
    """
    paragraphs = text.split("\n\n")
    return [p.strip() for p in paragraphs if p.strip()]


def chunk_sliding_window(text: str, size: int = 200, overlap: int = 50) -> list[str]:
    """
    Strategy 3: Sliding window — fixed size with overlap.

    Best for: dense technical text where every sentence matters equally.
    Splits on word boundaries (not characters) so words are never cut.
    Overlap ensures that answers spanning two windows are still captured.

    Example (size=6 words, overlap=2 words):
        text = "A B C D E F G H I J"
        chunks = [
            "A B C D E F",   <- window 1
            "E F G H I J",   <- window 2 (overlaps E F)
        ]

    This is the strategy rag-chatbot uses via LangChain's
    RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).

    Weakness: chunks don't respect sentence or topic boundaries.
    A sentence can be split in half between two windows if it's long.
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += size - overlap  # step forward by (size - overlap)
    return chunks


def chunk_semantic(text: str, client: "OpenAI") -> list[str]:
    """
    Strategy 4: Semantic — use an LLM to identify topic boundaries.

    Best for: long documents with mixed topics where paragraph breaks
    don't align with topic changes (e.g., a 50-page legal contract).

    How it works:
        1. Split text into sentences first (coarse pass)
        2. Ask the LLM: "Where does the topic change in this list?"
        3. LLM returns boundary indices
        4. Merge sentences between boundaries into one chunk

    Weakness: expensive — costs one LLM call per document.
    Use only when sentence/paragraph/sliding strategies give bad retrieval.

    This is a SKETCH — not a full implementation.
    In production, use LangChain's SemanticChunker or LlamaIndex's
    SemanticSplitterNodeParser instead of calling the LLM directly.
    """
    sentences = chunk_by_sentence(text)

    prompt = (
        "Below is a numbered list of sentences from a document.\n"
        "Return only the sentence numbers where the TOPIC CHANGES as a JSON array.\n"
        "Example: [3, 7, 12]\n\n"
        + "\n".join(f"{i}: {s}" for i, s in enumerate(sentences))
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # cheap model — no need for gpt-4o here
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )

    import json
    boundaries = json.loads(response.choices[0].message.content)
    boundaries = sorted(set([0] + boundaries + [len(sentences)]))

    chunks = []
    for i in range(len(boundaries) - 1):
        chunk_sentences = sentences[boundaries[i]:boundaries[i + 1]]
        chunks.append(" ".join(chunk_sentences))
    return chunks


# =============================================================================
# WHICH STRATEGY TO USE — decision table
#
#   Content type                    | Best strategy
#   --------------------------------|------------------
#   FAQs, policies, short docs      | sentence-based
#   Reports, manuals, structured    | paragraph-based
#   Dense technical text, code docs | sliding window  <-- rag-chatbot uses this
#   Long contracts, mixed topics    | semantic (LLM)
# =============================================================================


# =============================================================================
# STEP 1 -- EMBED DOCUMENTS (runs once at ingest time)
#
# For each chunk, call the embedding model and store the resulting vector.
# At query time you embed the question with the SAME model and compare.
#
# In production: Databricks Vector Search does this automatically.
# Here: we call OpenAI's embedding API and store vectors in a Python list.
# =============================================================================

def embed_text(client: OpenAI, text: str) -> list[float]:
    """
    Convert text to a vector using OpenAI's embedding model.

    The same model MUST be used for both documents and queries.
    Mixing models (e.g., embed docs with text-embedding-3-small but
    query with text-embedding-3-large) gives wrong similarity scores.

    Returns a list of 1,536 floats for text-embedding-3-small.
    """
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def build_index(client: OpenAI) -> list[dict]:
    """
    Embed all document chunks and return an in-memory index.

    Each item in the index is the original chunk dict + an 'embedding' key.

    In production: this step is replaced by Databricks Vector Search.
    The index is persisted in a managed Delta table -- you never store
    vectors in a Python list in production.
    """
    print("[Ingest] Embedding document chunks...")
    index = []
    for chunk in FAKE_DOCUMENT_CHUNKS:
        vector = embed_text(client, chunk["text"])
        index.append({**chunk, "embedding": vector})
        print(f"[Ingest] Embedded chunk {chunk['chunk_id']} ({chunk['source_file']} p.{chunk['page']})")
    print(f"[Ingest] Done. {len(index)} chunks in index.\n")
    return index


# =============================================================================
# STEP 2 -- RETRIEVE (runs at query time)
#
# Embed the question -> compute cosine similarity against all chunks
# -> return the top-k most similar chunks.
#
# Cosine similarity measures how similar two vectors are.
# Score 1.0 = identical meaning. Score 0.0 = completely unrelated.
#
# In production: one line:
#   client.get_index(...).similarity_search(query_text=question, num_results=3)
# Here: we compute it manually so you can see what the vector DB does internally.
# =============================================================================

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))


def retrieve(client: OpenAI, index: list[dict], question: str, top_k: int = 2) -> list[dict]:
    """
    Find the top-k most relevant chunks for a question.

    Steps:
    1. Embed the question with the SAME model used during ingest
    2. Compute cosine similarity between question vector and every chunk vector
    3. Return the top-k chunks sorted by score (highest = most relevant)
    """
    print(f"[Retrieve] Embedding question: {question!r}")
    question_vector = embed_text(client, question)

    scored = []
    for chunk in index:
        score = cosine_similarity(question_vector, chunk["embedding"])
        scored.append({**chunk, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_chunks = scored[:top_k]

    print(f"[Retrieve] Top {top_k} chunks:")
    for c in top_chunks:
        print(f"  score={c['score']:.3f} | {c['source_file']} p.{c['page']} | {c['text'][:60]}...")

    return top_chunks


# =============================================================================
# STEP 3 -- GENERATE (runs at query time, after retrieve)
#
# Build a prompt that contains:
#   - The retrieved chunks (the "context")
#   - The user's question
#
# The LLM is instructed to answer ONLY from the provided context.
# This is what prevents hallucination -- the LLM cannot use training data
# to make up an answer; it must use the retrieved text.
# =============================================================================

def build_prompt(question: str, retrieved_chunks: list[dict]) -> str:
    """
    Build the RAG prompt: context + question.

    The key instruction is "Answer ONLY from the context below."
    Without this, the LLM mixes retrieved facts with hallucinated ones.
    """
    context_sections = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        context_sections.append(
            f"[Source {i}: {chunk['source_file']}, page {chunk['page']}]\n{chunk['text']}"
        )

    context = "\n\n".join(context_sections)

    return f"""You are a ShopStream customer support assistant.
Answer the question ONLY using the context below.
If the context does not contain enough information, say "I don't have that information."
Always cite which source you used (e.g. "According to return-policy.pdf...").

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""


def generate_answer(client: OpenAI, prompt: str) -> str:
    """
    Call the LLM with the RAG prompt and return its answer.

    This is a plain LLM call -- no tools, no agent loop.
    The retrieval step already fetched the relevant information.
    The LLM's only job is to write a readable answer from the context.
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,  # deterministic -- same question always gets same answer
    )
    return response.choices[0].message.content


# =============================================================================
# STEP 4 -- THE FULL RAG PIPELINE
#
# retrieve -> build_prompt -> generate_answer
#
# Compare this to the agent loop in minimal_agent_example.py:
#
#   Agent:  LLM decides which tool to call -> tool runs -> LLM writes answer
#           (LLM is in control of what to look up)
#
#   RAG:    YOU retrieve relevant docs -> YOU build the prompt -> LLM writes answer
#           (Python is in control of what context the LLM sees)
#
# Use an agent when the question requires multiple steps or decisions.
# Use RAG when the question needs factual grounding from a document corpus.
# =============================================================================

def run_rag(client: OpenAI, index: list[dict], question: str) -> str:
    print(f"\n{'='*60}")
    print(f"Question: {question}")
    print(f"{'='*60}")

    # Step 1: find the most relevant chunks
    retrieved = retrieve(client, index, question, top_k=2)

    # Step 2: build the prompt with retrieved context
    prompt = build_prompt(question, retrieved)
    print(f"\n[Prompt] Built prompt with {len(retrieved)} context chunks")

    # Step 3: generate the answer
    print("[Generate] Calling LLM...")
    answer = generate_answer(client, prompt)

    print(f"\n[Answer] {answer}")
    return answer


# =============================================================================
# BUILD CLIENT
# =============================================================================

def build_client() -> OpenAI:
    """
    Build the OpenAI client.

    To use Databricks instead:
        return OpenAI(
            api_key=os.environ["DATABRICKS_TOKEN"],
            base_url=os.environ["DATABRICKS_HOST"].rstrip("/") + "/serving-endpoints",
        )
        # Change model= in generate_answer() to "databricks-meta-llama-3-3-70b-instruct"
        # Change embedding model= in embed_text() to "databricks-gte-large-en"
    """
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


# =============================================================================
# RUN IT
# =============================================================================

if __name__ == "__main__":
    client = build_client()

    # Build the index ONCE (ingest time)
    # In production: this runs nightly via embed_documents.py
    # At query time: the index already exists, skip this step
    index = build_index(client)

    # Ask questions (query time)
    questions = [
        "How do I return a product?",
        "My Alpine Pro Tent is leaking at the seams. What should I do?",
        "What is the warranty period?",
    ]

    for q in questions:
        run_rag(client, index, q)
        print()
