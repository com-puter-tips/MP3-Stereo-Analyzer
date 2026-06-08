import os
import sys
import shutil
import argparse
import subprocess
import numpy as np
from pydub import AudioSegment

__version__ = "1.1.0"

# Constants
SILENCE_THRESHOLD = -90.0   # dBFS, below this a channel is considered silent
BALANCE_THRESHOLD = 10.0    # Max allowed L/R RMS difference (dB) for a 'Balanced' result
CORRELATION_OK = 0.35       # L/R correlation above this means both ears share content
CORRELATION_PHASE = -0.30   # Below this the channels are phase-inverted (mono cancels)

# How many seconds to decode when a fast, representative sample is enough.
SAMPLE_SECONDS = 150


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def get_bitrate_kbps(file_path, audio=None):
    """Return the MP3 bitrate in kbps (e.g. 128, 192).

    Prefers ffprobe (part of the FFmpeg dependency). Falls back to estimating
    from file size and duration when ffprobe is unavailable.
    """
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            out = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=bit_rate:format=bit_rate",
                 "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                capture_output=True, text=True, timeout=30,
            )
            for token in out.stdout.split():
                if token.isdigit() and int(token) > 0:
                    return round(int(token) / 1000)
        except Exception:
            pass
    try:
        if audio is not None and len(audio) > 0:
            return round(os.path.getsize(file_path) * 8 / (len(audio) / 1000.0) / 1000)
    except Exception:
        pass
    return None


def _rms_db(x):
    x = np.asarray(x, dtype=np.float64)
    if x.size == 0:
        return -np.inf
    return 20 * np.log10((np.sqrt(np.mean(x ** 2)) + 1e-12) / 32768.0)


def _peak_db(x):
    x = np.asarray(x, dtype=np.float64)
    if x.size == 0:
        return -np.inf
    return 20 * np.log10((np.max(np.abs(x)) + 1e-12) / 32768.0)


