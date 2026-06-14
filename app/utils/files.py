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


def read_from_vault(name: str, vault_path: str, subfolder: str) -> str:
    """Read content of <name> stored inside vault_path/subfolder/."""
    return (Path(vault_path) / subfolder / name).read_text(encoding="utf-8")


def delete_files(paths: list[str]) -> None:
    # Удаляет файлы по списку путей; отсутствующие игнорируются (unlink(missing_ok=True)).
    # Нужна уборке шага 13: зафейленные клипы и их QC-кадры после успешной проверки бита.
    for path in paths:
        Path(path).unlink(missing_ok=True)
