import os
import sys
import subprocess
import urllib.request
import urllib.error

PROXYSCRAPE_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&country=in"

def clean_env_var(var_name, default=""):
    value = os.environ.get(var_name, default).strip()
    return value.strip('"\'[]()')

def fetch_fresh_indian_proxies():
    """Fetches real-time Indian proxies directly from ProxyScrape API."""
    print("[+] Fetching live Indian proxies from ProxyScrape...")
    try:
        req = urllib.request.Request(PROXYSCRAPE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            text = res.read().decode("utf-8")
            # Handle space-separated or line-separated proxy output
            proxies = [p.strip() for p in text.replace("\n", " ").split(" ") if p.strip()]
            # Filter down to HTTP/HTTPS proxies for FFmpeg compatibility
            http_proxies = [p for p in proxies if p.startswith("http://") or p.startswith("https://")]
            print(f"[+] Found {len(http_proxies)} HTTP Indian proxies from ProxyScrape.")
            return http_proxies
    except Exception as e:
        print(f"[!] Failed to fetch proxies from ProxyScrape API: {e}")
        return []

def diagnose_and_find_proxy(mpd_url, cookie, proxies):
    """Tests proxies against Jio's MPD URL and logs exact error codes."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cookie": cookie
    }

    # Test direct access first to log baseline status
    print("\n--- [DIAGNOSTIC TEST 1] Direct Connection (No Proxy) ---")
    try:
        req = urllib.request.Request(mpd_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as res:
            if res.status == 200:
                print("[!] Direct connection succeeded! No proxy required.")
                return "DIRECT"
    except urllib.error.HTTPError as e:
        print(f"[EXACT ERROR] Direct HTTP Failure Code: {e.code} ({e.reason})")
        if e.code == 451:
            print(" -> REASON: Jio Geo-block active (Render Server IP is outside India).")
        elif e.code in [401, 403]:
            print(" -> REASON: COOKIE_HEADER token is EXPIRED or INVALID.")
    except Exception as e:
        print(f"[EXACT ERROR] Direct Connection Failure: {e}")

    print("\n--- [DIAGNOSTIC TEST 2] Testing Live Indian Proxies ---")
    for idx, proxy in enumerate(proxies[:15], 1):  # Test top 15 proxies
        print(f"[{idx}/15] Testing Proxy: {proxy}")
        try:
            proxy_handler = urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request(mpd_url, headers=headers)
            
            with opener.open(req, timeout=6) as res:
                if res.status == 200:
                    print(f"\n[SUCCESS] Proxy {proxy} passed! Bypassed geo-block successfully.")
                    return proxy
        except urllib.error.HTTPError as e:
            print(f"   └─ [EXACT FAIL] HTTP {e.code}: Token expired or proxy IP flagged by Jio.")
        except urllib.error.URLError as e:
            print(f"   └─ [EXACT FAIL] Proxy Connection Refused / Timeout ({e.reason})")
        except Exception as e:
            print(f"   └─ [EXACT FAIL] {e}")

    return None

def run_ffmpeg_telegram():
    cookie = clean_env_var("COOKIE_HEADER")
    cenc_key = clean_env_var("CENC_KEY")
    mpd_url = clean_env_var("MPD_URL", "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd")
    telegram_rtmp = clean_env_var("TELEGRAM_RTMP_URL")

    if not telegram_rtmp:
        print("[!] FATAL ERROR: TELEGRAM_RTMP_URL environment variable is missing!")
        sys.exit(1)

    # Fetch live proxy list from API
    proxy_list = fetch_fresh_indian_proxies()
    
    # Run diagnostic tests and select functional proxy
    selected_proxy = diagnose_and_find_proxy(mpd_url, cookie, proxy_list)

    if not selected_proxy:
        print("\n========================================================")
        print("[!] FATAL DIAGNOSTIC SUMMARY:")
        print(" 1. Free public proxies on ProxyScrape are unstable/dead.")
        print(" 2. Your COOKIE_HEADER token may have expired.")
        print("========================================================")
        sys.exit(1)

    # Build FFmpeg execution arguments
    cmd = ["ffmpeg", "-y"]

    if selected_proxy != "DIRECT":
        cmd.extend(["-http_proxy", selected_proxy])

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

    print(f"\n[+] Executing FFmpeg using proxy mode: {selected_proxy}")
    sys.stdout.flush()

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    for line in process.stdout:
        print(line, end="")
        sys.stdout.flush()

    process.wait()

if __name__ == "__main__":
    run_ffmpeg_telegram()
