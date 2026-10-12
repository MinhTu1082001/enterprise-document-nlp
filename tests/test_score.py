"""Kiểm tra location_alignment đúng với định nghĩa trong CLAUSE [1], mục 5."""
import unittest
from contract_demo.score import align, norm_sentences

c = {i: f"Sentence number {i} of the contract." for i in range(1, 20)}


def span(*ids):
    return " ".join(c[i] for i in ids)


class TestAlign(unittest.TestCase):
    def test_example_from_study_guide(self):
        # G1={3,4}, G2={9}; P1={4,5}, P2={5,6}, P3={12}  ->  TP=1, FN=1, FP=2
        al = align([span(3, 4), span(9)], [span(4, 5), span(5, 6), span(12)])
        self.assertEqual((al.tp, al.fn, al.fp), (1, 1, 2))
        self.assertAlmostEqual(al.precision, 1 / 3)
        self.assertAlmostEqual(al.recall, 1 / 2)

    def test_two_predictions_on_one_gold_is_one_match(self):
        al = align([span(3, 4)], [span(3), span(4)])
        self.assertEqual((al.tp, al.fn, al.fp), (1, 0, 0))

    def test_one_prediction_covering_two_golds_is_one_group(self):
        # thành phần liên thông có 2 GT + 1 P = một match group, không có FN
        al = align([span(3), span(4)], [span(3, 4)])
        self.assertEqual((al.tp, al.fn, al.fp), (1, 0, 0))

    def test_no_overlap(self):
        al = align([span(1)], [span(2)])
        self.assertEqual((al.tp, al.fn, al.fp), (0, 1, 1))
        self.assertEqual(al.miss_rate, 1.0)
        self.assertEqual(al.extra_rate, 1.0)

    def test_empty(self):
        al = align([], [])
        self.assertEqual((al.tp, al.fn, al.fp), (0, 0, 0))
        self.assertEqual(al.f1, 0.0)

    def test_normalisation_ignores_case_quotes_and_spacing(self):
        a = norm_sentences('The  "Client" shall pay.')
        b = norm_sentences("the “client” shall pay")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
