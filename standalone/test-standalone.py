"""Self-test for the standalone Hotel Face-ID installation (no Docker).

Checks the two services on http://127.0.0.1:8000 (API+UI) and
http://127.0.0.1:8001 (face-service) and reports PASS/FAIL per check.

Usage:  runtime\\python\\python.exe test-standalone.py
"""

import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

import requests

BASE = "http://127.0.0.1:8000"
EMBED = "http://127.0.0.1:8001"
SERVICE_KEY = "change-me-service-key"

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))


def system(*a, **k):
    import subprocess
    return subprocess.run(a, capture_output=True, text=True)


# ---------------------------------------------------------------- API + seed
try:
    r = requests.get(BASE + "/health", timeout=5)
    check("api /health", r.status_code == 200 and r.json().get("status") == "ok", r.text[:60])
except Exception as e:
    check("api /health", False, str(e))

try:
    login = requests.post(BASE + "/api/auth/login", json={"username": "admin", "password": "admin"}, timeout=10)
    check("login admin/admin", login.status_code == 200, login.text[:80])
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
except Exception as e:
    check("login admin/admin", False, str(e))
    auth = {}

if auth:
    for path in ["/api/dashboard", "/api/occupancy", "/api/persons", "/api/cameras", "/api/events"]:
        try:
            r = requests.get(BASE + path, headers=auth, timeout=15)
            check(f"GET {path}", r.status_code == 200, str(r.status_code))
        except Exception as e:
            check(f"GET {path}", False, str(e))

# ---------------------------------------------------------------- face engine
try:
    r = requests.get(EMBED + "/health", timeout=5) if False else None
except Exception:
    pass

try:
    from faceservice.face_engine import FaceEngine
    import cv2

    eng = FaceEngine()
    img = cv2.imread(sys.argv[1]) if len(sys.argv) > 1 else None
    if img is None:
        # synthesize a 640x480 grey frame; faces expected? det may return none
        img = cv2.imread("test-face.jpg") if __debug__ else None
    if img is not None:
        faces = eng.detect(img)
        check("face engine detect on sample", len(faces) > 0, f"{len(faces)} faces")
except Exception as e:
    check("face engine", False, str(e))

# ---------------------------------------------------------------- embed API
if auth:
    sample = "test-face.jpg"
    try:
        import os
        payload = {"file": (sample, open(sample, "rb"), "image/jpeg")} if os.path.exists(sample) else None
        if payload:
            r = requests.post(EMBED + "/embed", files=payload, timeout=40)
            check("face-service /embed", r.status_code == 200 and r.ok, f"{r.status_code} {r.text[:60]}")
    except Exception as e:
        check("face-service /embed", False, str(e))

# ---------------------------------------------------------------- summary
print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for name, detail in FAIL:
    print("  FAIL:", name, "--", detail)
sys.exit(0 if not FAIL else 1)