import os
import json
import base64
import requests
import subprocess
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

def run_stream():
    # 1. Fetch Environment Variables
    secure_url = os.environ.get("SECURE_PHP_URL")
    secret_key = os.environ.get("SECRET_KEY", "12345678901234567890123456789012")
    referer = os.environ.get("REFERER_HEADER", "https://bb10.html-5.me/player.html")
    telegram_rtmp = os.environ.get("TELEGRAM_RTMP_URL")

    if not secure_url or not telegram_rtmp:
        raise ValueError("Missing SECURE_PHP_URL or TELEGRAM_RTMP_URL in environment variables.")

    print("[+] Fetching payload from PHP API...")
    headers = {
        "Referer": referer,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    res = requests.get(secure_url, headers=headers)
    res.raise_for_status()
    
    # 2. Extract Base64 Encrypted Payload
    encrypted_base64 = res.json().get("data")
    raw_data = base64.b64decode(encrypted_base64)

    # 3. Decrypt AES-256-CBC Payload
    iv = raw_data[:16]
    ciphertext = raw_data[16:]
    
    cipher = AES.new(secret_key.encode('utf-8'), AES.MODE_CBC, iv)
    decrypted_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
    payload = json.loads(decrypted_bytes.decode('utf-8'))

    stream_url = payload.get("url")
    cookie = payload.get("cookie", "")
    clearkeys = payload.get("clearKeys", {})

    print(f"[+] Decrypted Stream URL: {stream_url}")

    # 4. Format ClearKey Credentials
    clearkey_args = []
    if clearkeys:
        for kid, key in clearkeys.items():
            clearkey_args.extend(["--clearkey-auth", f"{kid}:{key}"])

    # 5. Build Streamlink + FFmpeg Command Pipeline
    streamlink_cmd = [
        "streamlink",
        "--http-header", f"Cookie={cookie}",
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

    print("[+] Starting Live Stream to Telegram...")
    
    # Pipe output from Streamlink into FFmpeg input
    p1 = subprocess.Popen(streamlink_cmd, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(ffmpeg_cmd, stdin=p1.stdout)
    p1.stdout.close()
    p2.communicate()

if __name__ == "__main__":
    run_stream()
