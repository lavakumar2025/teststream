import os
import sys
import subprocess
import urllib.parse
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==============================================================================
# 1. RENDER HEALTH CHECK SERVER
# ==============================================================================
# Prevents Render from shutting down due to "No open ports detected"
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Live Streamer Active")

    def log_message(self, format, *args):
        return  # Suppress health check server logs in stdout

def start_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"[+] Health check server listening on port {port}")
    server.serve_forever()

# Start port listener in a background thread
threading.Thread(target=start_health_check_server, daemon=True).start()

# ==============================================================================
# 2. UTILITY FUNCTIONS
# ==============================================================================
def clean_env_var(var_name, default=""):
    """Clean and strip quotes or brackets from environment variables."""
    value = os.environ.get(var_name, default).strip()
    return value.strip('"\'[]()')

def get_cloudflare_proxied_url(target_url, worker_url, cookie):
    """
    Wraps the target stream/manifest URL inside the Cloudflare Worker endpoint.
    Example output: https://my-worker.workers.dev/?url=HTTPS_TARGET&cookie=COOKIES
    """
    # Ensure worker URL ends with a slash before adding parameters
    base_worker = worker_url if worker_url.endswith("/") else f"{worker_url}/"
    
    params = {
        "url": target_url,
        "cookie": cookie
    }
    return f"{base_worker}?{urllib.parse.urlencode(params)}"

def get_video_stream_map(quality_setting):
    """
    Maps quality environment variable levels to stream representation tracks:
    - low: Stream track index 0
    - medium: Stream track index 1 (Default)
    - high: Stream track index 2
    """
    quality = quality_setting.lower()
    
    if quality == "low":
        print("[+] Stream Quality Configured: LOW")
        return "0:v:0"
    elif quality == "high":
        print("[+] Stream Quality Configured: HIGH")
        return "0:v:2"
    else:
        print("[+] Stream Quality Configured: MEDIUM")
        return "0:v:1"

# ==============================================================================
# 3. MAIN FFMPEG STREAMING ENGINE
# ==============================================================================
def run_ffmpeg():
    # Fetch Environment Variables
    cookie = clean_env_var("COOKIE_HEADER")
    cenc_key = clean_env_var("CENC_KEY")
    mpd_url = clean_env_var("MPD_URL", "https://jiotvmblive.cdn.jio.com/bpk-tv/Maa_HD_MOB/WDVLive/index.mpd")
    telegram_rtmp = clean_env_var("TELEGRAM_RTMP_URL")
    quality_env = clean_env_var("QUALITY", "medium")
    worker_url = clean_env_var("WORKER_URL")  # e.g., https://your-worker.workers.dev

    # Validate mandatory parameters
    if not telegram_rtmp:
        print("[!] ERROR: TELEGRAM_RTMP_URL environment variable is missing!")
        sys.exit(1)

    if not worker_url:
        print("[!] ERROR: WORKER_URL environment variable is missing!")
        print("Please deploy the Cloudflare Worker and set WORKER_URL=https://your-worker.workers.dev")
        sys.exit(1)

    video_map = get_video_stream_map(quality_env)
    
    # Construct the Cloudflare Worker URL
    proxied_mpd_url = get_cloudflare_proxied_url(mpd_url, worker_url, cookie)

    while True:
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel", "info",
            # Network reconnect & stability flags
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-buffer_size", "10240k",
            "-fflags", "+genpts+discardcorrupt",
            "-max_delay", "5000000",
            # Stream identification & DRM decryption
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "-cenc_decryption_key", cenc_key,
            # Input stream routed through Cloudflare Worker
            "-i", proxied_mpd_url,
            # Stream mapping
            "-map", video_map,
            "-map", "0:a:0",
            "-c:v", "copy",
            "-c:a", "copy",
            # FLV output flags for smooth RTMP ingestion
            "-flvflags", "no_duration_filesize",
            "-f", "flv",
            telegram_rtmp
        ]

        print(f"[+] Launching Stream via Cloudflare Worker ({quality_env.upper()} Quality)...")
        print(f"[+] Worker Endpoint: {worker_url}")
        sys.stdout.flush()

        # Run FFmpeg process and stream logs to output
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
        print("[!] FFmpeg stream connection ended. Restarting stream in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    run_ffmpeg()
