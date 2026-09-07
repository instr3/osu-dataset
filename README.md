# osu2017: A Rhythm Game–Based Dataset for Beat Tracking, Chord Recognition, and Key Estimation

osu2017 is a frozen dataset of **142 tracks**. The dataset contains cleaned beat annotations derived from osu! beatmaps, with chord and key annotations added separately. The authoritative track list is [`manifest.json`](manifest.json), exported from the maintainer's local dataset. This repository distributes **annotations, metadata and code only; no audio or beatmap archives**.

## Get the audio locally

Install Python **3.9 or newer**; no third-party Python packages or osu! API credentials are required for the default mirrors.

```sh
git clone --branch osu2017 https://github.com/instr3/osu-dataset.git
cd osu-dataset
python download_beatmaps.py --verify-annotations
python download_beatmaps.py
```

The script downloads each listed **beatmapset** as a temporary `.osz` archive from Nerinyan, with Catboy as fallback, finds the audio whose **file bytes match the manifest MD5**, and saves it under `music/<annotation basename>.mp3`. Archives and other assets are discarded. Audio remains on your computer and is excluded from Git.

The `osu2017` tag pins this release. Later incremental annotations can change on the default branch without changing this frozen version.

```sh
# Test one track or a small subset first.
python download_beatmaps.py --ids 100649
python download_beatmaps.py --limit 5

# Choose a destination outside the repository.
python download_beatmaps.py --output /path/to/local/music

# Recheck downloaded audio without network access.
python download_beatmaps.py --offline

# Restore from existing <beatmapset_id>.osz files without network access.
python download_beatmaps.py --archive-dir /path/to/osz --offline

# Override mirror order with HTTPS beatmapset URL templates.
python download_beatmaps.py --mirror "https://catboy.best/d/{id}" --mirror "https://api.nerinyan.moe/d/{id}"
```

Run the same command again to resume: existing files are rehashed, not merely skipped by name. Requests are spaced by at least two seconds by default. Transient HTTP failures are retried and `Retry-After` seconds are respected for rate limits. Persistent failures are recorded in `music/download_report.json`, and the command exits with status **1** if any selected track could not be verified. A `complete` report means all selected entries were attempted; check `failed` for success. A failed or different-version audio file is never accepted or used to overwrite existing audio.

**MD5 identifies the exact original audio, not the ZIP container or a `.osu` difficulty file.** Different mirrors may package the same audio differently. The original audio MD5 was checked against all 142 local MP3 files when building this release. MD5 is used for dataset byte identity, not as a security signature. Do not transcode or shift the audio before evaluation: timestamps refer to these original files. Mirrors may remove maps or retain different revisions; the downloader reports that rather than silently substituting a track.

## Dataset layout

| Path | Contents |
| --- | --- |
| `manifest.json` | Exactly 142 official entries: beatmapset ID, audio MD5/size, source filenames, annotation paths/MD5s |
| `beatlab/` | 142 beat annotation files |
| `chordlab/` | 142 chord annotation files |
| `keylab/` | 142 key annotation files |
| `raw/` | 142 original text `.arc` annotation files |
| `osumaplab/` | 35 map-derived beat files and 35 `.linkedInfo` files; an incomplete auxiliary subset |
| `updates/` | 127 other local annotation files, treated as later incremental updates, **excluded from osu2017** |
| `annotation_checksums.json` | MD5 inventory of all 765 distributed annotation files |

Use the manifest to enumerate the benchmark. Do not recursively glob `updates/` into it. These additional annotations may be incomplete or lack corresponding local audio and are not promised to be downloadable. They are kept byte-for-byte as supplied locally, including legacy filenames. Cache files, images, editor state and audio are not published.

