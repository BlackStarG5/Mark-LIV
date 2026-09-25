"""Confine generated filenames and archive members to their destination."""
from pathlib import Path, PureWindowsPath
import shutil
import stat
import tarfile
import zipfile


def child_path(root, name):
    root = Path(root).resolve()
    name = str(name).replace('\\', '/')
    if ':' in name or PureWindowsPath(name).drive or name.startswith('/') or '..' in name.split('/'):
        raise ValueError(f'Unsafe relative path: {name}')
    target = (root / name).resolve()
    if target == root or root not in target.parents:
        raise ValueError(f'Path escapes destination: {name}')
    return target


def extract_archive(source, destination):
    """Preflight every member before writing; never overwrite existing files."""
    is_zip = zipfile.is_zipfile(source)
    with (zipfile.ZipFile(source) if is_zip else tarfile.open(source)) as archive:
        members = archive.infolist() if is_zip else archive.getmembers()
        if len(members) > 10000:
            raise ValueError('Archive exceeds 10,000 members.')
        total = 0
        entries = []
        targets = set()
        for member in members:
            name = member.filename if is_zip else member.name
            if name.rstrip('/') in ('', '.'):
                continue
            target = child_path(destination, name)
            directory = member.is_dir() if is_zip else member.isdir()
            if (is_zip and stat.S_ISLNK(member.external_attr >> 16)) or (not is_zip and not (member.isfile() or directory)):
                raise ValueError('Archive links and special files are unsupported.')
            if target in targets or (target.exists() and not (directory and target.is_dir())):
                raise ValueError(f'Archive would overwrite a file: {name}')
            targets.add(target)
            total += member.file_size if is_zip else member.size
            if total > 1024 ** 3:
                raise ValueError('Archive exceeds the 1 GiB extraction limit.')
            entries.append((member, target, directory))
        for member, target, directory in entries:
            if directory:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with (archive.open(member) if is_zip else archive.extractfile(member)) as incoming, target.open('xb') as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
