"""构建脚本：扫描 CSV 题库和 kb/*.md 知识文档，嵌入后写入 Chroma 向量库。

用法：
    python -m jobmatch_ai.kb_build

幂等：重复运行会先删除已有集合再重建。
"""
from __future__ import annotations

import csv
import logging
import os
import re
import uuid
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
VECTOR_STORE_PATH = str(ROOT / "vector_store")
COLLECTION_NAME = "interview_kb"


def _resolve_dir(env_key: str, *candidates: Path) -> Path:
    """Resolve a directory path.

    Order:
    1) explicit env var (absolute or relative to ROOT)
    2) first existing candidate
    3) otherwise return the first candidate (for clearer error messages)
    """
    raw = (os.getenv(env_key) or "").strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (ROOT / p)
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


# Prefer knowledge-base question banks (题库), but keep legacy folders as fallback.
_FRONTEND_BANK_DIR = _resolve_dir(
    "JOBMATCH_BANK_FRONTEND_DIR",
    ROOT / "知识库-前端" / "题库",
    ROOT / "questionBank1",
)
_UNITY_BANK_DIR = _resolve_dir(
    "JOBMATCH_BANK_UNITY_DIR",
    ROOT / "知识库-游戏" / "题库",
    ROOT / "questionBank2",
)

# CSV 列名候选（中英文兼容）
_COL_QUESTION = ["题目", "Question"]
_COL_ANSWER = ["答案要点", "Answer", "AnswerKeyPoints"]
_COL_DIFFICULTY = ["难度", "Difficulty"]
_COL_POSITION = ["相关岗位", "Position"]
_COL_TAGS = ["标签", "Tags"]
_COL_TYPE = ["题目类型", "Type"]


def _get_col(row: dict, candidates: list[str]) -> str:
    """从 dict 中按候选列名取值，兼容 BOM 前缀。"""
    for key in candidates:
        if key in row and row[key]:
            return str(row[key]).strip()
    return ""


def _slugify(name: str) -> str:
    """将目录名转换为简洁的 topic slug。去掉序号前缀，转小写。"""
    name = re.sub(r"^[\d]+[._\s]+", "", name)
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def load_csv_chunks(bank_dir: Path, role: str) -> list[dict]:
    """遍历 bank_dir 下所有子目录的 CSV，每行转为一个 chunk dict。"""
    chunks: list[dict] = []
    for topic_dir in sorted(bank_dir.iterdir()):
        if not topic_dir.is_dir():
            continue
        topic = _slugify(topic_dir.name)
        for csv_file in sorted(topic_dir.glob("*.csv")):
            try:
                with open(csv_file, encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader):
                        cleaned = {k.lstrip("\ufeff"): v for k, v in row.items()}
                        question = _get_col(cleaned, _COL_QUESTION)
                        answer = _get_col(cleaned, _COL_ANSWER)
                        if not question:
                            continue
                        chunk_id = f"{role}_{topic}_{i}_{uuid.uuid4().hex[:6]}"
                        document = f"题目：{question}\n答案要点：{answer}"
                        chunks.append(
                            {
                                "id": chunk_id,
                                "document": document,
                                "metadata": {
                                    "role": role,
                                    "topic": topic,
                                    "chunk_type": "question",
                                    "question": question,
                                    "answer_key_points": answer,
                                    "difficulty": _get_col(cleaned, _COL_DIFFICULTY),
                                    "related_position": _get_col(cleaned, _COL_POSITION),
                                    "tags": _get_col(cleaned, _COL_TAGS),
                                    "question_type": _get_col(cleaned, _COL_TYPE),
                                    "source_file": csv_file.name,
                                },
                            }
                        )
            except Exception as exc:
                logger.warning(f"Failed to load {csv_file}: {exc}")
    return chunks


def load_md_chunks(kb_dir: Path) -> list[dict]:
    """读取 kb/*.md，按二级标题（## ）分段，每段作为一个 knowledge chunk。"""
    chunks: list[dict] = []
    for md_file in sorted(kb_dir.glob("*.md")):
        stem = md_file.stem  # e.g. "role_frontend"
        role = stem.replace("role_", "") if stem.startswith("role_") else stem
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning(f"Failed to read {md_file}: {exc}")
            continue

        sections = re.split(r"(?m)^## ", content)
        for sec in sections:
            if not sec.strip():
                continue
            lines = sec.strip().splitlines()
            title = lines[0].strip() if lines else "untitled"
            body = "\n".join(lines[1:]).strip()
            if not body:
                continue
            chunk_id = f"{role}_kb_{uuid.uuid4().hex[:8]}"
            document = f"## {title}\n{body}"
            chunks.append(
                {
                    "id": chunk_id,
                    "document": document,
                    "metadata": {
                        "role": role,
                        "topic": "knowledge",
                        "chunk_type": "knowledge",
                        "title": title,
                        "source_file": md_file.name,
                        "question": "",
                        "answer_key_points": body[:800],
                        "difficulty": "",
                        "related_position": role,
                        "tags": "知识库",
                        "question_type": "knowledge",
                    },
                }
            )
    return chunks


