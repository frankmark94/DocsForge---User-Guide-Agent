import re
import time

import chromadb
from openai import OpenAI

import config


def get_chroma_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=config.CHROMA_DIR)


def create_collection_name(video_name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", video_name.rsplit(".", 1)[0])
    safe = safe[:50]
    return f"{safe}_{int(time.time())}"


def embed_texts(texts: list[str]) -> list[list[float]]:
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.embeddings.create(
        model=config.EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def store_embeddings(
    collection_name: str,
    documents: list[str],
    metadatas: list[dict],
    ids: list[str],
) -> int:
    client = get_chroma_client()
    collection = client.get_or_create_collection(name=collection_name)

    batch_size = 50
    total = 0
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i : i + batch_size]
        batch_meta = metadatas[i : i + batch_size]
        batch_ids = ids[i : i + batch_size]
        batch_embeddings = embed_texts(batch_docs)

        collection.add(
            documents=batch_docs,
            embeddings=batch_embeddings,
            metadatas=batch_meta,
            ids=batch_ids,
        )
        total += len(batch_docs)

    return total


def query_similar(
    collection_name: str, query_text: str, n_results: int = 5
) -> list[dict]:
    client = get_chroma_client()
    collection = client.get_collection(name=collection_name)
    query_embedding = embed_texts([query_text])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
    )

    items = []
    if results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            items.append({
                "document": doc,
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
            })
    return items
