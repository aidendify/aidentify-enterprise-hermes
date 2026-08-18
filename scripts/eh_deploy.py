"""Deploy enterprise-hermes to Hostinger Docker API (raw POST)."""
import json
import sys
sys.path.insert(0, "/opt/data/aidentify/scripts")
import hostinger_api as h

# Browser UA to avoid Cloudflare bot-block on POST /docker
h.APP_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "Chrome/124.0 Safari/537.36")
# Override req headers with UA
import urllib.request

_orig_req = h.req
def _req(method, path, token, body=None, timeout=60, ua=h.APP_UA):
    url = h.API_BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": ua,
    })
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        raw = resp.read().decode()
        try:
            return resp.status, json.loads(raw)
        except json.JSONDecodeError:
            return resp.status, raw

h.req = _req

token = h.get_token()
print("token loaded:", bool(token), "len", len(token))
code, data = h.req("POST", "/api/vps/v1/virtual-machines/1894385/docker", token,
                   {"project_name": "enterprise-hermes",
                    "content": "https://github.com/aidendify/aidentify-enterprise-hermes.git"})
print("HTTP", code)
print(json.dumps(data, indent=2)[:600])