"""Build a credential-free skill archive from an explicit public-file allowlist."""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_FILES = (
    'SKILL.md', 'VERSION', 'requirements.txt', '.gitignore', '.gitattributes',
    'agents/openai.yaml', 'references/errors.md', 'references/fallback-setup.md',
    'scripts/generate_image.py', 'scripts/image_errors.py', 'scripts/package_skill.py',
    'tests/test_image_skill.py', 'tests/test_native_delivery.py',
    'scripts/native_delivery.py', 'CHANGELOG.md',
    'references/native-delivery.md', 'references/api-usage.md', 'references/monitoring.md',
    'references/models.md', 'references/prompting.md', 'references/delivery.md', 'references/recovery.md',
    'references/parallel.md', 'references/updates.md', 'tests/test_output_parallel.py',
    'references/gemini-v1beta.md', 'tests/test_gemini_image.py',
)


def package(root: Path, output: Path) -> list[str]:
    # No directory walk: adding a local credential file can never add it to the archive.
    missing = [name for name in PUBLIC_FILES if not (root / name).is_file()]
    if missing:
        raise ValueError('Missing public files: ' + ', '.join(missing))
    if any((root / name).is_symlink() for name in PUBLIC_FILES):
        raise ValueError('Public package files must not be symlinks')
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name in PUBLIC_FILES:
            archive.write(root / name, f'image-image-generation/{name}')
    return list(PUBLIC_FILES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    output = args.out.expanduser().resolve()
    files = package(ROOT, output)
    print(f'Packaged {len(files)} public files: {output}')


if __name__ == '__main__':
    main()
