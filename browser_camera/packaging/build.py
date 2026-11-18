"""Build portable Traffic Light camera archives with Python 3.12."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[2]
SUPPORT = Path(__file__).resolve().parent
RELEASE = '20261110'
PYTHON_VERSION = '3.12.16'
RELEASE_URL = f'https://github.com/astral-sh/python-build-standalone/releases/download/{RELEASE}'
TARGETS = {
    'windows-x64': ('x86_64-pc-windows-msvc', 'win_amd64',
                    '355ee61b8207b91574491b1c6dc9b0ebb4408fc56bfafe498f3ef439314b52dc'),
    'linux-x64': ('x86_64-unknown-linux-gnu', 'manylinux2014_x86_64',
                  '6a9e62dad033790aef722dbd370e0ce76ce17b73627ba3ae679f537049350b39'),
    'linux-arm64': ('aarch64-unknown-linux-gnu', 'manylinux2014_aarch64',
                    'b6a41defec4975d94b4ff1950236e7383e5c02ba40ea48c9ec33c66087a35aab'),
    'macos-intel': ('x86_64-apple-darwin', 'macosx_12_0_x86_64',
                    'b78a4c479f1964ec484880bee567568266f68da102269fb93a05fe8716b45f91'),
    'macos-apple-silicon': ('aarch64-apple-darwin', 'macosx_11_0_arm64',
                            '2f11b8aa3726bdbd87dd9eb76568412faddf4f47e26913fa45d6a2e424972acd'),
}
APP_FILES = (
    'browser_camera/app.js', 'browser_camera/camera.py', 'browser_camera/detector.py',
    'browser_camera/discovery.py', 'browser_camera/index.html', 'browser_camera/server.py',
    'browser_camera/styles.css', 'browser_camera/packaging/wifi_setup.py',
)
WINDOWS_START = r"""@echo off
setlocal
pushd "%~dp0" || exit /b 1
python\python.exe -E -s launch.py %*
set "exit_code=%ERRORLEVEL%"
if not "%exit_code%"=="0" pause
popd
exit /b %exit_code%
"""
UNIX_START = """#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
exec ./python/bin/python3.12 -E -s ./launch.py "$@"
"""


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download_runtime(triple, expected, destination):
    name = f'cpython-{PYTHON_VERSION}%2B{RELEASE}-{triple}-install_only_stripped.tar.gz'
    with urlopen(f'{RELEASE_URL}/{name}', timeout=60) as response, destination.open('wb') as file:
        shutil.copyfileobj(response, file, length=1024 * 1024)
    if digest(destination) != expected:
        raise ValueError(f'Python runtime checksum mismatch for {triple}')


def stage_app(bundle, target):
    for name in APP_FILES:
        destination = bundle / name
        destination.parent.mkdir(exist_ok=True, parents=True)
        shutil.copy2(ROOT / name, destination)
    shutil.copy2(SUPPORT / 'launch.py', bundle / 'launch.py')
    shutil.copy2(SUPPORT / 'README.txt', bundle / 'README.txt')
    if target == 'windows-x64':
        (bundle / 'Start.cmd').write_text(WINDOWS_START, encoding='ascii', newline='\r\n')
    else:
        launcher = bundle / ('Start.command' if target.startswith('macos-') else 'start.sh')
        launcher.write_text(UNIX_START, encoding='ascii')
        launcher.chmod(0o755)


def archive_bundle(bundle, destination, windows):
    pending = destination.with_suffix(destination.suffix + '.part')
    try:
        if windows:
            with ZipFile(pending, 'w', ZIP_DEFLATED, compresslevel=5) as archive:
                for name in sorted(bundle.rglob('*')):
                    if name.is_file():
                        archive.write(name, name.relative_to(bundle.parent))
        else:
            with tarfile.open(pending, 'w:gz', compresslevel=5) as archive:
                archive.add(bundle, arcname=bundle.name)
        pending.replace(destination)
    finally:
        pending.unlink(missing_ok=True)


def build(target, output):
    triple, wheel_platform, expected = TARGETS[target]
    windows = target == 'windows-x64'
    label = f'TrafficLight-Camera-{target}'
    print(f'Building {label}', flush=True)
    with TemporaryDirectory(prefix='traffic-package-') as directory:
        work = Path(directory)
        bundle = work / label
        bundle.mkdir()
        runtime = work / 'runtime.tar.gz'
        download_runtime(triple, expected, runtime)
        with tarfile.open(runtime) as archive:
            # Linux terminfo has case-distinct names. The browser host uses no
            # bundled terminal data, and omitting it avoids macOS build collisions.
            members = (member for member in archive
                       if not (member.name.removeprefix('./') + '/').startswith('python/share/terminfo/'))
            archive.extractall(bundle, members=members, filter='data')
        site = bundle / 'python' / ('Lib/site-packages' if windows else 'lib/python3.12/site-packages')
        subprocess.run([
            sys.executable, '-m', 'pip', '--disable-pip-version-check', 'install',
            '--no-compile', '--only-binary=:all:', '--target', str(site),
            '--platform', wheel_platform, '--python-version', '3.12',
            '--implementation', 'cp', '--abi', 'cp312',
            '-r', str(ROOT / 'browser_camera/requirements.txt'),
        ], check=True)
        stage_app(bundle, target)
        destination = output / f'{label}{".zip" if windows else ".tar.gz"}'
        archive_bundle(bundle, destination, windows)
        print(f'Built {destination.name}', flush=True)
        return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=TARGETS, action='append',
                        help='Build only this target. Repeat for more than one target.')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(exist_ok=True, parents=True)
    targets = list(dict.fromkeys(args.target or TARGETS))
    with ThreadPoolExecutor(max_workers=min(3, len(targets))) as pool:
        paths = list(pool.map(lambda target: build(target, output), targets))
    suffixes = ['.zip', '.tar.gz']
    archives = set(paths)
    for target in TARGETS:
        suffix = suffixes[0 if target == 'windows-x64' else 1]
        candidate = output / f'TrafficLight-Camera-{target}{suffix}'
        if candidate.is_file():
            archives.add(candidate)
    sums = '\n'.join(f'{digest(path)}  {path.name}' for path in sorted(archives))
    (output / 'SHA256SUMS.txt').write_text(sums + '\n', encoding='ascii', newline='\n')


if __name__ == '__main__':
    main()
