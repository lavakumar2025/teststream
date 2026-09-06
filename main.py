import os
import sys
import subprocess
import urllib.request
import urllib.error

def clean_env_var(var_name, default=""):
    value = os.environ.get(var_name, default).strip()
    # Remove leading/trailing quotes, brackets, and markdown artifacts
    value = value.strip('"\'[]()')
    return value

def run_ffmpeg_telegram():
    cookie = clean_env_var(
        "COOKIE_HEADER", 
        "__hdnea__=st=1788706812~exp=1788728412~acl=/*~hmac=dfa547b2a98b9d919862387cc72700b37df4b3b3d8848315ad8f5c20719b3728"
    )
    
    cenc_key = clean_env_var(
        "CENC_KEY", 
        "445450834250887830adbde7c75caa2b"
    )
    
    mpd_url = clean_env_var(
        "MPD_URL", 
        "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd"
    )
    
    telegram_rtmp = clean_env_var("TELEGRAM_RTMP_URL")

    if not telegram_rtmp:
        print("[!] ERROR: TELEGRAM_RTMP_URL environment variable is missing!")
        sys.exit(1)

    print(f"[+] Target MPD URL: {mpd_url}")
    print(f"[+] Target RTMP Endpoint: {telegram_rtmp[:25]}...")

    # 1. Pre-flight URL validation
    print("[+] Checking stream accessibility...")
    req = urllib.request.Request(
        mpd_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Cookie": cookie
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                print("[+] Stream URL accessible and Cookie verified!")
    except urllib.error.HTTPError as e:
        print(f"[!] HTTP Error {e.code}: Check if COOKIE_HEADER has expired.")
        sys.exit(1)
    except Exception as e:
        print(f"[!] URL Check Warning: {e}")

    # 2. Format headers for Linux FFmpeg
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
