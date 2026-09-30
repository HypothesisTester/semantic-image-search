"""End-to-end check of the running Docker stack, with real sign-in and the real model.

    python scripts/smoke_test.py

Run from backend/ after `docker compose up`. It:
  1. waits for both services to be healthy, and checks unsigned requests get 401
  2. creates a throwaway Firebase user (email/password sign-in must be enabled)
  3. uploads 20 COCO val2017 photos to the indexer in one request
  4. searches with one human-written caption per photo and reports how often
     the right photo comes back first and in the top 5
  5. checks a second user sees none of those photos, re-uploads are idempotent,
     and result links serve JPEGs
  6. queries the demo service too, if it is running
  7. deletes the throwaway users, even if a check failed

Needs the COCO data from `python -m bench.download_coco`.
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
import time
from pathlib import Path

import requests

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from bench.coco import DEFAULT_DATA_DIR, CocoPaths, load_split  # noqa: E402

FIREBASE_CONFIG = BACKEND.parent / "frontend" / "src" / "config" / "firebase.ts"
IDENTITY = "https://identitytoolkit.googleapis.com/v1/accounts"


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{f'  ({detail})' if detail else ''}")
        if not ok:
            self.failures.append(label)
        return ok


class FirebaseUsers:
    """Creates and deletes throwaway email/password users via Firebase's REST API."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.tokens: list[str] = []

    def create(self) -> str:
        email = f"smoke-{secrets.token_hex(6)}@example.com"
        resp = requests.post(
            f"{IDENTITY}:signUp",
            params={"key": self.api_key},
            json={"email": email, "password": secrets.token_urlsafe(18), "returnSecureToken": True},
            timeout=15,
        )
        if resp.status_code != 200:
            raise SystemExit(f"could not create a Firebase test user: {resp.text}")
        token = resp.json()["idToken"]
        self.tokens.append(token)
        return token

    def delete_all(self) -> None:
        for token in self.tokens:
            requests.post(f"{IDENTITY}:delete", params={"key": self.api_key}, json={"idToken": token}, timeout=15)


class FakeUsers:
    """For testing this script against services running with the test fakes."""

    def __init__(self) -> None:
        self.tokens: list[str] = []

    def create(self) -> str:
        token = f"token-smoke{secrets.token_hex(4)}"
        self.tokens.append(token)
        return token

    def delete_all(self) -> None:
        pass


def api_key_from_frontend() -> str:
    match = re.search(r'apiKey:\s*"([^"]+)"', FIREBASE_CONFIG.read_text())
    if not match:
        raise SystemExit(f"no apiKey found in {FIREBASE_CONFIG}; pass --api-key")
    return match.group(1)


