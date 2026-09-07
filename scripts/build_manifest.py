"""Export the locally verified osu2017 corpus, without copying any media."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


def md5(path):
    h = hashlib.md5()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def fields(path):
    return dict(line.split('=', 1) for line in path.read_text(encoding='utf-8-sig').splitlines() if '=' in line)


def build(source, dest):
    source, dest = source.resolve(), dest.resolve()
    if source == dest or source in dest.parents or dest in source.parents:
        raise ValueError('Source and publication must be separate directories')
    music = sorted((source / 'music').glob('*.mp3'))
    if len(music) != 142:
        raise ValueError(f'Frozen osu2017 expects 142 local MP3 files, got {len(music)}')
    tracks, copies = [], {}
    for audio in music:
        name = audio.stem
        raw = source / 'raw' / (name + '.arc')
        info = fields(raw)
        expected = re.sub(r'[\u200b\u200c\u200d\ufeff\s]', '', info['MD5']).lower()
        if not re.fullmatch('[0-9a-f]{32}', expected) or md5(audio) != expected:
            raise ValueError(f'Local audio MD5 mismatch: {name}')
        sid = int(info['osuMapID'])
        if sid <= 0 or sid != int(name.split(' ', 1)[0]):
            raise ValueError(f'Conflicting beatmapset ID: {name}')
        annotations = {}
        for folder, suffix in [('raw', '.arc'), ('beatlab', '.lab'), ('chordlab', '.lab'), ('keylab', '.lab'), ('osumaplab', '.lab'), ('osumaplab', '.linkedInfo')]:
            rel = Path(folder) / (name + suffix)
            if not (source / rel).is_file():
                if folder != 'osumaplab':
                    raise ValueError(f'Missing required annotation: {rel}')
                continue
            copies[rel.as_posix()] = source / rel
            annotations[rel.as_posix()] = md5(source / rel)
        tracks.append(dict(id=str(sid), name=name, beatmapset_id=sid,
                           audio_filename=audio.name, audio_md5=expected,
                           audio_bytes=audio.stat().st_size,
                           original_audio_path=info['Location'],
                           linked_osu_path=info.get('LinkedFile', ''),
                           confidence=info.get('Confidence'), annotations=annotations))
    # Preserve other local annotations as later additions, outside the frozen list.
    for folder, suffixes in [('raw', {'.arc'}), ('beatlab', {'.lab'}), ('chordlab', {'.lab'}), ('keylab', {'.lab'}), ('osumaplab', {'.lab', '.linkedInfo'})]:
        for f in sorted((source / folder).rglob('*')):
            if f.is_file() and f.suffix in suffixes:
                rel = f.relative_to(source).as_posix()
                if rel not in copies:
                    copies['updates/' + rel] = f
    # Only known annotation extensions may be reconciled; no cache/media copying.
    removed = []
    for folder in ['raw', 'beatlab', 'chordlab', 'keylab', 'osumaplab', 'updates']:
        for f in (dest / folder).rglob('*'):
            if f.is_file():
                rel = f.relative_to(dest).as_posix()
                if rel not in copies:
                    if f.suffix not in {'.arc', '.lab', '.linkedInfo', '.myinfo'}:
                        raise ValueError(f'Refusing to remove unexpected file: {f}')
                    removed.append(rel)
    for rel in removed:
        (dest / rel).unlink()
    for rel, src in copies.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
    manifest = dict(schema_version=1, dataset='osu2017', track_count=len(tracks),
                    checksum_target='original audio file bytes; not the OSZ archive', tracks=tracks)
    (dest / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    audit = dict(official_tracks=len(tracks), official_annotation_files=sum(len(t['annotations']) for t in tracks),
                 later_update_files=sum(r.startswith('updates/') for r in copies),
                 files={r: md5(dest / r) for r in sorted(copies)})
    (dest / 'annotation_checksums.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({**{k: v for k, v in audit.items() if k != 'files'}, 'removed_from_previous_tree': removed}, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--destination', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    build(args.source, args.destination)
