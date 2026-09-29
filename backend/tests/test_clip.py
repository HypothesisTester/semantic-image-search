"""CLIP encoder tests.

- The random-weight tests check shapes, normalisation and batching without
  downloading anything. They run whenever torch and open_clip are installed.
- The ``model`` tests need the real OpenAI weights (about 350 MB, downloaded on
  first use) and check that the model actually understands images:
      RUN_MODEL_TESTS=1 pytest -m model
"""

import os

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("torch")
pytest.importorskip("open_clip")

from common.clip import EMBED_DIM, ClipEncoder  # noqa: E402


@pytest.fixture(scope="module")
def random_encoder():
    return ClipEncoder(pretrained=None, device="cpu", batch_size=2)


def solid(colour, size=(64, 48)):
    return Image.new("RGB", size, colour)


def test_image_embeddings_have_the_right_shape_and_unit_norm(random_encoder):
    # 5 images with batch_size=2 also exercises a partial last batch.
    out = random_encoder.encode_images([solid(c) for c in ("red", "green", "blue", "white", "black")])
    assert out.shape == (5, EMBED_DIM) and out.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)


def test_text_embeddings_have_the_right_shape_and_unit_norm(random_encoder):
    out = random_encoder.encode_texts(["a dog", "a cat", "a very long caption " * 30])
    assert out.shape == (3, EMBED_DIM)
    np.testing.assert_allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-5)


def test_empty_input_gives_an_empty_matrix(random_encoder):
    assert random_encoder.encode_images([]).shape == (0, EMBED_DIM)
    assert random_encoder.encode_texts([]).shape == (0, EMBED_DIM)


def test_batching_does_not_change_the_result(random_encoder):
    imgs = [solid(c) for c in ("red", "green", "blue")]
    batched = random_encoder.encode_images(imgs)
    one_by_one = np.concatenate([random_encoder.encode_images([im]) for im in imgs])
    np.testing.assert_allclose(batched, one_by_one, atol=1e-4)


def test_text_only_encoder_refuses_images():
    encoder = ClipEncoder(pretrained=None, device="cpu", towers="text")
    assert encoder.encode_texts(["hello"]).shape == (1, EMBED_DIM)
    with pytest.raises(RuntimeError, match="text"):
        encoder.encode_images([solid("red")])


# ---- real weights ------------------------------------------------------------

requires_weights = pytest.mark.skipif(
    os.environ.get("RUN_MODEL_TESTS") != "1", reason="set RUN_MODEL_TESTS=1 to run"
)


@pytest.fixture(scope="module")
def real_encoder():
    return ClipEncoder()


@pytest.mark.model
@requires_weights
def test_real_model_matches_colours_to_captions(real_encoder):
    colours = ["red", "green", "blue", "yellow"]
    image_vecs = real_encoder.encode_images([solid(c, (224, 224)) for c in colours])
    text_vecs = real_encoder.encode_texts([f"a plain {c} square" for c in colours])
    similarity = image_vecs @ text_vecs.T
    # Each colour's image should match its own caption best.
    assert list(similarity.argmax(axis=1)) == [0, 1, 2, 3]


@pytest.mark.model
@requires_weights
def test_text_only_encoder_matches_the_full_encoder(real_encoder):
    text_only = ClipEncoder(towers="text")
    captions = ["a dog on a beach", "a birthday cake"]
    np.testing.assert_allclose(
        text_only.encode_texts(captions), real_encoder.encode_texts(captions), atol=1e-5
    )
