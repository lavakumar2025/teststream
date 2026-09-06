import os
import sys
import subprocess
import urllib.request
import urllib.error
import time

PROXYSCRAPE_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&country=in"

def clean_env_var(var_name, default=""):
    value = os.environ.get(var_name, default).strip()
    return value.strip('"\'[]()')

def fetch_fresh_indian_proxies():
    print("[+] Fetching live Indian proxies from ProxyScrape...")
    try:
        req = urllib.request.Request(PROXYSCRAPE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            text = res.read().decode("utf-8")
            proxies = [p.strip() for p in text.replace("\n", " ").split(" ") if p.strip()]
            http_proxies = [p for p in proxies if p.startswith("http://") or p.startswith("https://")]
            print(f"[+] Loaded {len(http_proxies)} HTTP proxies.")
            return http_proxies
    except Exception as e:
        print(f"[!] Proxy fetch failed: {e}")
        return []

def test_proxy(mpd_url, cookie, proxy):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cookie": cookie
    }
    try:
        proxy_handler = urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(mpd_url, headers=headers)
        with opener.open(req, timeout=5) as res:
            if res.status == 200:
                return True
    except Exception:
        pass
    return False

def run_ffmpeg():
    cookie = clean_env_var("COOKIE_HEADER")
    cenc_key = clean_env_var("CENC_KEY")
    mpd_url = clean_env_var("MPD_URL", "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd")
    telegram_rtmp = clean_env_var("TELEGRAM_RTMP_URL")

    if not telegram_rtmp:
        print("[!] TELEGRAM_RTMP_URL missing!")
        sys.exit(1)

    while True:
        proxies = fetch_fresh_indian_proxies()
        working_proxy = None

        for proxy in proxies[:15]:
            print(f"[+] Testing proxy: {proxy}")
            if test_proxy(mpd_url, cookie, proxy):
                working_proxy = proxy
                print(f"[SUCCESS] Selected Proxy: {proxy}")
                break

        if not working_proxy:
            print("[!] No working proxies found. Retrying in 10s...")
            time.sleep(10)
            continue

        # Passthrough copy mode eliminates CPU re-encoding overhead and broken pipe drops
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
            "-c:v", "copy",
            "-c:a", "copy",
            "-f", "flv",
            telegram_rtmp
        ]

        print(f"[+] Launching stream to Telegram via {working_proxy}...")
        sys.stdout.flush()

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        for line in process.stdout:
            print(line, end="")
            sys.stdout.flush()

        process.wait()
        print("[!] FFmpeg exited or stream dropped. Restarting pipeline in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    run_ffmpeg()
