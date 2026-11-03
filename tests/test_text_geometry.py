import numpy as np
from conftest import rect

from anaksor.geometry import drop_contained, expand_quad, line_geometry, order_quad, quad_size, warp_crop
from anaksor.longline import clusters, line_windows, stitch
from anaksor.text import CHARSET, normalize, unsupported_chars


def test_normalize_composes_split_vowels_and_drops_invisibles():
    assert normalize("កេា") == "កោ"  # េ + ា -> ោ
    assert normalize("ខ្មែរ​") == "ខ្មែរ"  # ZWSP removed
    assert normalize("  a   b  ") == "a b"
    assert normalize("") == ""


def test_normalize_is_idempotent_and_in_charset():
    for s in ["អ្នកធ្វើការឈ្នួល", "ស្ត្រី", "ព្រះរាជាណាចក្រកម្ពុជា", "Price: 12.50$"]:
        n = normalize(s)
        assert normalize(n) == n
        assert not unsupported_chars(n), unsupported_chars(n)
    assert len(CHARSET) == len(set(CHARSET))


def test_order_quad_any_start_point():
    q = np.array(rect(10, 20, 110, 50), np.float32)
    for k in range(4):
        assert np.allclose(order_quad(np.roll(q, k, axis=0)), q)
    assert quad_size(q) == (100.0, 30.0)


def test_expand_and_warp():
    q = np.array(rect(10, 10, 110, 40), np.float32)
    e = expand_quad(q, 5, 3)
    assert np.allclose(e[0], [5, 7], atol=1e-3) and np.allclose(e[2], [115, 43], atol=1e-3)
    img = np.zeros((60, 140, 3), np.uint8)
    assert warp_crop(img, q).shape == (30, 100, 3)


def test_drop_contained_fragment_and_duplicate_but_keeps_line_in_merged_pair():
    line = rect(0, 0, 400, 40)
    fragment = rect(50, 25, 70, 38)  # detached subscript: much shorter, inside
    duplicate = rect(100, 2, 200, 39)  # word box inside the line box, same height
    assert drop_contained([line, fragment, duplicate]) == [0]
    merged = rect(0, 0, 400, 80)  # two lines glued together
    top_line = rect(0, 0, 400, 38)  # about half its height: kept
    assert drop_contained([merged, top_line]) == [0, 1]


def test_line_geometry_of_a_horizontal_line():
    origin, d, w, h = line_geometry([rect(10, 20, 110, 50)])
    assert np.allclose(origin, [10, 50]) and np.allclose(d, [1, 0]) and (w, h) == (100.0, 30.0)


def test_line_windows_cover_the_line_with_stitches_inside_overlaps():
    crop = np.full((40, 1600, 3), 255, np.uint8)
    crop[10:30, ::37] = 0  # ink every 37 px
    wins, stitches = line_windows(crop, max_ratio=8)
    assert len(wins) >= 5 and wins[0][1] == 0 and wins[-1][2] == 1600
    assert all(w.shape[1] <= 8 * 40 + 1 for w, _, _ in wins)
    for (_, _, x1), (_, x0n, _), s in zip(wins, wins[1:], stitches):
        assert x0n <= s <= x1  # each stitch lies where both windows see the text
    short = crop[:, :200]
    assert line_windows(short, 8) == ([(short, 0, 200)], [])


def test_clusters_keep_marks_and_coengs_with_their_base():
    chars = [("ក", 0.1, 0.9), ("្", 0.15, 0.9), ("រ", 0.2, 0.9), ("ុ", 0.22, 0.9), ("ង", 0.4, 0.9)]
    cs = clusters(chars)
    assert [("".join(c for c, _ in x["chars"])) for x in cs] == ["ក្រុ", "ង"]


def test_stitch_takes_each_cluster_from_one_window():
    # two windows over x in [0, 100) and [60, 160), stitch at 80; both see "ខ" at x=70
    wins = [(None, 0, 100), (None, 60, 160)]
    r1 = {"chars": [("ក", 0.3, 0.9), ("ខ", 0.7, 0.8)]}  # x = 30, 70
    r2 = {"chars": [("ខ", 0.1, 0.7), ("គ", 0.5, 0.9)]}  # x = 70, 110
    text, score = stitch(wins, [80], [r1, r2])
    assert text == "កខគ"
    assert abs(score - (0.9 + 0.8 + 0.9) / 3) < 1e-6
