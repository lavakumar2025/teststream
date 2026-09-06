import os
import sys
import subprocess
import requests

def run_ffmpeg_telegram():
    cookie = os.environ.get(
        "COOKIE_HEADER", 
        "__hdnea__=st=1788706812~exp=1788728412~acl=/*~hmac=dfa547b2a98b9d919862387cc72700b37df4b3b3d8848315ad8f5c20719b3728"
    ).strip()
    
    cenc_key = os.environ.get(
        "CENC_KEY", 
        "445450834250887830adbde7c75caa2b"
    ).strip()
    
    mpd_url = os.environ.get(
        "MPD_URL", 
        "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd"
    ).strip()
    
    telegram_rtmp = os.environ.get("TELEGRAM_RTMP_URL", "").strip()

    if not telegram_rtmp:
        print("[!] ERROR: TELEGRAM_RTMP_URL environment variable is missing!")
        sys.exit(1)

    # 1. Pre-flight check to verify if Cookie is valid
    print("[+] Checking stream accessibility...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cookie": cookie
    }
    try:
        res = requests.get(mpd_url, headers=headers, timeout=10)
        if res.status_code != 200:
            print(f"[!] Stream URL rejected request (HTTP {res.status_code}). Cookie is likely EXPIRED!")
            print("[!] Please update COOKIE_HEADER in Render settings.")
            sys.exit(1)
        print("[+] Stream URL accessible and Cookie verified!")
    except Exception as e:
        print(f"[!] Network error checking MPD URL: {e}")

    # 2. Format headers strictly for Linux FFmpeg (\r\n trailing line break)
    formatted_headers = f"Cookie: {cookie}\r\n"

    cmd = [
        "ffmpeg",
        "-y",
        "-headers", formatted_headers,
        "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "-cenc_decryption_key", cenc_key,
        "-i", mpd_url,
        "-map", "0:v:0",
        "-map", "0:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", "2500k",
        "-maxrate", "3000k",
        "-bufsize", "6000k",
        "-c:a", "aac",
        "-b:a", "128k",
        "-f", "flv",
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
