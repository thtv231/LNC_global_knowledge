import urllib.request, json, time, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

url = "http://localhost:8000/chat/stream"
data = json.dumps({"query": "Express Entry Canada diem toi thieu la bao nhieu?", "session_id": "test"}).encode()
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

t0 = time.time()
first_token_time = None
token_count = 0

with urllib.request.urlopen(req, timeout=90) as resp:
    for line in resp:
        line = line.decode("utf-8").strip()
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        payload = json.loads(line[6:])
        t = round(time.time() - t0, 2)
        if payload.get("type") == "status":
            print(f"[{t}s] STATUS: {payload['message']}")
        elif payload.get("type") == "token":
            if first_token_time is None:
                first_token_time = t
                print(f"[{t}s] FIRST TOKEN")
            token_count += 1
        elif payload.get("type") == "meta":
            print(f"[{round(time.time()-t0,2)}s] META, {token_count} tokens total")
        elif payload.get("type") == "error":
            print(f"ERROR: {payload}")

print(f"Total: {round(time.time()-t0,2)}s, first token at {first_token_time}s")
