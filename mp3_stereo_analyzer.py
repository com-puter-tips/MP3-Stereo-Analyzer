import os
import sys
import argparse
from pydub import AudioSegment

__version__ = "1.0.0"

# Constants
SILENCE_THRESHOLD = -90.0  # dBFS
BALANCE_THRESHOLD = 10.0   # Max allowed difference between L/R for a 'Balanced' checkmark

def analyze_audio(file_path):
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

    # Metadata extraction
    channels = audio.channels
    duration = len(audio) / 1000.0

    print(f"[i] Format: {channels} Channels | {audio.frame_rate}Hz | {audio.sample_width*8}-bit")
    print(f"[i] Duration: {duration:.2f} seconds")
    print("\n--- Running Diagnostic Tests ---")

    tests_passed = 0
    total_tests = 4

    # TEST 1: Channel Presence
    print(f"[1/4] Checking Channel Count...", end=" ")
    if channels >= 1:
        print("✅ PASS")
        tests_passed += 1
    else:
        print("❌ FAIL (No audio data)")

    # TEST 2: Left Channel Signal
    print(f"[2/4] Left Channel Signal...  ", end=" ")
    left = audio.split_to_mono()[0] if channels > 1 else audio
    l_peak = left.max_dBFS
    l_avg = left.dBFS

    if l_peak > SILENCE_THRESHOLD:
        print(f"✅ PASS (Peak: {l_peak:.1f}dB | Avg: {l_avg:.1f}dB)")
        tests_passed += 1
    else:
        print(f"❌ FAIL (Silent)")

    # TEST 3: Right Channel Signal
    print(f"[3/4] Right Channel Signal... ", end=" ")
    if channels > 1:
        right = audio.split_to_mono()[1]
        r_peak = right.max_dBFS
        r_avg = right.dBFS
        if r_peak > SILENCE_THRESHOLD:
            print(f"✅ PASS (Peak: {r_peak:.1f}dB | Avg: {r_avg:.1f}dB)")
            tests_passed += 1
        else:
            print(f"❌ FAIL (Silent)")
    else:
        print("🟡 SKIP (Mono File - Duplicated to both ears by OS)")
        total_tests -= 1  # Adjust total for mono files

    # TEST 4: Stereo Balance
    print(f"[4/4] Stereo Balance Test... ", end=" ")
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

    # FINAL VERDICT
    score = (tests_passed / total_tests) * 100
    print(f"\n{'='*60}")
    print(f" FINAL SCORE: {score:.1f}%")

    if score >= 100:
        print(" VERDICT: 🏆 [PASS] This MP3 is perfect for both earbuds.")
    elif score >= 75:
        print(" VERDICT: ⚠️ [PASS WITH WARNING] Signal exists, but balance is off.")
    else:
        print(" VERDICT: 🚨 [FAIL] This file will only play in one ear (or not at all).")
    print(f"{'='*60}\n")

def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze MP3 files for earbud compatibility.")
    parser.add_argument('files', nargs='+', help='One or more MP3 files to analyze')
    parser.add_argument('--version', action='version', version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    for file in args.files:
        analyze_audio(file)

if __name__ == "__main__":
    main()
