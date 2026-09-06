import os
import sys
import subprocess
import urllib.request
import urllib.error

# Indian proxies extracted from your list
INDIAN_PROXIES = [
    "http://151.185.58.17:80",
    "http://219.65.73.80:80",
    "http://13.203.138.32:3001",
    "http://52.140.40.92:80",
    "http://65.1.240.131:3001",
    "http://156.67.110.124:10808"
]

def clean_env_var(var_name, default=""):
    value = os.environ.get(var_name, default).strip()
    return value.strip('"\'[]()')

def find_working_proxy(mpd_url, cookie, proxies):
    """Tests each Indian proxy against Jio's MPD endpoint until one succeeds."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cookie": cookie
    }

    for proxy in proxies:
        print(f"[+] Testing Indian Proxy: {proxy}...")
        try:
            proxy_handler = urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
            opener = urllib.request.build_opener(proxy_handler)
            
            req = urllib.request.Request(mpd_url, headers=headers)
            with opener.open(req, timeout=8) as response:
                if response.status == 200:
                    print(f"[SUCCESS] Proxy connected successfully: {proxy}")
                    return proxy
        except urllib.error.HTTPError as e:
            print(f"    [-] Proxy {proxy} failed with HTTP {e.code}")
        except Exception as e:
            print(f"    [-] Proxy {proxy} unreachable ({e})")
            
    return None

def run_ffmpeg_telegram():
    cookie = clean_env_var(
        "COOKIE_HEADER", 
        "__hdnea__=st=1788706812~exp=1788728412~acl=/*~hmac=dfa547b2a98b9d919862387cc72700b37df4b3b3d8848315ad8f5c20719b3728"
    )
    cenc_key = clean_env_var("CENC_KEY", "445450834250887830adbde7c75caa2b")
    mpd_url = clean_env_var("MPD_URL", "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd")
    telegram_rtmp = clean_env_var("TELEGRAM_RTMP_URL")

    if not telegram_rtmp:
        print("[!] ERROR: TELEGRAM_RTMP_URL environment variable is missing!")
        sys.exit(1)

    # Allow custom proxy override via Render ENV, otherwise use proxy rotation list
    env_proxy = clean_env_var("HTTP_PROXY")
    proxy_list = [env_proxy] if env_proxy else INDIAN_PROXIES

    working_proxy = find_working_proxy(mpd_url, cookie, proxy_list)

    if not working_proxy:
        print("[!] ERROR: All Indian proxies failed or timed out. Unable to bypass region block.")
        sys.exit(1)

    # Build FFmpeg Command with the verified Indian proxy
    cmd = [
        "ffmpeg",
        "-y",
        "-http_proxy", working_proxy,
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
    ]

    print(f"[+] Launching live stream to Telegram via {working_proxy}...")
    sys.stdout.flush()

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    for line in process.stdout:
        print(line, end="")
        sys.stdout.flush()

    process.wait()

if __name__ == "__main__":
    run_ffmpeg_telegram()
