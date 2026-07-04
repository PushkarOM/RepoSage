from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_core.documents import Document

CODE_EXTENSIONS = {".py": Language.PYTHON, ".js": Language.JS, ".ts": Language.TS}
DOC_EXTENSIONS = {".md", ".rst", ".txt"}
IGNORE_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv"}

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

        for i, chunk in enumerate(splitter.split_text(text)):
            docs.append(Document(
                page_content=chunk,
                metadata={"source": rel_path, "type": chunk_type, "chunk_index": i}
            ))

    return docs
