# MP3-Stereo-Analyzer

## MP3 Earbud Compatibility Analyzer

A Python tool to verify if your MP3 files are correctly formatted to play in both the left and right earbuds. It checks for channel silence, average volume (RMS), and stereo balance.

## Prerequisites

1. **FFmpeg**: Required for audio decoding.
   ```bash
   brew install ffmpeg
   ```
2. **Python 3.14+**: The script is compatible with the latest Python versions.

## Setup Instructions

1. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Upgrade pip and install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install audioop-lts pydub
   ```
   *Note: `audioop-lts` is required for Python 3.13 and newer.*

## Usage

Run the script by passing one or multiple MP3 files as arguments:

```bash
# Single file
python3 mp3-analyzer.py your_file.mp3

# Multiple files
python3 mp3-analyzer.py file1.mp3 file2.mp3

# All MP3s in a folder
python3 mp3-analyzer.py *.mp3
```

## Troubleshooting
If the script returns a **PASS** but you still hear only one ear on your iPhone, check:
1. **iOS Settings**: Accessibility > Audio/Visual > Balance (Ensure it's 0.00).
2. **Hardware**: Ensure your Lightning/USB-C adapter or Bluetooth buds are fully paired and clean.
