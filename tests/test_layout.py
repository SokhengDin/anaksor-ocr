import numpy as np
from conftest import rect

from anaksor.layout import layout


def items(boxes_texts):
    return [{"quad": np.array(rect(*b), np.float32), "text": t, "rec_score": 0.9, "det_score": 0.9} for b, t in boxes_texts]


def texts(paragraphs):
    return [[ln["text"] for ln in p] for p in paragraphs]


def test_two_columns_read_left_column_first():
    left = [((20, 30 + 40 * i, 360, 60 + 40 * i), f"L{i}") for i in range(5)]
    right = [((420, 30 + 40 * i, 760, 60 + 40 * i), f"R{i}") for i in range(5)]
    paras = layout(items(right + left))  # input order must not matter
    order = [ln["text"] for p in paras for ln in p]
    assert order == [f"L{i}" for i in range(5)] + [f"R{i}" for i in range(5)]


def test_receipt_price_stays_on_its_label_line():
    rows = []
    for i in range(5):
        y = 30 + 40 * i
        rows += [((20, y, 220, y + 28), f"item{i}"), ((620, y, 700, y + 28), f"{i}.50")]
    paras = layout(items(rows))
    lines = [ln["text"] for p in paras for ln in p]
    assert lines == [f"item{i} {i}.50" for i in range(5)]
    assert all(ln["parts"] == [f"item{i}", f"{i}.50"] for i, ln in enumerate(p for q in paras for p in q))


def test_paragraphs_split_on_big_gaps_and_size_changes():
    title = [((100, 20, 600, 80), "Title")]
    body = [((40, 120 + 34 * i, 700, 148 + 34 * i), f"b{i}") for i in range(3)]
    far = [((40, 400, 700, 428), "far")]
    assert texts(layout(items(title + body + far))) == [["Title"], ["b0", "b1", "b2"], ["far"]]


def test_tight_leading_does_not_chain_lines_together():
    # boxes of adjacent lines overlap vertically by a few pixels (tall Khmer stacks)
    boxes = []
    for i in range(4):
        y = 30 + 26 * i
        boxes += [((20, y, 200, y + 30), f"a{i}"), ((210, y + 1, 400, y + 31), f"b{i}")]
    lines = [ln["text"] for p in layout(items(boxes)) for ln in p]
    assert lines == [f"a{i} b{i}" for i in range(4)]


def test_skewed_page_is_read_by_rows():
    ang = np.radians(3)
    rot = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    its = []
    for i in range(4):
        for j, x in enumerate((20, 260)):
            q = np.array(rect(x, 40 + 40 * i, x + 220, 68 + 40 * i), np.float64) @ rot.T
            its.append({"quad": q.astype(np.float32), "text": f"{i}{j}", "rec_score": 0.9, "det_score": 0.9})
    lines = [ln["text"] for p in layout(its) for ln in p]
    assert lines == [f"{i}0 {i}1" for i in range(4)]


def test_empty():
    assert layout([]) == []
