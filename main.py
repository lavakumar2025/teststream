import os
import json
import base64
import requests
import subprocess
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

def run_stream():
    # 1. Check Toggle Mode (true/false)
    use_secure_php = os.environ.get("USE_SECURE_PHP", "true").lower() in ["true", "1", "yes"]
    telegram_rtmp = os.environ.get("TELEGRAM_RTMP_URL")

    if not telegram_rtmp:
        raise ValueError("Missing TELEGRAM_RTMP_URL in environment variables.")

    stream_url = ""
    cookie = ""
    clearkeys = {}

    if use_secure_php:
        print("[+] Mode: Fetching dynamically from secure.php API...")
        secure_url = os.environ.get("SECURE_PHP_URL")
        secret_key = os.environ.get("SECRET_KEY", "12345678901234567890123456789012")
        referer = os.environ.get("REFERER_HEADER", "https://bb10.html-5.me/player.html")

        if not secure_url:
            raise ValueError("USE_SECURE_PHP is true, but SECURE_PHP_URL environment variable is missing.")

        headers = {
            "Referer": referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        res = requests.get(secure_url, headers=headers, timeout=15)
        print(f"[+] PHP Response Status: {res.status_code}")
        
        if res.status_code != 200:
            print(f"[-] PHP Script returned error. Response content:\n{res.text}")
            res.raise_for_status()

        try:
            data = res.json()
        except Exception as e:
            print(f"[-] Failed to parse JSON. Raw output from PHP:\n{res.text}")
            raise e

        encrypted_base64 = data.get("data")
        if not encrypted_base64:
            raise ValueError(f"[-] 'data' field missing in JSON response: {data}")

        # Decrypt AES-256-CBC Payload
        raw_data = base64.b64decode(encrypted_base64)
        iv = raw_data[:16]
        ciphertext = raw_data[16:]
        
        cipher = AES.new(secret_key.encode('utf-8'), AES.MODE_CBC, iv)
        decrypted_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
        payload = json.loads(decrypted_bytes.decode('utf-8'))

        stream_url = payload.get("url")
        cookie = payload.get("cookie", "")
        clearkeys = payload.get("clearKeys", {})

    else:
        print("[+] Mode: Using manual MPD URL, Keys, and Cookie environment variables...")
        stream_url = os.environ.get("MPD_URL")
        cookie = os.environ.get("COOKIE_HEADER", "")
        raw_keys = os.environ.get("CLEARKEYS_JSON", "") # Format: {"KID":"KEY"} or "KID:KEY"

        if not stream_url:
            raise ValueError("USE_SECURE_PHP is false, but MPD_URL environment variable is missing.")

        # Parse DRM Keys
        if raw_keys:
            try:
                # Try parsing as JSON format: {"6c4b7825...": "983ecd2f..."}
                clearkeys = json.loads(raw_keys)
            except Exception:
                # Fallback parse as simple "KID:KEY" string
                if ":" in raw_keys:
                    k_id, k_val = raw_keys.split(":", 1)
                    clearkeys = {k_id.strip(): k_val.strip()}

    print(f"[+] Active Stream URL: {stream_url}")

    # Format ClearKey Credentials for Streamlink
    clearkey_args = []
    if clearkeys and isinstance(clearkeys, dict):
        for kid, key in clearkeys.items():
            clearkey_args.extend(["--clearkey-auth", f"{kid}:{key}"])

    # Build Streamlink + FFmpeg Pipeline
    streamlink_cmd = [
        "streamlink",
        "--http-header", f"Cookie={cookie}",
        "--http-header", "User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        *clearkey_args,
        stream_url,
        "best",
        "-O"
    ]

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", "pipe:0",
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

    print("[+] Starting Streamlink -> FFmpeg -> Telegram pipeline...")
    
    p1 = subprocess.Popen(streamlink_cmd, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout)
    p1.stdout.close()
    p2.communicate()

if __name__ == "__main__":
    run_stream()
