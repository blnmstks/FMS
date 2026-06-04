from pathlib import Path


def read_text_file(path: str) -> str:
    return Path(path.strip()).read_text(encoding="utf-8")


def save_to_vault(content: str, name: str, vault_path: str, subfolder: str) -> str:
    """Save content as <name>.md inside vault_path/subfolder/. Returns the filename."""
    folder = Path(vault_path) / subfolder
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{name}.md"
    (folder / filename).write_text(content, encoding="utf-8")
    return filename
