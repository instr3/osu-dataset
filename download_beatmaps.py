"""Reconstruct osu2017 audio locally using exact manifest MD5 checks (Python 3.9+)."""
import argparse
import hashlib
import http.client
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

MIRRORS = ['https://api.nerinyan.moe/d/{id}', 'https://catboy.best/d/{id}']
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_AUDIO = 256 * 1024 * 1024


def digest(stream):
    h = hashlib.md5()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(block)
    return h.hexdigest()


def file_md5(path):
    with path.open('rb') as stream:
        return digest(stream)


def safe_path(root, relative):
    if not isinstance(relative, str) or '\\' in relative or ':' in relative:
        raise ValueError(f'Unsafe manifest path: {relative!r}')
    path = (root / relative).resolve()
    if path == root.resolve() or root.resolve() not in path.parents:
        raise ValueError(f'Unsafe manifest path: {relative!r}')
    return path


def load_manifest(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or data.get('track_count') != len(data['tracks']):
        raise ValueError('Invalid manifest schema or count')
    seen = set()
    for track in data['tracks']:
        sid = track['beatmapset_id']
        if type(sid) is not int or sid <= 0 or str(sid) != track['id'] or track['id'] in seen:
            raise ValueError('Invalid or duplicate beatmapset ID')
        seen.add(track['id'])
        if not re.fullmatch('[0-9a-f]{32}', track['audio_md5']):
            raise ValueError('Invalid audio MD5')
        if Path(track['audio_filename']).name != track['audio_filename']:
            raise ValueError('Audio filename must be a basename')
        safe_path(Path('.'), track['audio_filename'])
    return data['tracks']


def verify_annotations(root):
    checks = json.loads((root / 'annotation_checksums.json').read_text(encoding='utf-8'))['files']
    for rel, expected in checks.items():
        path = safe_path(root, rel)
        if not path.is_file() or file_md5(path) != expected:
            raise ValueError(f'Annotation missing or MD5 mismatch: {rel}')
    return len(checks)


def extract_matching_audio(archive, track, target):
    """Never extract archive paths; only write a verified audio member to our filename."""
    with zipfile.ZipFile(archive) as z:
        candidates = [i for i in z.infolist() if not i.is_dir() and
                      i.filename.lower().endswith(('.mp3', '.ogg', '.wav', '.flac', '.m4a'))]
        preferred = track.get('original_audio_path', '').replace('\\', '/').split('/')[-1]
        candidates.sort(key=lambda i: i.filename.replace('\\', '/').split('/')[-1] != preferred)
        checked = []
        scanned_bytes = 0
        for member in candidates:
            if member.file_size > MAX_AUDIO:
                continue
            scanned_bytes += member.file_size
            if scanned_bytes > 1024 * 1024 * 1024:
                raise ValueError('Archive audio exceeds 1 GiB scan limit')
            with z.open(member) as stream:
                actual = digest(stream)  # Reading through EOF also verifies ZIP CRC.
            checked.append(actual)
            if actual != track['audio_md5']:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix='.osu2017-', suffix='.part', dir=target.parent)
            temporary = Path(name)
            try:
                with os.fdopen(fd, 'wb') as out, z.open(member) as stream:
                    shutil.copyfileobj(stream, out)
                if file_md5(temporary) != track['audio_md5']:
                    raise ValueError('Audio changed while extracting')
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            return member.filename
    raise ValueError(f'No original audio MD5 match (expected {track["audio_md5"]}; found {checked})')


def fetch(url, target, timeout):
    request = urllib.request.Request(url, headers={'User-Agent': 'osu2017-dataset/1.0 (https://github.com/instr3/osu-dataset)'})
    with urllib.request.urlopen(request, timeout=timeout) as response, target.open('wb') as out:
        total = 0
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > MAX_ARCHIVE:
                raise ValueError('Archive exceeds 512 MiB limit')
            out.write(block)


