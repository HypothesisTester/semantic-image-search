import faiss
import numpy as np
import pytest

from common.vectors import check_normalized, l2_normalize
from tests.helpers import unit_vectors


def test_l2_normalize_gives_unit_rows():
    x = np.array([[3.0, 4.0], [0.0, 2.0]], dtype=np.float32)
    out = l2_normalize(x)
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, [[0.6, 0.8], [0.0, 1.0]], rtol=1e-6)
    np.testing.assert_allclose(np.linalg.norm(out, axis=1), 1.0, rtol=1e-6)


def test_l2_normalize_accepts_a_single_vector():
    assert l2_normalize(np.array([1.0, 1.0])).shape == (1, 2)


def test_l2_normalize_rejects_zero_and_non_finite_vectors():
    with pytest.raises(ValueError, match="zero"):
        l2_normalize(np.array([[1.0, 0.0], [0.0, 0.0]]))
    with pytest.raises(ValueError, match="NaN"):
        l2_normalize(np.array([[np.nan, 1.0]]))


def test_check_normalized_rejects_bad_input():
    with pytest.raises(ValueError, match="not L2-normalised"):
        check_normalized(np.full((2, 4), 2.0, dtype=np.float32), 4)
    with pytest.raises(ValueError, match="float32"):
        check_normalized(unit_vectors(2, seed=0, dim=4).astype(np.float64), 4)
    with pytest.raises(ValueError, match="shape"):
        check_normalized(unit_vectors(2, seed=0, dim=4), 8)


def test_inner_product_index_equals_cosine_similarity():
    # The reason for normalising: on unit vectors, FAISS inner product = cosine.
    rng = np.random.default_rng(0)
    raw = rng.standard_normal((200, 512)).astype(np.float32) * 7  # deliberately not unit length
    query_raw = rng.standard_normal((1, 512)).astype(np.float32) * 3

    cosine = (raw @ query_raw.T).ravel() / (
        np.linalg.norm(raw, axis=1) * np.linalg.norm(query_raw)
    )

    index = faiss.IndexFlatIP(512)
    index.add(l2_normalize(raw))
    scores, ids = index.search(l2_normalize(query_raw), 200)

    np.testing.assert_allclose(scores[0], cosine[ids[0]], atol=1e-5)
    assert list(ids[0]) == list(np.argsort(-cosine))