def wait_healthy(url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if requests.get(f"{url}/healthz", timeout=3).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(2)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--indexer", default="http://localhost:8001")
    parser.add_argument("--search", default="http://localhost:8002")
    parser.add_argument("--demo", default="http://localhost:8003")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--photos", type=int, default=20)
    parser.add_argument("--api-key", default=None, help="Firebase web API key (default: read from the frontend config)")
    parser.add_argument("--fake-tokens", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    checks = Checks()
    paths = CocoPaths(args.data_dir)
    if not paths.captions.exists():
        raise SystemExit("COCO data not found: run `python -m bench.download_coco` first")
    split = load_split(paths)

    print("services")
    for name, url in (("indexer", args.indexer), ("search", args.search)):
        if not checks.check(wait_healthy(url, 180), f"{name} is healthy at {url}"):
            print("\nIs `docker compose up` running? `docker compose logs` shows why a service is down.")
            return 1
    r = requests.post(f"{args.search}/search", json={"text": "a dog"}, timeout=15)
    checks.check(r.status_code == 401, "search without sign-in is refused", f"HTTP {r.status_code}")
    r = requests.post(f"{args.indexer}/upload", files=[("files", ("x.jpg", b"x"))], timeout=15)
    checks.check(r.status_code == 401, "upload without sign-in is refused", f"HTTP {r.status_code}")

    users = FakeUsers() if args.fake_tokens else FirebaseUsers(args.api_key or api_key_from_frontend())
    try:
        alice = {"Authorization": f"Bearer {users.create()}"}
        bob = {"Authorization": f"Bearer {users.create()}"}

        # Spread the picks across the whole set rather than taking the first N.
        step = max(1, len(split.file_names) // args.photos)
        picks = list(range(0, len(split.file_names), step))[: args.photos]
        names = [split.file_names[i] for i in picks]
        first_caption = {}
        for caption, image in zip(split.captions, split.caption_image):
            first_caption.setdefault(image, caption)

        print(f"\nupload {len(names)} photos")
        start = time.perf_counter()
        r = requests.post(
            f"{args.indexer}/upload",
            headers=alice,
            files=[("files", (n, (paths.images / n).read_bytes(), "image/jpeg")) for n in names],
            timeout=300,
        )
        elapsed = time.perf_counter() - start
        if not checks.check(r.status_code == 200, "upload accepted", f"HTTP {r.status_code}"):
            print(r.text[:500])
            return 1
        body = r.json()
        checks.check(
            body["added"] == len(names) and body["failed"] == 0,
            f"all {len(names)} photos indexed",
            f"added {body['added']}, failed {body['failed']}, {elapsed:.1f}s, {len(names) / elapsed:.1f} photos/s",
        )
        id_of = {res["filename"]: res["id"] for res in body["results"] if res["ok"]}

        print(f"\nsearch with one caption per photo, over a library of {len(names)}")
        top1 = top5 = 0
        latencies = []
        for i, name in zip(picks, names):
            caption = first_caption[i]
            start = time.perf_counter()
            r = requests.post(f"{args.search}/search", headers=alice, json={"text": caption, "k": 5}, timeout=30)
            latencies.append(time.perf_counter() - start)
            ranked = [res["url"] for res in r.json()["results"]]
            hit = next((rank for rank, url in enumerate(ranked, 1) if f"/{id_of.get(name)}/" in url), None)
            top1 += hit == 1
            top5 += hit is not None
            if i == picks[0]:
                example = (caption, hit)
        latencies.sort()
        p50 = latencies[len(latencies) // 2] * 1000
        where = f"came back at rank {example[1]}" if example[1] else "was not in the top 5"
        print(f'  e.g. "{example[0]}" -> its photo {where}')
        checks.check(top5 >= 0.8 * len(names) or args.fake_tokens, "the right photo is usually in the top 5",
                     f"top 1: {top1}/{len(names)}, top 5: {top5}/{len(names)}, p50 {p50:.0f} ms over HTTP")

        print("\nisolation, idempotency, photo links")
        r = requests.post(f"{args.search}/search", headers=bob, json={"text": first_caption[picks[0]], "k": 10}, timeout=30)
        checks.check(r.json() == {"results": []}, "another user sees none of these photos")
        r = requests.post(
            f"{args.indexer}/upload", headers=alice,
            files=[("files", (names[0], (paths.images / names[0]).read_bytes(), "image/jpeg"))], timeout=60,
        )
        checks.check(r.json()["updated"] == 1 and r.json()["added"] == 0, "re-uploading a photo replaces it")
        top = requests.post(f"{args.search}/search", headers=alice, json={"text": "a photo", "k": 1}, timeout=30).json()["results"][0]
        photo = requests.get(top["url"], timeout=15)
        checks.check(
            photo.status_code == 200 and photo.headers.get("content-type") == "image/jpeg",
            "result links serve JPEGs", top["url"],
        )
    finally:
        users.delete_all()

    print("\ndemo")
    if wait_healthy(args.demo, 5):
        r = requests.post(f"{args.demo}/search", json={"text": "a dog catching a frisbee", "k": 3}, timeout=30)
        ok = r.status_code == 200 and len(r.json()["results"]) == 3
        checks.check(ok, "demo search works without sign-in")
        if ok:
            for res in r.json()["results"]:
                print(f"        {res['score']:.3f}  {res.get('caption', '')}")
    else:
        print("  skipped (start it with: docker compose --profile demo up)")

    print(f"\n{'ALL CHECKS PASSED' if not checks.failures else f'{len(checks.failures)} FAILED: ' + ', '.join(checks.failures)}")
    return 1 if checks.failures else 0


if __name__ == "__main__":
    sys.exit(main())
