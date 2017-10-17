# osu-dataset

A public dataset containing chord/beat annotation from a music game named 'osu!'.

## What is it used for

* It was not yet a formal dataset for training of chord recognition/beat tracking, but it is okay if you just want to test your ACE (Automatic Chord Estimation) against some modern music pieces. 
* The annotation was initially used for testing rhythm-based music visualization schemes.

## Where to get the audio tracks

* We do not own copyright for the audio tracks, and they are not presented in this repo.
* You can get almost all of the audio tracks (typically formatted in .mp3 with uncertained bit rates) on osu.ppy.sh.
* Osu! currently allows you to get these audio tracks freely and legally under its DMCA, but be sure to deal with them properly, following their DMCA and pay attention to copyright infringements from artists.

## How to convert them into other formats (e.g. MIREX-style)

* You can try [this](https://github.com/instr3/MIRDataManager).

## Todo

* Add 7th and full notations to early entries
* Support complex tonality notations

## About ranking

* 7 - Correct annotation under majmin7 mapping
* 6 - Basically correct under majmin7 mapping
* 5 - Correct annotation under majmin mapping
* 4 - Basically correct under majmin mapping
* 3 - Basically annotated
* 2 - Unfinished annotation
* 1 - Not annotation
* 0 - Unsuitable for annotation
