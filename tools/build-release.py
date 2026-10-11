#!/usr/bin/python3
"""Build a deterministic source archive without binaries or personal state."""
import gzip
import hashlib
from pathlib import Path
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from omarchy_ptt import __version__


def main():
    name = 'omarchy-ptt-' + __version__
    destination = ROOT / 'dist'
    destination.mkdir(exist_ok=True)
    archive = destination / (name + '.tar.gz')
    roots = ['src', 'bin', 'profiles', 'tests', 'docs', 'examples', 'tools', '.github',
             'install.sh', 'README.md', 'README.en.md', 'LICENSE', 'CHANGELOG.md', '.gitignore']
    files = []
    for entry in roots:
        path = ROOT / entry
        if not path.exists():
            continue
        candidates = path.rglob('*') if path.is_dir() else [path]
        files.extend(p for p in candidates if p.is_file() and '__pycache__' not in p.parts
                     and p.suffix not in ('.pyc', '.so'))
    with archive.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w') as tar:
                for file in sorted(files):
                    if file.is_symlink():
                        raise RuntimeError('Refusing to package symlink: ' + str(file))
                    info = tar.gettarinfo(str(file), arcname=name + '/' + str(file.relative_to(ROOT)))
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ''
                    info.mode = 0o755 if file.stat().st_mode & 0o111 else 0o644
                    with file.open('rb') as data:
                        tar.addfile(info, data)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + '.sha256').write_text(checksum + '  ' + archive.name + '\n')
    print(str(archive))
    print(checksum)


if __name__ == '__main__':
    main()
