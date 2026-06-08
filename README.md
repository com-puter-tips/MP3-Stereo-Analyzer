# MP3-Stereo-Analyzer

## MP3 Earbud Compatibility Analyzer

A Python tool to verify if your MP3 files are correctly formatted to play in both the left and right earbuds. It checks channel presence, average volume (RMS), stereo balance, and whether both channels actually carry the same content. It can also fix problem files and compare two versions of a track to pick the best one.

## Installation

Install from PyPI:

```bash
pip install mp3-stereo-analyzer
```

This installs the `mp3-stereo-analyzer` command. FFmpeg must be present on your system for audio decoding:

```bash
brew install ffmpeg        # macOS
```

### From source

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install pydub numpy
pip install "audioop-lts; python_version >= '3.13'"   # only needed on Python 3.13+
python3 mp3-analyzer.py your_file.mp3
```

`audioop-lts` is required only on Python 3.13 and newer.

## Usage

After `pip install`, use the `mp3-stereo-analyzer` command (or run `python3 mp3-analyzer.py` from a source checkout):

```bash
# Analyze a single file
mp3-stereo-analyzer your_file.mp3

# Analyze multiple files
mp3-stereo-analyzer file1.mp3 file2.mp3

# Analyze every MP3 in a folder
mp3-stereo-analyzer *.mp3

# Detect AND fix files that play different audio in each ear
mp3-stereo-analyzer --fix your_file.mp3

# Compare versions and pick the best one
mp3-stereo-analyzer --compare old.mp3 new.mp3
```

## What it checks

The analyzer reports the format (channels, sample rate, bit depth, bitrate) and runs five tests:

1. Channel count: the file actually contains audio channels.
2. Left channel signal: the left channel is not silent.
3. Right channel signal: the right channel is not silent.
4. Stereo balance: left and right RMS levels are within range (not heavily panned).
5. Channel content match: the left and right channels carry the same material. This uses the cross-channel correlation and catches the common problem where one earbud plays only the music and the other plays only the vocals, or where the channels are phase-inverted and cancel to near-silence. Earlier versions could not detect this because each channel individually has signal.

## Fixing a problem file (`--fix`)

If a file fails the channel content test (each ear hears different or partial audio), run:

```bash
mp3-stereo-analyzer --fix "your_file.mp3"
```

This writes a corrected copy named `your_file (fixed-bothears).mp3` in the same folder. Both channels in the corrected file carry the full (left + right) mix, so it plays the complete audio, voice and music, in both earbuds. The original file is left untouched and the bitrate is preserved.

## Comparing two versions (`--compare`)

When you have two downloads of the same track and want the better one:

```bash
mp3-stereo-analyzer --compare "version_a.mp3" "version_b.mp3"
```

It prints a side-by-side table and an overall score, then recommends the best version. The score weighs bitrate, audio bandwidth (the high-frequency cutoff, which reflects clarity and sharpness), loudness (RMS), sample rate, bit depth, healthy stereo, and a clipping penalty. Differences smaller than a just-noticeable threshold are treated as ties so trivial gaps do not swing the result. More than two files can be compared at once.

## Troubleshooting

If the script returns a **PASS** but you still hear only one ear on your iPhone, check:

1. **iOS Settings**: Accessibility > Audio/Visual > Balance (ensure it is centered at 0.00).
2. **Hardware**: Ensure your Lightning/USB-C adapter or Bluetooth buds are fully paired, seated, and clean.

If a file **FAILS** the channel content test, the audio itself is the problem (different content per ear). Run `--fix` to create a both-ears copy.

## Citation

If you use this software, please cite it using the metadata in [CITATION.cff](CITATION.cff).