def restore(track, output, mirrors, archive_dir, offline, retries, delay, timeout):
    target = safe_path(output, track['audio_filename'])
    if target.is_file() and file_md5(target) == track['audio_md5']:
        return dict(status='verified_existing')
    errors = []
    if archive_dir:
        cached = archive_dir / (str(track['beatmapset_id']) + '.osz')
        if cached.is_file():
            try:
                member = extract_matching_audio(cached, track, target)
                return dict(status='verified_archive', member=member)
            except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
                errors.append(f'Local archive: {exc}')
    if offline:
        return dict(status='failed', errors=errors + ['No MD5-verified local audio/archive; offline mode'])
    with tempfile.TemporaryDirectory(prefix='osu2017-') as tmp:
        archive = Path(tmp) / 'download.osz'
        for mirror in mirrors:
            url = mirror.format(id=track['beatmapset_id'])
            for attempt in range(retries + 1):
                time.sleep(delay)
                try:
                    fetch(url, archive, timeout)
                    member = extract_matching_audio(archive, track, target)
                    return dict(status='downloaded_verified', source=url, member=member)
                except urllib.error.HTTPError as exc:
                    errors.append(f'{url}: HTTP {exc.code}')
                    if exc.code != 429 and exc.code < 500:
                        break
                    if attempt < retries:
                        wait = exc.headers.get('Retry-After', '')
                        time.sleep(float(wait) if wait.isdigit() else min(60, 2 ** (attempt + 1)))
                except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, http.client.HTTPException) as exc:
                    errors.append(f'{url}: {exc}')
                    if isinstance(exc, ValueError):
                        break  # Version mismatch: try the next mirror, never accept another audio.
                    if attempt < retries:
                        time.sleep(min(60, 2 ** (attempt + 1)))
    return dict(status='failed', errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('manifest.json'))
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('music'))
    parser.add_argument('--ids', nargs='+', help='Only these beatmapset IDs')
    parser.add_argument('--limit', type=int, help='Only the first N selected tracks')
    parser.add_argument('--mirror', action='append', help='HTTPS URL template containing {id}; repeat for fallback')
    parser.add_argument('--archive-dir', type=Path, help='Optional existing archives named <beatmapset_id>.osz')
    parser.add_argument('--offline', action='store_true', help='Verify local audio or restore from local archives only')
    parser.add_argument('--verify-annotations', action='store_true', help='Check all shipped annotations and exit')
    parser.add_argument('--retries', type=int, default=2)
    parser.add_argument('--delay', type=float, default=2, help='Minimum seconds before each network request')
    parser.add_argument('--timeout', type=float, default=90)
    parser.add_argument('--report', type=Path, help='JSON report; defaults to <output>/download_report.json')
    args = parser.parse_args()
    if args.retries < 0 or args.delay < 0 or args.timeout <= 0 or (args.limit is not None and args.limit <= 0):
        parser.error('Invalid retries/delay/timeout/limit')
    if args.verify_annotations:
        print(f'Verified {verify_annotations(args.manifest.parent)} annotation files')
        return 0
    tracks = load_manifest(args.manifest)
    if args.ids:
        unknown = set(args.ids) - {t['id'] for t in tracks}
        if unknown:
            parser.error(f'Unknown IDs: {sorted(unknown)}')
        tracks = [t for t in tracks if t['id'] in args.ids]
    if args.limit:
        tracks = tracks[:args.limit]
    mirrors = args.mirror or MIRRORS
    for mirror in mirrors:
        if not mirror.startswith('https://') or '{id}' not in mirror:
            parser.error('Each mirror must be an HTTPS URL template with {id}')
        try:
            mirror.format(id=1)
        except (KeyError, ValueError):
            parser.error('Invalid mirror template')
    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.report or args.output / 'download_report.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = dict(dataset='osu2017', selected=len(tracks), complete=False, results=[])
    for track in tracks:
        result = restore(track, args.output, mirrors, args.archive_dir, args.offline, args.retries, args.delay, args.timeout)
        report['results'].append(dict(id=track['id'], audio_md5=track['audio_md5'], **result))
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'{track["id"]}: {result["status"]}', flush=True)
    report['complete'] = True
    report['failed'] = sum(r['status'] == 'failed' for r in report['results'])
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(tracks) - report["failed"]}/{len(tracks)} verified; report: {report_path}')
    return 1 if report['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
