import os
import sys
import time
import requests
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==============================================================================
# 1. RENDER HEALTH CHECK SERVER
# ==============================================================================
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
    print(f"[+] Health check server running on port {port}")
    server.serve_forever()

threading.Thread(target=start_health_check_server, daemon=True).start()

# ==============================================================================
# 2. PROXY FETCHING & INDIAN IP FILTERING
# ==============================================================================
PROXIES_JSON_URL = "https://raw.githubusercontent.com/abusaeeidx/TazaProxy-Troxy/refs/heads/main/working_proxies.json"

def get_best_indian_proxy():
    """
    Fetches the JSON proxy list, checks IP locations, and returns an active Indian proxy.
    """
    print("[+] Fetching fresh proxy list...")
    try:
        response = requests.get(PROXIES_JSON_URL, timeout=10)
        if response.status_code != 200:
            print(f"[!] Failed to download proxy list. Status: {response.status_code}")
            return None
        
        proxy_list = response.json()
        print(f"[+] Total proxies in feed: {len(proxy_list)}")
    except Exception as e:
        print(f"[!] Error fetching proxies: {e}")
        return None

    # Filter proxies with usable latency (e.g., < 3000ms)
    filtered_proxies = [p for p in proxy_list if p.get("latency", 5000) < 3000]

    for entry in filtered_proxies:
        raw_proxy = entry.get("proxy")
        if not raw_proxy:
            continue
        
        # Ensure proxy protocol format
        proxy_url = raw_proxy if raw_proxy.startswith("http") else f"http://{raw_proxy}"
        
        try:
            # Check IP Geolocation via API
            geo_req = requests.get(
                "http://ip-api.com/json",
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=5
            )
            geo_data = geo_req.json()
            
            # Match Indian Location
            if geo_data.get("countryCode") == "IN":
                print(f"[✓] Found Working Indian Proxy: {proxy_url} ({geo_data.get('city', 'India')}) - Latency: {entry.get('latency')}ms")
                return proxy_url
        except Exception:
            # Skip unreachable or non-responsive proxies
            continue

    print("[!] No working Indian proxies found in this fetch cycle.")
    return None

# ==============================================================================
# 3. MAIN FFMPEG STREAMING ENGINE
# ==============================================================================
def clean_env_var(var_name, default=""):
    return os.environ.get(var_name, default).strip().strip('"\'[]()')

def run_stream():
    cookie = clean_env_var("COOKIE_HEADER")
    cenc_key = clean_env_var("CENC_KEY")
    mpd_url = clean_env_var("MPD_URL", "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd")
    telegram_rtmp = clean_env_var("TELEGRAM_RTMP_URL")
    
    if not telegram_rtmp:
        print("[!] ERROR: TELEGRAM_RTMP_URL environment variable is missing!")
        sys.exit(1)

    while True:
        # Get dynamic working proxy
        proxy = get_best_indian_proxy()
        
        if not proxy:
            print("[!] Retry fetching proxy in 10 seconds...")
            time.sleep(10)
            continue

        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "warning",
            # Increased buffer sizes to handle public proxy latency
            "-buffer_size", "15400k",
            "-analyseduration", "10000000",
            "-probesize", "10000000",
            # Reconnect & stream recovery options
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "3",
            # Proxy Configuration
            "-http_proxy", proxy,
            "-headers", f"Cookie: {cookie}\r\n",
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "-cenc_decryption_key", cenc_key,
            "-i", mpd_url,
            "-map", "0:v:0",  # Low/Medium representation track mapping
            "-map", "0:a:0",
            "-c:v", "copy",
            "-c:a", "copy",
            "-flvflags", "no_duration_filesize",
            "-f", "flv",
            telegram_rtmp
        ]

        print(f"[+] Starting FFmpeg process using Proxy: {proxy}")
        sys.stdout.flush()

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )

        for line in process.stdout:
            print(line, end="")
            sys.stdout.flush()

        process.wait()
        print("[!] Stream disconnected. Finding a new proxy and restarting...")
        time.sleep(3)

if __name__ == "__main__":
    run_stream()
