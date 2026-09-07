import os
import sys
import subprocess
import urllib.request
import urllib.error
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Live Streamer Active")
    
    def log_message(self, format, *args):
        return

def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"[+] Health check server bound to port {port}")
    server.serve_forever()

threading.Thread(target=start_health_check_server, daemon=True).start()

PROXYSCRAPE_URL = "https://bykw.short.gy/N6zdOH"

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

def test_proxy_robust(mpd_url, cookie, proxy):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cookie": cookie
    }
    try:
        proxy_handler = urllib.request.ProxyHandler({'http': proxy, 'https': proxy})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(mpd_url, headers=headers)
        with opener.open(req, timeout=6) as res:
            if res.status == 200:
                content = res.read(1024)
                if b"<MPD" in content or b"xml" in content:
                    return True
    except Exception:
        pass
    return False

def get_video_stream_map(quality_setting):
    """
    Maps quality levels to DASH stream indices:
    - low: Lowest bitrate track (Index 0 or last depending on MPD structure)
    - medium: Mid-tier stream
    - high: Highest resolution / bitrate track
    """
    quality = quality_setting.lower()
    
    if quality == "low":
        # Selects lowest bitrate stream representation
        print("[+] Stream Quality Set To: LOW")
        return "0:v:0"
    elif quality == "high":
        # Selects highest bitrate representation (or highest stream index)
        print("[+] Stream Quality Set To: HIGH")
        return "0:v:2"
    else:
        # Default to MEDIUM
        print("[+] Stream Quality Set To: MEDIUM")
        return "0:v:1"

def run_ffmpeg():
    cookie = clean_env_var("COOKIE_HEADER")
    cenc_key = clean_env_var("CENC_KEY")
    mpd_url = clean_env_var("MPD_URL", "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd")
    telegram_rtmp = clean_env_var("TELEGRAM_RTMP_URL")
    quality_env = clean_env_var("QUALITY", "medium")

    if not telegram_rtmp:
        print("[!] TELEGRAM_RTMP_URL missing!")
        sys.exit(1)

    video_map = get_video_stream_map(quality_env)

    while True:
        proxies = fetch_fresh_indian_proxies()
        working_proxy = None

        for proxy in proxies[:20]:
            print(f"[+] Testing proxy: {proxy}")
            if test_proxy_robust(mpd_url, cookie, proxy):
                working_proxy = proxy
                print(f"[SUCCESS] Selected Proxy: {proxy}")
                break

        if not working_proxy:
            print("[!] No working proxies found. Retrying in 10s...")
            time.sleep(10)
            continue

        cmd = [
            "ffmpeg",
            "-y",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-fflags", "+genpts+discardcorrupt",
            "-max_delay", "5000000",
            "-http_proxy", working_proxy,
            "-headers", f"Cookie: {cookie}\r\n",
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "-cenc_decryption_key", cenc_key,
            "-i", mpd_url,
            "-map", video_map,
            "-map", "0:a:0",
            "-c:v", "copy",
            "-c:a", "copy",
            "-f", "flv",
            telegram_rtmp
        ]

        print(f"[+] Launching stream ({quality_env.upper()}) to Telegram via {working_proxy}...")
        sys.stdout.flush()

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

        for line in process.stdout:
            print(line, end="")
            sys.stdout.flush()

        process.wait()
        print("[!] FFmpeg process ended. Rotating proxy in 3 seconds...")
        time.sleep(3)

if __name__ == "__main__":
    run_ffmpeg()
