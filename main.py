import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
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
    print(f"[+] Health check server bound to port {port}")
    server.serve_forever()

threading.Thread(target=start_health_check_server, daemon=True).start()

# ==============================================================================
# 2. PROXY FETCHING & INDIAN GEOLOCATION CHECK (NATIVE URLLIB)
# ==============================================================================
PROXIES_JSON_URL = "https://raw.githubusercontent.com/abusaeeidx/TazaProxy-Troxy/refs/heads/main/working_proxies.json"

def clean_env_var(var_name, default=""):
    value = os.environ.get(var_name, default).strip()
    return value.strip('"\'[]()')

def fetch_json_proxies():
    """Fetches and parses the JSON proxy list using standard urllib."""
    print("[+] Fetching fresh proxy JSON from GitHub...")
    try:
        req = urllib.request.Request(PROXIES_JSON_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            if res.status == 200:
                data = json.loads(res.read().decode("utf-8"))
                print(f"[+] Retrieved {len(data)} total proxies from source.")
                return data
    except Exception as e:
        print(f"[!] Error downloading proxy JSON: {e}")
    return []

def verify_indian_ip(proxy_url):
    """
    Checks via ip-api.com if the proxy routes through India (countryCode == 'IN').
    """
    geo_url = "http://ip-api.com/json"
    try:
        proxy_handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request(geo_url, headers={"User-Agent": "Mozilla/5.0"})
        
        with opener.open(req, timeout=5) as res:
            if res.status == 200:
                geo_data = json.loads(res.read().decode("utf-8"))
                if geo_data.get("countryCode") == "IN":
                    print(f"[✓] Verified Indian Proxy: {proxy_url} ({geo_data.get('city', 'India')})")
                    return True
    except Exception:
        pass
    return False

def get_best_indian_proxy():
    proxy_entries = fetch_json_proxies()
    
    # Filter proxies by latency (< 3500ms)
    filtered = [p for p in proxy_entries if p.get("latency", 5000) < 3500]

    for entry in filtered[:25]:  # Test first 25 low-latency entries
        raw_proxy = entry.get("proxy")
        if not raw_proxy:
            continue
        
        # Ensure proxy protocol format
        proxy_url = raw_proxy if raw_proxy.startswith("http") else f"http://{raw_proxy}"
        
        print(f"[+] Verifying location for: {proxy_url}")
        if verify_indian_ip(proxy_url):
            return proxy_url

    print("[!] No responsive Indian proxies found in this cycle.")
    return None

# ==============================================================================
# 3. STREAM QUALITY MAPPING & FFMPEG ENGINE
# ==============================================================================
def get_video_stream_map(quality_setting):
    quality = quality_setting.lower()
    if quality == "low":
        print("[+] Stream Quality Set To: LOW")
        return "0:v:0"
    elif quality == "high":
        print("[+] Stream Quality Set To: HIGH")
        return "0:v:2"
    else:
        print("[+] Stream Quality Set To: MEDIUM")
        return "0:v:1"

def run_ffmpeg():
    cookie = clean_env_var("COOKIE_HEADER")
    cenc_key = clean_env_var("CENC_KEY")
    mpd_url = clean_env_var("MPD_URL", "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd")
    telegram_rtmp = clean_env_var("TELEGRAM_RTMP_URL")
    quality_env = clean_env_var("QUALITY", "medium")

    if not telegram_rtmp:
        print("[!] ERROR: TELEGRAM_RTMP_URL is missing!")
        sys.exit(1)

    video_map = get_video_stream_map(quality_env)

    while True:
        working_proxy = get_best_indian_proxy()

        if not working_proxy:
            print("[!] No valid Indian proxies available. Retrying in 10s...")
            time.sleep(10)
            continue

        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "warning",
            # Buffer settings to minimize stutter over public proxies
            "-buffer_size", "15400k",
            "-analyseduration", "10000000",
            "-probesize", "10000000",
            # Reconnect rules
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "3",
            # Proxy and Headers
            "-http_proxy", working_proxy,
            "-headers", f"Cookie: {cookie}\r\n",
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "-cenc_decryption_key", cenc_key,
            "-i", mpd_url,
            "-map", video_map,
            "-map", "0:a:0",
            "-c:v", "copy",
            "-c:a", "copy",
            "-flvflags", "no_duration_filesize",
            "-f", "flv",
            telegram_rtmp
        ]

        print(f"[+] Launching stream ({quality_env.upper()}) via {working_proxy}...")
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
        print("[!] FFmpeg stream disconnected. Finding a new proxy...")
        time.sleep(3)

if __name__ == "__main__":
    run_ffmpeg()
