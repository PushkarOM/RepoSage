from pathlib import Path
from app.ingestion.chunker import IGNORE_DIRS


def build_directory_tree(repo_path: Path, max_depth: int = 4) -> str:
    """
    Builds a simple indented directory tree, reusing the chunker's
    IGNORE_DIRS so noise like node_modules/.git never appears here
    either. Depth-limited so a huge repo doesn't produce an unusably
    long tree the LLM has to wade through.
    """
    lines = []

    def walk(dir_path: Path, prefix: str = "", depth: int = 0):
        if depth > max_depth:
            return
        entries = sorted(
            [e for e in dir_path.iterdir() if e.name not in IGNORE_DIRS and not e.name.startswith(".")],
            key=lambda e: (e.is_file(), e.name.lower()),
        )
        for i, entry in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                extension = "    " if i == len(entries) - 1 else "│   "
                walk(entry, prefix + extension, depth + 1)

    walk(repo_path)
    return "\n".join(lines)