def get_embed_fn():
    """
    获取嵌入函数。优先 sentence-transformers BAAI/bge-small-zh-v1.5，
    退而使用 ChromaDB 内置 ONNXMiniLM_L6_V2（需联网首次下载）。
    """
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        logger.info("Loading BAAI/bge-small-zh-v1.5 ...")
        model = SentenceTransformer("BAAI/bge-small-zh-v1.5")

        def _embed_st(texts: list[str]) -> list[list[float]]:
            return model.encode(
                texts, normalize_embeddings=True, show_progress_bar=True
            ).tolist()

        logger.info("Embedding model loaded (sentence-transformers).")
        return _embed_st
    except Exception as exc:
        logger.warning(f"sentence-transformers unavailable: {exc}")

    try:
        from chromadb.utils import embedding_functions as ef  # type: ignore

        logger.info("Falling back to ChromaDB built-in ONNXMiniLM_L6_V2 ...")
        onnx_fn = ef.ONNXMiniLM_L6_V2()
        return onnx_fn
    except Exception as exc:
        raise RuntimeError(
            f"No embedding backend available. "
            f"Install sentence-transformers or chromadb[onnx]: {exc}"
        ) from exc


def build(batch_size: int = 64) -> None:
    """主构建函数：扫描语料 → 嵌入 → 写入 Chroma。"""
    import chromadb  # type: ignore

    logger.info("=" * 60)
    logger.info("MockInterviewerAI KB Build — start")

    # --- 1. 收集所有 chunks ---
    all_chunks: list[dict] = []

    bank_sources: list[tuple[str, Path, str]] = [
        ("frontend_bank", _FRONTEND_BANK_DIR, "frontend"),
        ("unity_bank", _UNITY_BANK_DIR, "unity"),
    ]
    for label, bank_dir, role in bank_sources:
        if bank_dir.exists():
            chunks = load_csv_chunks(bank_dir, role)
            logger.info(
                f"  {label} ({role}): {len(chunks)} question chunks  dir={bank_dir}"
            )
            all_chunks.extend(chunks)
        else:
            logger.warning(
                f"  Question bank not found: {bank_dir} (label={label}, role={role})"
            )

    kb_dir = ROOT / "kb"
    if kb_dir.exists():
        md_chunks = load_md_chunks(kb_dir)
        logger.info(f"  kb/: {len(md_chunks)} knowledge chunks")
        all_chunks.extend(md_chunks)
    else:
        logger.warning("  kb/ directory not found — skipping knowledge docs.")

    if not all_chunks:
        raise ValueError(
            "No chunks found! Check these directories (or set env overrides): "
            "知识库-前端/题库, questionBank1, 知识库-游戏/题库, questionBank2. "
            "You can override via JOBMATCH_BANK_FRONTEND_DIR / JOBMATCH_BANK_UNITY_DIR."
        )

    # --- 2. 初始化 Chroma ---
    os.makedirs(VECTOR_STORE_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)

    # 幂等：先删除已有集合
    try:
        client.delete_collection(COLLECTION_NAME)
        logger.info(f"Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # --- 3. 嵌入 ---
    embed_fn = get_embed_fn()
    documents = [c["document"] for c in all_chunks]
    ids = [c["id"] for c in all_chunks]
    metadatas = [c["metadata"] for c in all_chunks]

    logger.info(f"Embedding {len(documents)} chunks (batch_size={batch_size}) ...")
    embeddings: list[list[float]] = []
    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        batch_embs = embed_fn(batch)
        # 兼容返回 np.ndarray 或 list
        if hasattr(batch_embs, "tolist"):
            batch_embs = batch_embs.tolist()
        embeddings.extend(batch_embs)
        done = min(i + batch_size, len(documents))
        logger.info(f"  Embedded {done}/{len(documents)}")

    # --- 4. 写入 Chroma ---
    # Chroma 单次 add 建议 ≤ 5000，分批写入
    write_batch = 500
    for i in range(0, len(all_chunks), write_batch):
        collection.add(
            documents=documents[i : i + write_batch],
            ids=ids[i : i + write_batch],
            metadatas=metadatas[i : i + write_batch],
            embeddings=embeddings[i : i + write_batch],
        )

    # --- 5. 统计打印 ---
    role_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    for c in all_chunks:
        r = c["metadata"].get("role", "unknown")
        t = c["metadata"].get("chunk_type", "unknown")
        role_counts[r] = role_counts.get(r, 0) + 1
        type_counts[t] = type_counts.get(t, 0) + 1

    logger.info("=" * 60)
    logger.info(f"Build complete!  Total chunks: {len(all_chunks)}")
    for role_name, cnt in sorted(role_counts.items()):
        logger.info(f"  Role '{role_name}': {cnt} chunks")
    for ctype, cnt in sorted(type_counts.items()):
        logger.info(f"  Type '{ctype}': {cnt} chunks")
    logger.info(f"Vector store saved to: {VECTOR_STORE_PATH}")
    logger.info("=" * 60)


if __name__ == "__main__":
    build()