The `.lab` files are tab-separated `start_seconds`, `end_seconds`, `label`. Beat labels are positions within the bar; chord labels use spellings such as `C#:maj` or `Eb:sus4(b7)`; key labels use spellings such as `Ab Maj`. Each audio file has the same basename as its annotations. Gaps or absent leading/trailing labels are not inferred as silence. `.arc` files contain the original textual editor annotations and metadata. In these files, `osuMapID` denotes a **beatmapset ID**, not a difficulty ID; legacy MD5 strings contain invisible formatting characters that the exporter removes when writing the manifest. The original annotation editor/converter is [MIRDataManager](https://github.com/instr3/MIRDataManager).

Annotation quality is not uniform. Known historical limitations include missing intros, inaccurate keys, between-beat chord changes and incomplete seventh-chord labels. Original confidence values are preserved, using the previous remote README definitions: 0 unsuitable, 1 unannotated, 2 unfinished, 3 basically annotated, 4 mostly correct under majmin, 5 checked under majmin, 6 mostly correct under majmin7, 7 checked under majmin7. The official subset has 11 tracks at 3, 93 at 4, 6 at 5 and 32 at 6. No new train/test split or relabeling is introduced.

## Maintainer export and checks

```sh
python scripts/build_manifest.py /path/to/local/osu --destination /path/to/separate/repository
python -m unittest discover -s tests -v
python download_beatmaps.py --verify-annotations
```

The exporter expects exactly 142 local MP3 files and matching `.arc`, beat, chord and key files. It checks every original audio MD5, copies only annotation formats, and separates all remaining local annotations into `updates/`. It reconciles the publication tree against local files, so the previous remote file count never expands the benchmark. The source directory is read-only to this script. Build into a separate checkout; the script replaces the managed annotation files there.

## Download feasibility and provenance

Automatic beatmapset downloads were tested for this release on **2026-09-07**: **142/142 tracks downloaded successfully and matched their original audio MD5s** (137 from Nerinyan, 5 from Catboy fallback). A subsequent offline verification also passed for all 142 files. Both Nerinyan and Catboy also returned beatmapset `100649`, containing `Vivalavida.mp3` with MD5 `f48097f8b50a2d697fc61a865c0b47c3`, exactly matching the local annotation. See [`download_validation.json`](download_validation.json) for full-corpus retrieval results. Availability is a dated observation, not a guarantee of future mirror service.

Related open-source implementations:

- [zfi2/osu-beatmap-downloader](https://github.com/zfi2/osu-beatmap-downloader) and its [mirror endpoint implementation](https://github.com/zfi2/osu-beatmap-downloader/blob/main/src/downloader.rs): Nerinyan and Catboy beatmapset downloads.
- [kionell/osu-downloader](https://github.com/kionell/osu-downloader): multiple beatmapset sources and download validation.
- [nzbasic/batch-beatmap-downloader](https://github.com/nzbasic/batch-beatmap-downloader): bulk beatmap retrieval.

The existing repository [MIT license](LICENSE) is retained. No rights to third-party audio are granted by this repository. Users retrieve media separately from upstream services, subject to those services' terms and availability.

**Disclaimer:** Neither the author nor MIREX provides audio files or is affiliated with any of the third-party mirrors listed above; use of those mirrors is at your own risk.

## Citation

If you use osu2017, please cite the fixed dataset version below. GitHub's **Cite this repository** button provides APA and BibTeX exports from [`CITATION.cff`](CITATION.cff).

Jiang, J. (2026). *osu2017: A Rhythm Game–Based Dataset for Beat Tracking, Chord Recognition, and Key Estimation* (Version osu2017) [Data set]. https://github.com/instr3/osu-dataset/tree/osu2017

```bibtex
@misc{jiang2026osu2017,
  author       = {Jiang, Junyan},
  title        = {{osu2017}: A Rhythm Game--Based Dataset for Beat Tracking,
                  Chord Recognition, and Key Estimation},
  year         = {2026},
  howpublished = {Dataset, version osu2017},
  url          = {https://github.com/instr3/osu-dataset/tree/osu2017}
}
```

The citation year refers to the release of this fixed version; `osu2017` is the dataset name. This citation covers the annotations and dataset metadata, not ownership of the underlying audio.

## 中文说明

正式 osu2017 固定为本地可核验的 **142 首**，以 `manifest.json` 为唯一曲目清单。Beat 标注来源于 osu! 谱面并经过清洗，chord 和 key 标注则为后期单独添加。直接分发 beat/chord/key 和原始标注；其余本地标注放在 `updates/`，视为后续零散更新，不计入正式版本。远程历史上多出的正式目录标注已移出正式集合。

运行 `python download_beatmaps.py` 即可按列表自动下载 beatmap 包，在本地提取音频并逐一核验原始音频 MD5。仓库及发布文件不包含音频。无法下载、音频版本不匹配、镜像限流等情况会写入失败报告；再次运行可以继续，已有文件也会重新核验。全部标注保持本地原始内容，不把缺失或低置信度标注自动修补成“正确”标注。
