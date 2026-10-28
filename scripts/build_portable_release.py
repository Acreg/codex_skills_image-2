"""Build release ZIP with Codex Skill, Python bootstrap, and install guide."""
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "portable" / "image-image-generation-portable"
VERSION = (PACKAGE / "image-image-generation" / "VERSION").read_text(encoding="utf-8").strip()
ZIP = ROOT / "dist" / f"GPT-image2-gemini-nano-banana-2.1-v{VERSION}-portable.zip"


def build() -> Path:
    python_installer = ROOT / "python-installers/windows-x64/python-3.14.10-amd64.exe"
    wheels = sorted((ROOT / "bundled-dependencies/windows-x64").glob("pillow-*-cp314-cp314-win_amd64.whl"))
    if not python_installer.is_file() or len(wheels) != 1:
        raise RuntimeError("Missing official Python installer or cp314 Pillow wheel")
    files = [ROOT / "安装图片Skill.cmd", ROOT / "安装说明.txt", python_installer,
             ROOT / "python-installers/windows-x64/LICENSE.python.txt",
             ROOT / "python-installers/windows-x64/README.md", *wheels]
    files += [f for f in PACKAGE.rglob("*") if f.is_file()]
    if any(f.name == ".env" for f in files):
        raise RuntimeError("Private .env cannot be included in a release")
    ZIP.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, file.relative_to(ROOT).as_posix() if PACKAGE not in file.parents else
                          "image-image-generation-portable/" + file.relative_to(PACKAGE).as_posix())
    return ZIP


if __name__ == "__main__":
    print(build())
