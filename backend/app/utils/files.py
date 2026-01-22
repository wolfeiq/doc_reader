from pathlib import Path


def find_markdown_files(base_path: Path) -> list[Path]:
    files = list(base_path.glob("**/*.md"))
    if not files:
        raise FileNotFoundError(f"No markdown files found in {base_path}")
    return files
