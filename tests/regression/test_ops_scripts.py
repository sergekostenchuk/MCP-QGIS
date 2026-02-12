from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess


def test_backup_and_restore_scripts() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backup_script = repo_root / "scripts" / "backup_runtime.sh"
    restore_script = repo_root / "scripts" / "restore_runtime.sh"

    with TemporaryDirectory() as td:
        runtime = Path(td) / "runtime"
        runtime.mkdir(parents=True)
        (runtime / "state").mkdir(parents=True)
        (runtime / "state" / "one.txt").write_text("ok", encoding="utf-8")

        out = subprocess.run(
            [str(backup_script), str(runtime), str(Path(td) / "backups")],
            check=True,
            capture_output=True,
            text=True,
        )
        archive = Path(out.stdout.strip())
        assert archive.exists()

        restore_target = Path(td) / "restored"
        subprocess.run([str(restore_script), str(archive), str(restore_target)], check=True, capture_output=True, text=True)
        assert (restore_target / "runtime" / "state" / "one.txt").exists()
