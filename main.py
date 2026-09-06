import os
import sys
import subprocess

def run_ffmpeg():
    # Fetch environment variables with fallback defaults
    cookie = os.environ.get(
        "COOKIE_HEADER", 
        "__hdnea__=st=1788706812~exp=1788728412~acl=/*~hmac=dfa547b2a98b9d919862387cc72700b37df4b3b3d8848315ad8f5c20719b3728"
    )
    cenc_key = os.environ.get(
        "CENC_KEY", 
        "445450834250887830adbde7c75caa2b"
    )
    mpd_url = os.environ.get(
        "MPD_URL", 
        "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd"
    )
    output_file = os.environ.get("OUTPUT_FILE", "output.mp4")

    # Build the exact FFmpeg command array
    cmd = [
        "ffmpeg",
        "-y",
        "-headers", f"Cookie: {cookie}",
        "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "-cenc_decryption_key", cenc_key,
        "-i", mpd_url,
        "-c", "copy",
        output_file
    ]

    print("[+] Running FFmpeg Command:")
    print(" ".join(cmd))
    sys.stdout.flush()

    # Execute FFmpeg process
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    # Stream logs live to stdout
    for line in process.stdout:
        print(line, end="")
        sys.stdout.flush()

    process.wait()

if __name__ == "__main__":
    run_ffmpeg()
