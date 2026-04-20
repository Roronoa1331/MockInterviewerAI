"""向量检索模块：从 Chroma 向量库中检索最相关的 chunk。

公开接口：
    search(query, k=5, filter=None) -> list[dict]

filter 支持 Chroma where 语法，例如：
    {"role": "frontend"}
    {"$and": [{"role": "unity"}, {"chunk_type": "question"}]}
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_VECTOR_STORE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "vector_store"
)
_COLLECTION_NAME = "interview_kb"

# 延迟初始化的单例
_client: Any = None
_collection: Any = None
_embed_fn: Any = None


def _get_embed_fn() -> Any:
    """延迟加载嵌入函数，优先本地 sentence-transformers，退而用 ChromaDB 内置。"""
    global _embed_fn
    if _embed_fn is not None:
        return _embed_fn

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
        _embed_fn = lambda texts: model.encode(
            texts, normalize_embeddings=True
        ).tolist()
        logger.info("Retriever: using BAAI/bge-small-zh-v1.5")
        return _embed_fn
    except Exception:
        pass

    try:
        from chromadb.utils import embedding_functions as ef  # type: ignore

        onnx_fn = ef.ONNXMiniLM_L6_V2()
        _embed_fn = lambda texts: onnx_fn(texts)
        logger.info("Retriever: using ChromaDB built-in ONNXMiniLM_L6_V2")
        return _embed_fn
    except Exception:
        pass

    raise RuntimeError(
        "No embedding backend available. "
        "Install sentence-transformers: pip install sentence-transformers"
    )


def _get_collection() -> Any:
    """延迟初始化 Chroma PersistentClient 和集合。"""
    global _client, _collection
    if _collection is not None:
        return _collection

    if not os.path.exists(_VECTOR_STORE_PATH):
        raise RuntimeError(
            f"Vector store not found at '{_VECTOR_STORE_PATH}'. "
            "Please build it first: python -m jobmatch_ai.kb_build"
        )

    import chromadb  # type: ignore

    _client = chromadb.PersistentClient(path=_VECTOR_STORE_PATH)
    _collection = _client.get_collection(_COLLECTION_NAME)
    return _collection


def search(
    query: str,
    k: int = 5,
    filter: dict | None = None,
) -> list[dict]:
    """
    从向量库中检索与 query 最相关的 chunk。

    Args:
        query:  查询字符串（问题文本 / 候选人回答片段）
        k:      返回结果数量
        filter: Chroma where 条件，如 {"role": "frontend"} 或
                {"$and": [{"role": "unity"}, {"chunk_type": "question"}]}

    Returns:
        list[dict]，每项包含原始元数据字段 + "document" + "score"（越大越相关）

    Raises:
        RuntimeError: 向量库不存在时，给出清晰提示（不会静默失败）。
    """
    try:
        collection = _get_collection()
        embed_fn = _get_embed_fn()

        query_embedding = embed_fn([query])
        # 兼容 np.ndarray
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()
        query_vec = query_embedding[0]

        total = collection.count()
        n = min(k, max(1, total))

        where = filter if filter else None
        results = collection.query(
            query_embeddings=[query_vec],
            n_results=n,
            where=where,
            include=["metadatas", "distances", "documents"],
        )

        output: list[dict] = []
        if results.get("ids") and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = (results["metadatas"][0][i] if results.get("metadatas") else {}) or {}
                dist = (results["distances"][0][i] if results.get("distances") else 1.0)
                doc = (results["documents"][0][i] if results.get("documents") else "") or ""
                output.append(
                    {
                        **meta,
                        "id": doc_id,
                        "document": doc,
                        # Chroma cosine distance ∈ [0, 2]; convert to similarity ∈ [-1, 1]
                        "score": round(float(1.0 - dist), 4),
                    }
                )
        return output

    except RuntimeError:
        raise
    except Exception as exc:
        logger.warning(f"RAG search failed (query='{query[:40]}…'): {exc}")
        return []
