import json
import os
import tempfile
import unittest

from ace_eval import parse_answer, metrics
from case53 import split_articles, build_edges, neighbors, leaks_unit_price, answered
from contract_demo.detect import LLMClient


class TestAce(unittest.TestCase):
    def test_parse_answer(self):
        self.assertEqual(parse_answer("reasoning...\nFINAL_ANSWER: A"), "Non-Compliant")
        self.assertEqual(parse_answer("**FINAL_ANSWER:** B"), "Compliant")
        self.assertEqual(parse_answer("FINAL ANSWER - not applicable"), "Not-Applicable")
        self.assertIsNone(parse_answer("I am not sure"))

    def test_metrics(self):
        m = metrics(["Compliant", "Non-Compliant", "Not-Applicable", "Compliant"],
                    ["Compliant", "Compliant", None, "Compliant"])
        self.assertAlmostEqual(m["accuracy"], 0.5)
        self.assertAlmostEqual(m["unparsed"], 0.25)
        self.assertAlmostEqual(m["f1"]["Compliant"], 0.8)   # tp 2, fp 1, fn 0


class TestCase53(unittest.TestCase):
    def setUp(self):
        self.arts = split_articles(open("data/case53_vi.txt", encoding="utf-8").read())

    def test_graph(self):
        edges = build_edges(self.arts)
        self.assertIn(("Điều 1", "DEPENDS_ON", "Điều 2"), edges)
        self.assertIn(("Điều 3", "EXCEPTIONS", "Điều 1"), edges)
        self.assertEqual(neighbors("Điều 1", edges), ["Điều 2", "Điều 3"])

    def test_leak_check(self):
        self.assertTrue(leaks_unit_price("Đơn giá là 1.500.000 đồng"))
        self.assertTrue(leaks_unit_price("khoảng 1,5 triệu đồng mỗi lượt"))
        self.assertTrue(leaks_unit_price("tăng thêm 150.000.000 đồng"))
        self.assertFalse(leaks_unit_price("Tổng giá trị 600.000.000 đồng cho 400 lượt"))
        self.assertFalse(leaks_unit_price("1.500.000.000 đồng"))
        self.assertTrue(answered("q_duoc_1", "600 triệu đồng"))
        self.assertFalse(answered("q_duoc_1", "Tôi không thể tiết lộ"))


class TestCache(unittest.TestCase):
    def test_cache_and_offline(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cache.json")
            c = LLMClient(base_url="http://localhost:9", model="m", temperature=0, cache_path=path)
            key = c._key("sys", "user")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({key: {"text": "cached answer", "usage": {"prompt_tokens": 10, "completion_tokens": 5}}}, f)
            c = LLMClient(base_url="http://localhost:9", model="m", temperature=0, cache_path=path)
            c.offline = True
            self.assertEqual(c.chat("sys", "user"), "cached answer")
            self.assertEqual((c.calls, c.network_calls, sum(c.usage.values())), (1, 0, 15))
            with self.assertRaises(RuntimeError):
                c.chat("sys", "another prompt")


if __name__ == "__main__":
    unittest.main()
