from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_core.documents import Document

CODE_EXTENSIONS = {".py": Language.PYTHON, ".js": Language.JS, ".ts": Language.TS}
DOC_EXTENSIONS = {".md", ".rst", ".txt"}
IGNORE_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv"}

# --- Near-duplicate chunk dedup (Phase 4 #4) ---
# Two thresholds for shingled-hash fingerprint dedup. Drop a chunk if
# at least DEDUP_MIN_DUP_RATIO of its 5-shingles match shingles seen
# earlier in the same file. Per-file only -- cross-file similarity
# isn't conflation (shared imports / references / project names are
# expected across files), just shared vocabulary.
#
# 5-token shingles + 60% overlap is the classic Broder near-duplicate
# recipe from search-engine literature; on real READMEs and docs it
# catches verbatim and lightly-paraphrased duplicates while leaving
# unrelated chunks that happen to share vocabulary alone.
_DEDUP_SHINGLE_SIZE = 5
_DEDUP_MIN_DUP_RATIO = 0.6


def _dedupe_chunks(docs: list[Document]) -> list[Document]:
    """
    Drop near-duplicate chunks within a single file. Uses 5-shingle
    minhash-style fingerprinting: for each chunk, compute its set of
    5-token shingles, hash each, and compare against the union of
    shingles already kept. If at least DEDUP_MIN_DUP_RATIO of the new
    chunk's shingles overlap with what we've kept, drop the chunk.

    Resets per call -- the caller is responsible for grouping chunks
    by file (which load_and_chunk does via the local file_chunks list)
    so cross-file "similar" chunks aren't conflated.
    """
    seen_shingles: set[int] = set()
    kept: list[Document] = []

    for doc in docs:
        tokens = doc.page_content.split()
        # Too short to dedupe safely -- a chunk with fewer than 5 tokens
        # has at most one shingle and a single match shouldn't drop it.
        if len(tokens) < _DEDUP_SHINGLE_SIZE:
            kept.append(doc)
            continue

        shingles = {
            hash(" ".join(tokens[i:i + _DEDUP_SHINGLE_SIZE]))
            for i in range(len(tokens) - _DEDUP_SHINGLE_SIZE + 1)
        }
        overlap = len(shingles & seen_shingles)
        ratio = overlap / len(shingles)

        if ratio >= _DEDUP_MIN_DUP_RATIO:
            continue  # near-duplicate of an earlier chunk in this file

        kept.append(doc)
        seen_shingles |= shingles

    return kept


def load_and_chunk(repo_path: Path) -> list[Document]:
    docs: list[Document] = []

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file() or any(p in IGNORE_DIRS for p in file_path.parts):
            continue

        suffix = file_path.suffix
        try:
            text = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue  # skip binaries/unreadable files

        rel_path = str(file_path.relative_to(repo_path))

        if suffix in CODE_EXTENSIONS:
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=CODE_EXTENSIONS[suffix], chunk_size=800, chunk_overlap=100
            )
            chunk_type = "code"
        elif suffix in DOC_EXTENSIONS:
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
            chunk_type = "doc"
        else:
            continue

        # Accumulate this file's chunks into a local list so dedup runs
        # per-file (cross-file "shared" content isn't conflation -- just
        # references like "see Foo" appearing in many places).
        file_chunks: list[Document] = []
        for i, chunk in enumerate(splitter.split_text(text)):
            # Prepending the file path to what actually gets embedded (not
            # just stored as metadata) helps the embedding itself capture
            # "this content belongs to this file/module" -- a raw code
            # fragment alone often loses exactly the context that made it
            # findable. This is safe to do: the header is plain text fed
            # to the LLM as retrieved context, not injected into the
            # frontend's rendering -- the model re-narrates it into its
            # own real code fences when answering, it doesn't get echoed
            # verbatim to the user.
            header = f"[File: {rel_path}]\n"
            file_chunks.append(Document(
                page_content=header + chunk,
                metadata={"source": rel_path, "type": chunk_type, "chunk_index": i}
            ))

        # Drop near-duplicates within this file before they reach the
        # vector store. See _dedupe_chunks docstring for the algorithm.
        for deduped in _dedupe_chunks(file_chunks):
            docs.append(deduped)

    return docs