def channel_correlation(audio):
    """Pearson correlation between L and R channels (downsampled for speed)."""
    samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
    if audio.channels < 2:
        return None
    samples = samples.reshape((-1, audio.channels))
    l, r = samples[:, 0], samples[:, 1]
    n = len(l)
    if n < 2:
        return None
    stride = max(1, n // 300000)
    l, r = l[::stride], r[::stride]
    if np.std(l) < 1e-9 or np.std(r) < 1e-9:
        return None
    return float(np.corrcoef(l, r)[0, 1])


def decode_pcm(file_path, seconds=SAMPLE_SECONDS, rate=48000, channels=2):
    """Decode (a portion of) a file to an (N, channels) int16 numpy array via ffmpeg."""
    cmd = ["ffmpeg", "-v", "error"]
    if seconds:
        cmd += ["-t", str(seconds)]
    cmd += ["-i", file_path, "-f", "s16le", "-ac", str(channels), "-ar", str(rate), "-"]
    out = subprocess.run(cmd, capture_output=True).stdout
    a = np.frombuffer(out, dtype=np.int16)
    a = a[: (a.size // channels) * channels].reshape((-1, channels))
    return a, rate


def audio_bandwidth_hz(mono, rate, floor_db=-50.0):
    """Highest frequency retaining real energy (the encoder low-pass edge).

    Lossy MP3 encoders roll off the top end harder at lower bitrates
    (~16 kHz at 128k, ~19 kHz at 192k, ~20 kHz at 320k), so a wider
    bandwidth means a sharper, clearer, higher-quality file.
    """
    mono = np.asarray(mono, dtype=np.float64)
    if mono.size < rate:  # need at least ~1s
        return None
    win = 8192
    nwin = mono.size // win
    if nwin == 0:
        return None
    acc = np.zeros(win // 2 + 1)
    window = np.hanning(win)
    for i in range(nwin):
        seg = mono[i * win:(i + 1) * win] * window
        acc += np.abs(np.fft.rfft(seg))
    acc /= nwin
    # Smooth across a few bins to ignore spurious spikes.
    k = 5
    smooth = np.convolve(acc, np.ones(k) / k, mode="same")
    peak = smooth.max()
    if peak <= 0:
        return None
    mag_db = 20 * np.log10(smooth / peak + 1e-12)
    freqs = np.fft.rfftfreq(win, d=1.0 / rate)
    above = np.where(mag_db > floor_db)[0]
    if above.size == 0:
        return None
    return float(freqs[above[-1]])


# --------------------------------------------------------------------------- #
# Single-file diagnostic
# --------------------------------------------------------------------------- #
def analyze_audio(file_path, do_fix=False):
    if not os.path.exists(file_path):
        print(f"❌ Error: {file_path} not found.")
        return

    print(f"\n{'='*60}")
    print(f" 🔍 ANALYZING: {os.path.basename(file_path)}")
    print(f"{'='*60}")

    try:
        audio = AudioSegment.from_file(file_path)
    except Exception as e:
        print(f"❌ Failed to load audio: {e}")
        return

    channels = audio.channels
    duration = len(audio) / 1000.0
    bitrate = get_bitrate_kbps(file_path, audio)
    bitrate_str = f" | {bitrate} kbps" if bitrate else ""

    print(f"[i] Format: {channels} Channels | {audio.frame_rate}Hz | {audio.sample_width*8}-bit{bitrate_str}")
    print(f"[i] Duration: {duration:.2f} seconds")
    print("\n--- Running Diagnostic Tests ---")

    tests_passed = 0
    total_tests = 5
    fix_needed = False

    # TEST 1: Channel Presence
    print(f"[1/5] Checking Channel Count...   ", end=" ")
    if channels >= 1:
        print("✅ PASS")
        tests_passed += 1
    else:
        print("❌ FAIL (No audio data)")

    # TEST 2: Left Channel Signal
    print(f"[2/5] Left Channel Signal...      ", end=" ")
    left = audio.split_to_mono()[0] if channels > 1 else audio
    l_peak, l_avg = left.max_dBFS, left.dBFS
    if l_peak > SILENCE_THRESHOLD:
        print(f"✅ PASS (Peak: {l_peak:.1f}dB | Avg: {l_avg:.1f}dB)")
        tests_passed += 1
    else:
        print(f"❌ FAIL (Silent)")

    # TEST 3: Right Channel Signal
    print(f"[3/5] Right Channel Signal...     ", end=" ")
    r_avg = None
    if channels > 1:
        right = audio.split_to_mono()[1]
        r_peak, r_avg = right.max_dBFS, right.dBFS
        if r_peak > SILENCE_THRESHOLD:
            print(f"✅ PASS (Peak: {r_peak:.1f}dB | Avg: {r_avg:.1f}dB)")
            tests_passed += 1
        else:
            print(f"❌ FAIL (Silent)")
    else:
        print("🟡 SKIP (Mono File - Duplicated to both ears by OS)")
        total_tests -= 1

    # TEST 4: Stereo Balance
    print(f"[4/5] Stereo Balance Test...      ", end=" ")
    if channels > 1:
        diff = abs(l_avg - r_avg)
        if diff < BALANCE_THRESHOLD:
            print(f"✅ PASS ({diff:.1f}dB difference)")
            tests_passed += 1
        else:
            print(f"⚠️  WARN ({diff:.1f}dB difference - Audio is heavily panned)")
    else:
        print("🟡 SKIP (Mono)")
        total_tests -= 1

    # TEST 5: Channel Content Match (catches voice-in-one-ear / phase issues)
    print(f"[5/5] Channel Content Match...    ", end=" ")
    if channels > 1:
        corr = channel_correlation(audio)
        if corr is None:
            print("🟡 SKIP (could not measure)")
            total_tests -= 1
        elif corr < CORRELATION_PHASE:
            print(f"❌ FAIL (corr {corr:.2f} - channels are PHASE-INVERTED; sum to near-silence)")
            fix_needed = True
        elif corr < CORRELATION_OK:
            print(f"❌ FAIL (corr {corr:.2f} - channels carry DIFFERENT content; each ear hears different audio, e.g. vocals vs music)")
            fix_needed = True
        else:
            print(f"✅ PASS (corr {corr:.2f} - both ears share content)")
            tests_passed += 1
    else:
        print("🟡 SKIP (Mono)")
        total_tests -= 1

    # FINAL VERDICT
    score = (tests_passed / total_tests) * 100 if total_tests else 0
    print(f"\n{'='*60}")
    print(f" FINAL SCORE: {score:.1f}%")
    if fix_needed:
        print(" VERDICT: 🚨 [FAIL] Each earbud hears different/partial audio.")
        print("          FIX: re-run with --fix to write a corrected (both-ears) copy.")
    elif score >= 100:
        print(" VERDICT: 🏆 [PASS] This MP3 is perfect for both earbuds.")
    elif score >= 75:
        print(" VERDICT: ⚠️ [PASS WITH WARNING] Signal exists, but balance is off.")
    else:
        print(" VERDICT: 🚨 [FAIL] This file will only play in one ear (or not at all).")
    print(f"{'='*60}\n")

    if do_fix and fix_needed:
        fix_audio(file_path, audio, bitrate)


def fix_audio(file_path, audio=None, bitrate=None):
    """Write a corrected copy where both channels carry the full (L+R) mix.

    This guarantees every earbud hears the complete audio (voice + music),
    resolving voice-in-one-ear and phase-inversion problems.
    """
    if audio is None:
        audio = AudioSegment.from_file(file_path)
    if bitrate is None:
        bitrate = get_bitrate_kbps(file_path, audio) or 192

    stem, ext = os.path.splitext(file_path)
    out_path = f"{stem} (fixed-bothears){ext or '.mp3'}"
    # set_channels(1) averages L+R into a mono mix; set_channels(2) duplicates it.
    fixed = audio.set_channels(1).set_channels(2)
    fixed.export(out_path, format="mp3", bitrate=f"{bitrate}k")
    print(f"🔧 FIXED FILE WRITTEN: {os.path.basename(out_path)}")
    print(f"   Both channels now carry the full mix; it will play fully in both earbuds.\n")
    return out_path


# --------------------------------------------------------------------------- #
# Compare two or more versions and pick the best
# --------------------------------------------------------------------------- #
def extract_features(file_path):
    audio = AudioSegment.from_file(file_path)
    pcm, rate = decode_pcm(file_path)
    if pcm.size == 0:
        return None
    l, r = pcm[:, 0].astype(np.float64), pcm[:, 1].astype(np.float64)
    both = pcm.astype(np.float64).reshape(-1)
    mono = (l + r) / 2.0
    clip = np.mean(np.abs(both) >= 32767 * 0.999) * 100.0
    corr = float(np.corrcoef(l, r)[0, 1]) if (np.std(l) > 1e-9 and np.std(r) > 1e-9) else 0.0
    return {
        "path": file_path,
        "name": os.path.basename(file_path),
        "bitrate": get_bitrate_kbps(file_path, audio) or 0,
        "sample_rate": audio.frame_rate,
        "bit_depth": audio.sample_width * 8,
        "channels": audio.channels,
        "duration": len(audio) / 1000.0,
        "rms_db": _rms_db(both),
        "peak_db": _peak_db(both),
        "clip_pct": clip,
        "bandwidth_hz": audio_bandwidth_hz(mono, rate) or 0.0,
        "corr": corr,
    }


def _norm(values, tol=0.0):
    """Min-max normalize a list to 0..1.

    If the spread is within `tol` (a just-noticeable difference for the
    metric), the values are treated as a tie and all score 1.0, so trivial
    differences do not produce large score swings.
    """
    lo, hi = min(values), max(values)
    if hi - lo <= tol:
        return [1.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def compare_files(files):
    feats = []
    for f in files:
        if not os.path.exists(f):
            print(f"❌ Error: {f} not found."); continue
        try:
            ft = extract_features(f)
            if ft:
                feats.append(ft)
        except Exception as e:
            print(f"❌ Failed to analyze {f}: {e}")
    if len(feats) < 2:
        print("⚠️  Need at least two readable files to compare.")
        return

    print(f"\n{'='*72}")
    print(" 🆚 COMPARING VERSIONS")
    print(f"{'='*72}")
    for i, ft in enumerate(feats, 1):
        print(f" [{i}] {ft['name']}")
    print(f"{'-'*72}")
    header = f"{'Metric':<22}" + "".join(f"{'['+str(i+1)+']':>14}" for i in range(len(feats)))
    print(header)

    def row(label, key, fmt):
        print(f"{label:<22}" + "".join(f"{fmt(ft[key]):>14}" for ft in feats))

    row("Bitrate (kbps)", "bitrate", lambda v: f"{v}")
    row("Sample rate (Hz)", "sample_rate", lambda v: f"{v}")
    row("Bit depth", "bit_depth", lambda v: f"{v}-bit")
    row("Channels", "channels", lambda v: f"{v}")
    row("Loudness (RMS dBFS)", "rms_db", lambda v: f"{v:.1f}")
    row("Peak (dBFS)", "peak_db", lambda v: f"{v:.1f}")
    row("Clipping (%)", "clip_pct", lambda v: f"{v:.2f}")
    row("Audio bandwidth (Hz)", "bandwidth_hz", lambda v: f"{v:.0f}")
    row("L/R correlation", "corr", lambda v: f"{v:.2f}")

    # ---- Scoring -------------------------------------------------------- #
    weights = {
        "bitrate": 25,        # higher = better
        "bandwidth_hz": 25,   # wider = clearer / sharper
        "rms_db": 15,         # higher = louder
        "sample_rate": 10,    # higher = better
        "bit_depth": 5,       # higher = better
        "stereo": 10,         # genuine, healthy stereo
        "clip_pct": 10,       # lower = better (penalty)
    }
    cols = {
        # tolerances = just-noticeable differences; smaller gaps count as ties
        "bitrate": _norm([f["bitrate"] for f in feats], tol=5),
        "bandwidth_hz": _norm([f["bandwidth_hz"] for f in feats], tol=500),
        "rms_db": _norm([f["rms_db"] for f in feats], tol=1.0),
        "sample_rate": _norm([f["sample_rate"] for f in feats]),
        "bit_depth": _norm([f["bit_depth"] for f in feats]),
        # stereo health: 2ch & healthy corr -> 1.0; 2ch but split -> 0.5; mono -> 0
        "stereo": _norm([
            1.0 if (f["channels"] >= 2 and f["corr"] >= CORRELATION_OK)
            else 0.5 if f["channels"] >= 2 else 0.0
            for f in feats
        ]),
        # clipping is inverted: less clipping scores higher
        "clip_pct": _norm([-f["clip_pct"] for f in feats], tol=0.1),
    }
    scores = []
    for i in range(len(feats)):
        s = sum(weights[k] * cols[k][i] for k in weights)
        scores.append(s)

    print(f"{'-'*72}")
    print(f"{'SCORE (0-100)':<22}" + "".join(f"{s:>14.1f}" for s in scores))
    print(f"{'='*72}")

    best = int(np.argmax(scores))
    print(f" 🏆 BEST VERSION: [{best+1}] {feats[best]['name']}")
    # Reasons: metrics where the best file is the top performer.
    reasons = []
    labels = {"bitrate": "higher bitrate", "bandwidth_hz": "wider bandwidth (clearer/sharper)",
              "rms_db": "louder", "sample_rate": "higher sample rate",
              "bit_depth": "deeper bit depth", "stereo": "healthier stereo",
              "clip_pct": "less clipping"}
    # Cite a metric only when the winner is uniquely best on the
    # tolerance-aware normalized column (ties are not reasons).
    for k in ["bitrate", "bandwidth_hz", "rms_db", "sample_rate", "bit_depth", "stereo", "clip_pct"]:
        col = cols[k]
        if col[best] == max(col) and any(c < col[best] for c in col):
            reasons.append(labels[k])
    if reasons:
        print(f"    Why: {', '.join(reasons)}.")
    # Warn if the winner still has the channel-split defect.
    if feats[best]["channels"] >= 2 and feats[best]["corr"] < CORRELATION_OK:
        print("    ⚠️  Note: even the best version has a channel-split issue; run --fix on it.")
    print(f"{'='*72}\n")
    return feats[best]["path"]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyze MP3 files for earbud compatibility, fix channel-split files, and compare versions.")
    parser.add_argument('files', nargs='+', help='One or more MP3 files')
    parser.add_argument('--fix', action='store_true',
                        help='Write a corrected (both-ears) copy for any file with a channel-split/phase issue')
    parser.add_argument('--compare', action='store_true',
                        help='Compare the given files and recommend the best version')
    parser.add_argument('--version', action='version', version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    if args.compare:
        compare_files(args.files)
    else:
        for f in args.files:
            analyze_audio(f, do_fix=args.fix)


if __name__ == "__main__":
    main()
