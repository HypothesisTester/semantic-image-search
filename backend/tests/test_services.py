"""Indexer and search service tests, using a fake model and fake sign-in."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from common.photo_store import PhotoStore, photo_id
from services.config import Settings
from services.indexer import create_app as create_indexer
from services.search import create_app as create_search
from tests.fakes import FakeEncoder, FakeVerifier, auth


def jpeg(colour, size=(80, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, colour).save(buf, format="JPEG")
    return buf.getvalue()


def files(*items):
    """items: (filename, bytes) pairs -> the multipart 'files' field."""
    return [("files", (name, data, "application/octet-stream")) for name, data in items]


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", firebase_project_id="test", cors_origins=["http://localhost:5173"])


@pytest.fixture
def encoder():
    return FakeEncoder()


@pytest.fixture
def indexer(settings, encoder):
    with TestClient(create_indexer(settings, encoder=encoder, verifier=FakeVerifier())) as client:
        yield client


@pytest.fixture
def search(settings, encoder):
    # A separate app over the same data directory: the two services share
    # nothing but the volume, exactly as in Docker.
    with TestClient(create_search(settings, encoder=encoder, verifier=FakeVerifier())) as client:
        yield client


def upload(indexer, uid, *items):
    resp = indexer.post("/upload", files=files(*items), headers=auth(uid))
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---- sign-in -----------------------------------------------------------------


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nonsense"}, {"Authorization": "Basic x"}])
def test_both_services_require_sign_in(indexer, search, headers):
    r = indexer.post("/upload", files=files(("a.jpg", jpeg("red"))), headers=headers)
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    r = search.post("/search", json={"text": "red"}, headers=headers)
    assert r.status_code == 401


def test_user_id_in_the_body_is_ignored(indexer, search):
    upload(indexer, "alice", ("red.jpg", jpeg("red")))
    # Bob claims to be Alice in the body, as the old frontend's request allowed.
    r = search.post("/search", json={"text": "red", "userId": "alice"}, headers=auth("bob"))
    assert r.status_code == 200 and r.json() == {"results": []}


# ---- upload then search, across the two services ----------------------------


def test_upload_then_search_finds_the_right_photo(indexer, search):
    body = upload(indexer, "alice", ("red.jpg", jpeg("red")), ("blue.png", _png("blue")), ("green.jpg", jpeg("green")))
    assert (body["added"], body["updated"], body["failed"]) == (3, 0, 0)
    assert all(r["ok"] for r in body["results"])

    r = search.post("/search", json={"text": "a blue photo", "k": 2}, headers=auth("alice"))
    results = r.json()["results"]
    assert [x["rank"] for x in results] == [1, 2]
    blue_id = body["results"][1]["id"]
    assert results[0]["url"].endswith(f"/photos/alice/{blue_id}/display.jpg")
    assert results[0]["thumbnailUrl"].endswith(f"/photos/alice/{blue_id}/thumb.jpg")
    assert results[0]["score"] > results[1]["score"]

    # The returned link serves a real JPEG of the right photo.
    photo = search.get(results[0]["url"])
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    assert "immutable" in photo.headers["cache-control"]
    r_, g_, b_ = Image.open(io.BytesIO(photo.content)).convert("RGB").getpixel((5, 5))
    assert b_ > 200 and r_ < 50


def test_users_only_see_their_own_photos(indexer, search):
    upload(indexer, "alice", ("red.jpg", jpeg("red")))
    upload(indexer, "bob", ("blue.jpg", jpeg("blue")))
    alice = search.post("/search", json={"text": "blue", "k": 10}, headers=auth("alice")).json()["results"]
    assert len(alice) == 1 and "/photos/alice/" in alice[0]["url"]


def test_new_uploads_are_searchable_immediately(indexer, search):
    upload(indexer, "alice", ("red.jpg", jpeg("red")))
    first = search.post("/search", json={"text": "yellow"}, headers=auth("alice")).json()["results"]
    assert len(first) == 1  # the search service has now cached a 1-photo index
    yellow_id = upload(indexer, "alice", ("yellow.jpg", jpeg("yellow")))["results"][0]["id"]
    after = search.post("/search", json={"text": "yellow"}, headers=auth("alice")).json()["results"]
    assert len(after) == 2
    assert f"/photos/alice/{yellow_id}/" in after[0]["url"]


def test_a_user_with_no_photos_gets_no_results(search):
    assert search.post("/search", json={"text": "red"}, headers=auth("newuser")).json() == {"results": []}


# ---- upload details ----------------------------------------------------------------


def test_uploading_the_same_photo_twice_replaces_it(indexer, search):
    first = upload(indexer, "alice", ("IMG_1.jpg", jpeg("red")))
    second = upload(indexer, "alice", ("copy of IMG_1.jpg", jpeg("red")))
    assert (second["added"], second["updated"]) == (0, 1)
    assert first["results"][0]["id"] == second["results"][0]["id"]
    assert len(search.post("/search", json={"text": "red", "k": 10}, headers=auth("alice")).json()["results"]) == 1


def test_same_photo_from_two_users_gets_different_ids():
    data = jpeg("red")
    assert photo_id("alice", data) != photo_id("bob", data)
    assert len(photo_id("alice", data)) == 22


def test_bad_files_are_reported_and_the_rest_still_indexed(indexer):
    body = upload(indexer, "alice", ("good.jpg", jpeg("red")), ("notes.txt", b"not a photo"), ("empty.jpg", b""))
    assert (body["added"], body["failed"]) == (1, 2)
    good, notes, empty = body["results"]
    assert good["ok"] and good["filename"] == "good.jpg"
    assert notes == {"filename": "notes.txt", "ok": False, "error": "the file is not a supported image"}
    assert empty["ok"] is False and "empty" in empty["error"]


def test_a_request_with_only_bad_files_does_not_call_the_model(indexer, encoder):
    body = upload(indexer, "alice", ("notes.txt", b"nope"))
    assert body["added"] == 0 and body["failed"] == 1
    assert encoder.image_calls == 0


def test_all_photos_in_a_request_are_embedded_in_one_batch(indexer, encoder):
    upload(indexer, "alice", *[(f"{c}.jpg", jpeg(c)) for c in ("red", "green", "blue", "white")])
    assert encoder.image_calls == 1


def test_heic_uploads_get_a_browser_friendly_jpeg(indexer, settings):
    buf = io.BytesIO()
    try:
        Image.new("RGB", (64, 48), "green").save(buf, format="HEIF")
    except (KeyError, OSError, ValueError) as exc:
        pytest.skip(f"HEIF encoder unavailable: {exc}")
    body = upload(indexer, "alice", ("IMG_0001.HEIC", buf.getvalue()))
    result = body["results"][0]
    assert result["ok"]
    display = indexer.get(result["url"])
    assert display.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(display.content)).format == "JPEG"
    folder = settings.photos_dir / "alice" / result["id"]
    assert (folder / "original.heic").read_bytes() == buf.getvalue()  # original kept untouched


def test_renditions_are_resized(indexer):
    result = upload(indexer, "alice", ("big.jpg", jpeg("white", size=(4000, 3000))))["results"][0]
    display = Image.open(io.BytesIO(indexer.get(result["url"]).content))
    thumb = Image.open(io.BytesIO(indexer.get(result["thumbnailUrl"]).content))
    assert max(display.size) <= 2048 and max(thumb.size) <= 384


def test_too_many_files_is_rejected(tmp_path, encoder):
    s = Settings(data_dir=tmp_path, firebase_project_id="test", max_files_per_upload=2)
    with TestClient(create_indexer(s, encoder=encoder, verifier=FakeVerifier())) as client:
        r = client.post("/upload", files=files(*[(f"{i}.jpg", jpeg("red")) for i in range(3)]), headers=auth("a"))
    assert r.status_code == 413


def test_upload_without_files_is_rejected(indexer):
    assert indexer.post("/upload", headers=auth("alice")).status_code == 422


# ---- photo serving -------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/photos/alice/AAAAAAAAAAAAAAAAAAAAAA/display.jpg",  # well-formed but missing
        "/photos/alice/short/display.jpg",
        "/photos/alice/AAAAAAAAAAAAAAAAAAAAAA/original.jpg",  # originals are not served
        "/photos/..%2F..%2Fetc/AAAAAAAAAAAAAAAAAAAAAA/display.jpg",
        "/photos/alice/..%2F..%2F..%2Fetc%2Fpasswd/display.jpg",
    ],
)
def test_bad_photo_urls_are_404(indexer, path):
    upload(indexer, "alice", ("red.jpg", jpeg("red")))
    assert indexer.get(path).status_code == 404


def test_photo_store_cannot_be_tricked_into_reading_outside_its_folder(tmp_path):
    (tmp_path / "photos").mkdir()  # must exist, or "photos/.." cannot resolve at all
    store = PhotoStore(tmp_path / "photos")
    # A real file one level above the photo folder, shaped like a photo path.
    secret = tmp_path / "secret" / ("A" * 22)
    secret.mkdir(parents=True)
    (secret / "display.jpg").write_bytes(b"private")
    assert store.file_for("../secret", "A" * 22, "display") is None
    assert store.file_for("..", "secret", "display") is None
    with pytest.raises(ValueError):
        store.save("../evil", b"x", "a.jpg", Image.new("RGB", (4, 4)))


def test_originals_are_never_served_and_copies_carry_no_location(indexer, settings):
    # Phone photos often embed GPS coordinates in EXIF. The original is kept
    # on disk untouched, but only re-encoded copies without metadata are served.
    img = Image.new("RGB", (64, 48), "red")
    exif = img.getexif()
    exif[0x8825] = {1: "N", 2: (53.0, 20.0, 0.0), 3: "W", 4: (6.0, 15.0, 0.0)}  # GPS: Dublin
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    result = upload(indexer, "alice", ("dublin.jpg", buf.getvalue()))["results"][0]

    original = settings.photos_dir / "alice" / result["id"] / "original.jpg"
    assert original.read_bytes() == buf.getvalue()
    assert indexer.get(f"/photos/alice/{result['id']}/original.jpg").status_code == 404
    for url in (result["url"], result["thumbnailUrl"]):
        served = Image.open(io.BytesIO(indexer.get(url).content))
        assert 0x8825 not in served.getexif()


# ---- search input -----------------------------------------------------------------


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "   "}, {"text": "x" * 201}, {"text": "red", "k": 0}, {}])
def test_invalid_search_requests(search, body):
    assert search.post("/search", json=body, headers=auth("alice")).status_code == 422


def test_k_is_capped(indexer, tmp_path, encoder, settings):
    upload(indexer, "alice", *[(f"{i}.jpg", jpeg((i * 20, 0, 0))) for i in range(6)])
    capped = Settings(data_dir=settings.data_dir, firebase_project_id="test", max_k=3)
    with TestClient(create_search(capped, encoder=encoder, verifier=FakeVerifier())) as client:
        results = client.post("/search", json={"text": "red", "k": 100}, headers=auth("alice")).json()["results"]
    assert len(results) == 3


def test_query_whitespace_is_normalised(indexer, search):
    upload(indexer, "alice", ("red.jpg", jpeg("red")))
    r = search.post("/search", json={"text": "  a\n red   photo "}, headers=auth("alice"))
    assert r.status_code == 200 and len(r.json()["results"]) == 1


# ---- CORS and health ----------------------------------------------------------------


def test_cors_allows_only_the_configured_frontend(search):
    ok = search.options(
        "/search",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "authorization,content-type"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = search.options(
        "/search", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}
    )
    assert "access-control-allow-origin" not in bad.headers


def test_health(indexer, search):
    assert indexer.get("/healthz").json() == {"status": "ok"}
    assert search.get("/healthz").json() == {"status": "ok"}


def test_health_checks_are_left_out_of_the_access_log(indexer):
    import logging

    access = logging.getLogger("uvicorn.access")

    def record(path):
        # The same shape uvicorn uses for access-log lines.
        return logging.LogRecord(
            "uvicorn.access", logging.INFO, __file__, 0,
            '%s - "%s %s HTTP/%s" %d', ("127.0.0.1:5000", "GET", path, "1.1", 200), None,
        )

    assert not access.filter(record("/healthz"))
    assert access.filter(record("/search"))
    # Creating more apps does not stack up duplicate filters.
    assert sum(type(f).__name__ == "_HideHealthChecks" for f in access.filters) == 1


def test_photos_base_url_setting_is_used(tmp_path, encoder):
    s = Settings(data_dir=tmp_path, firebase_project_id="test", photos_base_url="https://photos.example")
    with TestClient(create_indexer(s, encoder=encoder, verifier=FakeVerifier())) as client:
        result = upload(client, "alice", ("red.jpg", jpeg("red")))["results"][0]
    assert result["url"].startswith("https://photos.example/photos/alice/")


def test_missing_firebase_project_fails_at_startup(tmp_path, encoder):
    s = Settings(data_dir=tmp_path, firebase_project_id=None)
    with pytest.raises(RuntimeError, match="FIREBASE_PROJECT_ID"):
        with TestClient(create_indexer(s, encoder=encoder)):
            pass


# ---- demo mode ---------------------------------------------------------------------


@pytest.fixture
def demo_dir(tmp_path, encoder):
    """A tiny demo dataset built the same way demo.build_index builds the real one."""
    from common.index_store import IndexStore

    root = tmp_path / "demo"
    thumbs = root / "thumbnails"
    thumbs.mkdir(parents=True)
    names, images = [], []
    for colour in ("red", "green", "blue"):
        name = f"{colour}.jpg"
        (thumbs / name).write_bytes(jpeg(colour))
        names.append(name)
        images.append(Image.new("RGB", (8, 8), colour))
    IndexStore(root / "index").add(
        "demo",
        [f"coco/val2017/{n}" for n in names],
        encoder.encode_images(images),
        metas=[{"url": f"/images/{n}", "caption": f"a {n[:-4]} thing"} for n in names],
    )
    return root


def test_demo_mode_needs_no_sign_in_and_serves_its_images(tmp_path, demo_dir, encoder):
    s = Settings(data_dir=tmp_path / "unused", demo_mode=True, demo_dir=demo_dir, max_k=20)
    with TestClient(create_search(s, encoder=encoder)) as client:
        r = client.post("/search", json={"text": "something green", "k": 50})
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) == 3  # k capped at 20, and only 3 images exist
        assert results[0]["caption"] == "a green thing"
        assert results[0]["url"].endswith("/images/green.jpg")
        image = client.get(results[0]["url"])
        assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
        # No user photos, and no way to upload, in demo mode.
        assert client.get("/photos/alice/AAAAAAAAAAAAAAAAAAAAAA/display.jpg").status_code == 404
        assert client.post("/upload").status_code in (404, 405)


def test_demo_browse_pages_through_every_photo_once(tmp_path, demo_dir, encoder):
    s = Settings(data_dir=tmp_path, demo_mode=True, demo_dir=demo_dir)
    with TestClient(create_search(s, encoder=encoder)) as client:
        first = client.get("/browse", params={"offset": 0, "limit": 2}).json()
        second = client.get("/browse", params={"offset": 2, "limit": 2}).json()
        assert first["total"] == second["total"] == 3
        urls = [i["url"] for i in first["items"] + second["items"]]
        assert len(urls) == 3 and len(set(urls)) == 3
        assert all(u.endswith(".jpg") and "/images/" in u for u in urls)
        assert client.get(urls[0]).status_code == 200
        assert client.get("/browse", params={"limit": 0}).status_code == 422
        assert client.get("/browse", params={"limit": 61}).status_code == 422
        assert client.get("/browse", params={"offset": -1}).status_code == 422


def test_browse_is_not_available_to_signed_in_services(search):
    assert search.get("/browse").status_code == 404


def test_demo_mode_ignores_tokens(tmp_path, demo_dir, encoder):
    s = Settings(data_dir=tmp_path, demo_mode=True, demo_dir=demo_dir)
    with TestClient(create_search(s, encoder=encoder)) as client:
        r = client.post("/search", json={"text": "red"}, headers={"Authorization": "Bearer junk"})
        assert r.status_code == 200 and r.json()["results"][0]["caption"] == "a red thing"


def _png(colour) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), colour).save(buf, format="PNG")
    return buf.getvalue()
