import json, base64, time, sys

token_path = sys.argv[1]
with open(token_path) as f:
    for line in f:
        if line.startswith("#") or not line.strip():
            continue
        parts = line.strip().split("\t")
        if len(parts) >= 7 and parts[5] == "reposage_refresh":
            token = parts[6]
            payload_b64 = token.split(".")[1] + "=="
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            # Don't print the token itself, only the parsed claims
            safe = {k: v for k, v in payload.items()}
            safe["exp_in_seconds"] = int(payload["exp"] - time.time())
            print("claims:", safe)
            print("expires_at_iso:", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(payload["exp"])))
            print("now_iso:", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            break
