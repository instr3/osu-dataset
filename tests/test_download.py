import hashlib
import importlib.util
import json
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('download', ROOT / 'download_beatmaps.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audio = b'exact original audio bytes'
        self.track = dict(id='1', beatmapset_id=1, audio_filename='1 song.mp3',
                          audio_md5=hashlib.md5(self.audio).hexdigest(), original_audio_path='1 song/audio.mp3')
        self.target = self.root / 'out' / '1 song.mp3'

    def archive(self, entries):
        path = self.root / '1.osz'
        with zipfile.ZipFile(path, 'w') as z:
            for name, data in entries.items():
                z.writestr(name, data)
        return path

    def restore(self, **kw):
        options = dict(track=self.track, output=self.root / 'out', mirrors=['https://example.com/{id}'],
                       archive_dir=None, offline=False, retries=0, delay=0, timeout=1)
        options.update(kw)
        return d.restore(**options)

    def test_exact_hash_despite_renamed_audio(self):
        archive = self.archive({'audio.mp3': b'changed', 'renamed.mp3': self.audio})
        self.assertEqual(d.extract_matching_audio(archive, self.track, self.target), 'renamed.mp3')
        self.assertEqual(self.target.read_bytes(), self.audio)

    def test_mismatch_does_not_replace_existing_audio(self):
        self.target.parent.mkdir()
        self.target.write_bytes(b'keep existing')
        with self.assertRaisesRegex(ValueError, 'No original audio MD5 match'):
            d.extract_matching_audio(self.archive({'audio.mp3': b'wrong'}), self.track, self.target)
        self.assertEqual(self.target.read_bytes(), b'keep existing')

    def test_archive_paths_are_never_extracted(self):
        d.extract_matching_audio(self.archive({'../../escape.mp3': self.audio, '../../evil.txt': b'evil'}), self.track, self.target)
        self.assertEqual(self.target.read_bytes(), self.audio)
        self.assertFalse((self.root / 'evil.txt').exists())

    def test_existing_file_is_rehashed(self):
        self.target.parent.mkdir()
        self.target.write_bytes(self.audio)
        with patch.object(d, 'fetch') as fetch:
            self.assertEqual(self.restore()['status'], 'verified_existing')
            fetch.assert_not_called()
        self.target.write_bytes(b'corrupt')
        self.assertEqual(self.restore(offline=True)['status'], 'failed')

    def test_local_archive_offline(self):
        self.archive({'audio.mp3': self.audio})
        with patch.object(d, 'fetch') as fetch:
            self.assertEqual(self.restore(archive_dir=self.root, offline=True)['status'], 'verified_archive')
            fetch.assert_not_called()

    def test_mirror_fallback_after_mismatch(self):
        calls = []
        def fetch(url, target, timeout):
            calls.append(url)
            with zipfile.ZipFile(target, 'w') as z:
                z.writestr('audio.mp3', b'wrong' if len(calls) == 1 else self.audio)
        with patch.object(d, 'fetch', side_effect=fetch):
            result = self.restore(mirrors=['https://a/{id}', 'https://b/{id}'])
        self.assertEqual(result['status'], 'downloaded_verified')
        self.assertEqual(len(calls), 2)

    def test_rate_limit_retries_and_failure_is_explicit(self):
        error = urllib.error.HTTPError('https://a/1', 429, 'limited', {'Retry-After': '1'}, None)
        with patch.object(d, 'fetch', side_effect=error) as fetch, patch.object(d.time, 'sleep') as sleep:
            result = self.restore(retries=1)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(fetch.call_count, 2)
        self.assertIn(unittest.mock.call(1.0), sleep.call_args_list)

    def test_truncated_http_response_is_reported(self):
        with patch.object(d, 'fetch', side_effect=d.http.client.IncompleteRead(b'partial')):
            self.assertEqual(self.restore()['status'], 'failed')

    def test_html_is_not_accepted_as_osz(self):
        path = self.root / 'bad.osz'
        path.write_text('<html>blocked</html>')
        with self.assertRaises(zipfile.BadZipFile):
            d.extract_matching_audio(path, self.track, self.target)
        self.assertFalse(self.target.exists())

    def test_unsafe_manifest_paths(self):
        for rel in ['../escape', '/escape', 'C:/escape', '..\\escape']:
            with self.assertRaises(ValueError):
                d.safe_path(self.root, rel)

    def test_published_dataset_and_checksums(self):
        tracks = d.load_manifest(ROOT / 'manifest.json')
        self.assertEqual(len(tracks), 142)
        inventory = json.loads((ROOT / 'annotation_checksums.json').read_text(encoding='utf-8'))
        self.assertEqual(d.verify_annotations(ROOT), len(inventory['files']))
        self.assertEqual(sum(len(t['annotations']) for t in tracks), inventory['official_annotation_files'])
        for track in tracks:
            for rel, expected in track['annotations'].items():
                self.assertEqual(d.file_md5(ROOT / rel), expected)
            for folder in ['raw', 'beatlab', 'chordlab', 'keylab']:
                self.assertTrue(any(p.startswith(folder + '/') for p in track['annotations']))


if __name__ == '__main__':
    unittest.main()
