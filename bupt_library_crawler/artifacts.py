from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from .exporter import export_excel
from .storage import Store


LOGGER = logging.getLogger(__name__)


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    return result.stdout


def split_file(input_path: Path, output_dir: Path, part_size_mb: int) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    part_size = part_size_mb * 1024 * 1024
    parts: list[Path] = []
    with input_path.open("rb") as source:
        index = 1
        while True:
            chunk = source.read(part_size)
            if not chunk:
                break
            part_path = output_dir / f"{input_path.name}.part{index:03d}"
            part_path.write_bytes(chunk)
            parts.append(part_path)
            index += 1
    return parts


def zip_batch(db_path: Path, excel_path: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(db_path, "bupt_library.sqlite3")
        archive.write(excel_path, "bupt_library_holdings.xlsx")


def write_manifest(path: Path, batch_name: str, split_parts: list[Path]) -> None:
    if split_parts:
        part_names = "\n".join(f"- `{part.name}`" for part in split_parts)
        reconstruction = f"""
Reconstruct in PowerShell:

```powershell
$output = '{batch_name}.zip'
Remove-Item $output -ErrorAction SilentlyContinue
Get-ChildItem '{batch_name}.zip.part*' | Sort-Object Name | ForEach-Object {{
    $in = [System.IO.File]::OpenRead($_.FullName)
    $out = [System.IO.File]::Open($output, [System.IO.FileMode]::Append)
    try {{ $in.CopyTo($out) }} finally {{ $in.Dispose(); $out.Dispose() }}
}}
```
"""
    else:
        part_names = f"- `{batch_name}.zip`"
        reconstruction = ""

    path.write_text(
        f"""# BUPT Library Crawl Batch

Batch: `{batch_name}`
Generated at: {datetime.now().isoformat(timespec="seconds")}

Files:

{part_names}

Each archive contains:

- `bupt_library.sqlite3`
- `bupt_library_holdings.xlsx`

{reconstruction}
""",
        encoding="utf-8",
    )


def publish_batch(
    db_path: Path,
    output_path: Path,
    repo_root: Path,
    part_size_mb: int = 90,
    cleanup_after_upload: bool = True,
) -> bool:
    """Export, archive, push a batch to GitHub, then optionally clear local records."""
    store = Store(db_path)
    try:
        if store.count_books() == 0:
            LOGGER.info("No book records to upload in this batch.")
            return False

        batch_number = store.next_batch_number()
        batch_name = f"bupt_library_batch_{batch_number:05d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    finally:
        store.close()

    LOGGER.info("Exporting batch %s to Excel.", batch_name)
    export_excel(db_path, output_path)

    with tempfile.TemporaryDirectory(prefix="bupt-library-artifact-") as temp_dir:
        temp_root = Path(temp_dir)
        zip_path = temp_root / f"{batch_name}.zip"
        artifact_dir = temp_root / "artifact"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        zip_batch(db_path, output_path, zip_path)
        if zip_path.stat().st_size > part_size_mb * 1024 * 1024:
            parts = split_file(zip_path, artifact_dir, part_size_mb)
        else:
            target = artifact_dir / zip_path.name
            shutil.copy2(zip_path, target)
            parts = []

        write_manifest(artifact_dir / f"{batch_name}_README.md", batch_name, parts)

        repo_url = run_git(["remote", "get-url", "origin"], cwd=repo_root).strip()
        clone_dir = temp_root / "repo"
        LOGGER.info("Cloning %s for artifact upload.", repo_url)
        run_git(["clone", repo_url, str(clone_dir)], cwd=repo_root)

        target_dir = clone_dir / "artifacts" / batch_name
        target_dir.mkdir(parents=True, exist_ok=True)
        for item in artifact_dir.iterdir():
            shutil.copy2(item, target_dir / item.name)

        run_git(["add", "-f", "artifacts"], cwd=clone_dir)
        run_git(["commit", "-m", f"Add crawl artifact {batch_name}"], cwd=clone_dir)
        run_git(["push", "origin", "main"], cwd=clone_dir)

    if cleanup_after_upload:
        LOGGER.info("Upload succeeded. Clearing local book and holding records.")
        store = Store(db_path)
        try:
            store.clear_records()
        finally:
            store.close()
        if output_path.exists():
            output_path.unlink()

    return True

