import os
import sys
import subprocess
import urllib.request
import urllib.error

def clean_env_var(var_name, default=""):
    value = os.environ.get(var_name, default).strip()
    return value.strip('"\'[]()')

def run_ffmpeg_telegram():
    cookie = clean_env_var("COOKIE_HEADER")
    cenc_key = clean_env_var("CENC_KEY")
    mpd_url = clean_env_var("MPD_URL", "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd")
    telegram_rtmp = clean_env_var("TELEGRAM_RTMP_URL")
    proxy_url = clean_env_var("HTTP_PROXY") # Add your Indian proxy here

    if not telegram_rtmp:
        print("[!] ERROR: TELEGRAM_RTMP_URL environment variable is missing!")
        sys.exit(1)

    # Configure proxy for urllib pre-check
    if proxy_url:
        proxy_handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
        opener = urllib.request.build_opener(proxy_handler)
        urllib.request.install_opener(opener)
        print(f"[+] Routing request through Indian Proxy...")

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
        print(f"[!] HTTP Error {e.code}: Region blocked (requires Indian IP) or Cookie expired.")
        sys.exit(1)
    except Exception as e:
        print(f"[!] URL Check Warning: {e}")

    # 2. Build FFmpeg Command
    cmd = [
        "ffmpeg",
        "-y"
    ]

    # Pass HTTP proxy into FFmpeg if present
    if proxy_url:
        cmd.extend(["-http_proxy", proxy_url])

    cmd.extend([
        "-headers", f"Cookie: {cookie}\r\n",
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
    ])

    print("[+] Launching live stream to Telegram...")
    sys.stdout.flush()

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    for line in process.stdout:
        print(line, end="")
        sys.stdout.flush()

    process.wait()

if __name__ == "__main__":
    run_ffmpeg_telegram()
