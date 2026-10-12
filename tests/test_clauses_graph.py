import unittest
from contract_demo.clauses import split_clauses, annotate, defined_terms
from contract_demo.graph import build_graph

TEXT = open("data/sample_contract.txt", encoding="utf-8").read()


class TestClauses(unittest.TestCase):
    def setUp(self):
        self.cl = annotate(split_clauses(TEXT))
        self.by = {c.cid: c for c in self.cl}

    def test_split_and_kinds(self):
        self.assertEqual(len(self.cl), 49)
        self.assertEqual(self.by["1.1"].kind, "definitional")
        self.assertEqual(self.by["4.2"].kind, "exception")
        self.assertEqual(self.by["4.3"].kind, "conditional")
        self.assertEqual(self.by["2.1"].kind, "operative")
        self.assertEqual(self.by["4"].kind, "heading")

    def test_defined_terms(self):
        terms = defined_terms(self.cl)
        self.assertEqual(terms["Confidential Information"], "1.2")
        self.assertEqual(terms["Receiving Party"], "1.2")
        self.assertEqual(terms["Provider Materials"], "5.2")

    def test_fields(self):
        f = self.by["4.4"].fields
        self.assertEqual(f["Subject"], "Receiving Party")
        self.assertEqual(f["Deontic"], "shall (obligation)")
        self.assertEqual(f["Action"], "return")
        self.assertIn("Confidential Information", f["contains_defined_terms"])
        self.assertEqual(self.by["2.3"].fields["Deontic"], "shall not (prohibition)")
        self.assertEqual(self.by["2.2"].fields["Deontic"], "may (permission)")


class TestGraph(unittest.TestCase):
    def setUp(self):
        self.g = build_graph(annotate(split_clauses(TEXT)))

    def has(self, src, kind, dst):
        return any(e.src == src and e.kind == kind and e.dst == dst for e in self.g.edges)

    def test_edges(self):
        self.assertTrue(self.has("1.2", "DEFINES", "4.1"))
        self.assertTrue(self.has("4.2", "EXCEPTIONS", "4.1"))
        self.assertTrue(self.has("7.2", "EXCEPTIONS", "7.1"))
        self.assertTrue(self.has("8.3", "EXCEPTIONS", "8.1"))
        self.assertTrue(self.has("3.3", "DEPENDS_ON", "3.1"))
        self.assertTrue(self.has("7.2", "DEPENDS_ON", "8.1"))
        self.assertFalse(self.has("7.2", "EXCEPTIONS", "4.1"))     # "breach of Section 4" không phải ngoại lệ của 4
        self.assertFalse(self.has("4.1", "DEPENDS_ON", "4.2"))     # "this Section 4" là tự dẫn chiếu

    def test_neighbors_bfs(self):
        one = self.g.neighbors("3.3", hops=1)
        self.assertEqual(set(one), {"3.1"})            # 3.3 chỉ dẫn chiếu 3.1 và không dùng thuật ngữ định nghĩa nào
        two = self.g.neighbors("3.3", hops=2)
        self.assertTrue(set(one) <= set(two))
        self.assertIn("1.4", two)                      # 3.3 -> 3.1 <- 1.4 ("Fees" định nghĩa ở 1.4)
        self.assertEqual([e.kind for e in two["1.4"]], ["DEPENDS_ON", "DEFINES"])
        self.assertNotIn("3.3", two)


if __name__ == "__main__":
    unittest.main()
