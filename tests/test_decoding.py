import numpy as np

from anaksor.decoding import Charset, cppd_greedy, ctc_greedy, smtr_greedy
from anaksor.longline import merge_overlapping, stitch

CS = Charset(["ក", "ខ", "ា"])


def onehot(ids, n, p=0.9):
    out = np.full((1, len(ids), n), (1 - p) / (n - 1), np.float32)
    out[0, np.arange(len(ids)), ids] = p
    return out


def test_ctc_merges_repeats_and_drops_blanks():
    ((text, score),) = ctc_greedy(onehot([0, 1, 1, 0, 1, 3, 0], 4), CS.ctc)
    assert text == "កកា" and abs(score - 0.9) < 1e-6
    assert ctc_greedy(onehot([0, 0], 4), CS.ctc) == [("", 0.0)]


def test_smtr_stops_at_end_and_skips_start_and_pad():
    v = len(CS.smtr)  # </s> ក ខ ា <s> <INF> <INB> <pad>
    text, score = smtr_greedy(onehot([1, 4, 2, 7, 3, 0, 1], v), CS.smtr)[0]
    assert text == "កខា" and abs(score - 0.9) < 1e-6
    assert smtr_greedy(onehot([1, 2], v), CS.smtr, reverse=True)[0][0] == "ខក"


def test_cppd_reads_up_to_the_end_symbol():
    assert cppd_greedy(onehot([2, 3, 0, 1], 4), CS.cppd)[0][0] == "ខា"
    assert cppd_greedy(onehot([0, 1], 4), CS.cppd) == [("", 0.0)]


def test_windows_without_positions_merge_on_their_overlap():
    assert merge_overlapping(["ការងារ សាលា", "សាលា រៀន"]) == "ការងារ សាលា រៀន"
    wins = [(None, 0, 100), (None, 70, 170)]
    text, score = stitch(
        wins, [85], [{"text": "ab cd", "score": 0.8, "chars": None}, {"text": "cd ef", "score": 0.6, "chars": None}]
    )
    assert text == "ab cd ef" and abs(score - 0.7) < 1e-9
