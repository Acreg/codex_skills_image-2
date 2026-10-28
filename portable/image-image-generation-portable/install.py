"""Install or update the bundled Codex image Skill (Python 3.11+, offline)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile

NAME = "image-image-generation"
ROOT = Path(__file__).resolve().parent


def verify_bundle(root: Path) -> dict[str, str]:
    """Validate all package files against the bundled manifest before writing."""
    root = root.resolve()
    manifest = root / "manifest.json"
    if manifest.is_symlink():
        raise ValueError("Manifest must not be a symlink")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or data.get("skill") != NAME:
        raise ValueError("Unsupported bundle manifest")
    entries = data.get("files")
    if not isinstance(entries, dict) or not entries or f"{NAME}/SKILL.md" not in entries:
        raise ValueError("Missing Skill files in manifest")
    for relative, digest in entries.items():
        part = PurePosixPath(relative)
        if (not relative or part.is_absolute() or ".." in part.parts
                or ":" in relative or "\\" in relative or str(part) != relative):
            raise ValueError("Unsafe manifest path: " + relative)
        file = root.joinpath(*part.parts)
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(root):
            raise ValueError("Missing or unsafe package file: " + relative)
        if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError("Checksum mismatch: " + relative)
    found = set()
    for file in root.rglob("*"):
        if file.is_symlink():
            raise ValueError("Package must not contain symlinks")
        if file.is_file():
            found.add(file.relative_to(root).as_posix())
    if found != set(entries) | {"manifest.json"}:
        raise ValueError("Unexpected or missing package files")
    return entries


def default_skills_dir() -> Path:
    home = Path(os.environ["CODEX_HOME"]).expanduser() if os.environ.get("CODEX_HOME") else Path.home() / ".codex"
    return home / "skills"


def select_target(skills_dir: Path) -> Path:
    preferred = skills_dir / NAME
    legacy = Path.home() / ".agents" / "skills" / NAME
    # Update a legacy installation in place rather than creating a second copy.
    if preferred.exists() or preferred.is_symlink():
        return preferred
    if not os.environ.get("CODEX_HOME") and skills_dir == default_skills_dir() and (legacy.exists() or legacy.is_symlink()):
        return legacy
    return preferred


def same_version(target: Path, root: Path, entries: dict[str, str]) -> bool:
    if not target.is_dir() or target.is_symlink():
        return False
    for relative, digest in entries.items():
        if not relative.startswith(NAME + "/"):
            continue
        file = target / relative.removeprefix(NAME + "/")
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            return False
    return True


def install(root: Path, skills_dir: Path) -> dict[str, str]:
    entries = verify_bundle(root)
    skills_dir = skills_dir.expanduser().resolve()
    target = select_target(skills_dir)
    if target.is_symlink() or (target.exists() and not target.is_dir()):
        raise ValueError("Existing Skill path is not a regular directory: " + str(target))
    if same_version(target, root, entries):
        return {"status": "already_installed", "skill": NAME, "target": str(target)}

    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix=".image-skill-stage-", dir=target.parent) as temporary:
        staged = Path(temporary) / NAME
        shutil.copytree(root / NAME, staged)
        # Keep the user's optional local API settings usable after an upgrade.
        local_config = target / 'fallback-config.local.json'
        if target.is_dir() and local_config.is_file():
            shutil.copy2(local_config, staged / local_config.name)
        if target.exists():
            backup_dir = target.parent / ".image-skill-backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = backup_dir / f"{NAME}-{suffix}"
            target.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            if backup is not None:
                backup.rename(target)
            raise
    result = {"status": "updated" if backup else "installed", "skill": NAME, "target": str(target)}
    if backup is not None:
        result["backup"] = str(backup)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the bundle only")
    parser.add_argument("--skills-dir", type=Path, help="Override the Codex skills parent directory")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        print("Python 3.11+ required", file=sys.stderr)
        return 2
    try:
        if args.check:
            result = {"status": "verified", "files": len(verify_bundle(ROOT))}
        else:
            result = install(ROOT, args.skills_dir or default_skills_dir())
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("Installation failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
