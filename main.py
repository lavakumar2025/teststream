import os
import sys
import subprocess

def run_ffmpeg_telegram():
    # Fetch credentials from Environment Variables
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
    telegram_rtmp = os.environ.get("TELEGRAM_RTMP_URL")

    if not telegram_rtmp:
        print("[!] ERROR: TELEGRAM_RTMP_URL environment variable is missing!")
        sys.exit(1)

    # Build FFmpeg command targeted for Telegram RTMP Streaming
    cmd = [
        "ffmpeg",
        "-y",
        "-headers", f"Cookie: {cookie}\r\n",
        "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "-cenc_decryption_key", cenc_key,
        "-i", mpd_url,
        "-map", "0:v:0",         # Select video track
        "-map", "0:a:0",         # Select audio track
        "-c:v", "libx264",       # RTMP requires H.264
        "-preset", "veryfast",   # Keeps CPU low on cloud hosts like Render
        "-b:v", "2500k",
        "-maxrate", "3000k",
        "-bufsize", "6000k",
        "-c:a", "aac",           # RTMP requires AAC audio
        "-b:a", "128k",
        "-f", "flv",             # FLV container needed for RTMP
        telegram_rtmp
    ]

    print("[+] Launching live stream to Telegram...")
    sys.stdout.flush()

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    for line in process.stdout:
        print(line, end="")
        sys.stdout.flush()

    process.wait()

if __name__ == "__main__":
    run_ffmpeg_telegram()
