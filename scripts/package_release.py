"""Package tracked source and built dashboard; never include local state or secrets."""
import argparse
import hashlib
import subprocess
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def package(root: Path, output: Path):
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    dist = root / 'dashboard' / 'dist'
    if not (dist / 'index.html').is_file():
        raise ValueError('Build dashboard before packaging')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_relative_to(root):
        raise ValueError('Release artifact must be outside source checkout')
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name in sorted(f for f in files if f):
            path = root / name
            if path.is_symlink() or not path.is_file():
                raise ValueError('Unexpected tracked entry: ' + name)
            archive.write(path, 'hiyo-engineering-os/' + name)
        for path in sorted(dist.rglob('*')):
            if path.is_file() and not path.is_symlink():
                archive.write(path, 'hiyo-engineering-os/' + str(path.relative_to(root)).replace('\\','/'))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n')
    return digest


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    print(package(Path(__file__).resolve().parents[1], args.output.resolve()))
