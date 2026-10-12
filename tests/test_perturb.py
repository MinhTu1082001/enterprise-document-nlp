import unittest
from contract_demo.clauses import split_clauses, annotate, render
from contract_demo.perturb import inject, KINDS

TEXT = open("data/sample_contract.txt", encoding="utf-8").read()


class TestInject(unittest.TestCase):
    def test_every_kind_once_and_ground_truth_is_in_document(self):
        clean = annotate(split_clauses(TEXT))
        for seed in range(1, 8):
            pert, ps = inject(clean, KINDS, 1, seed)
            doc = render(pert)
            self.assertEqual([p.kind for p in ps], list(KINDS), f"seed {seed}")
            cids = {c.cid for c in pert}
            for p in ps:
                self.assertIn(p.changed, doc)
                if p.original:
                    self.assertNotIn(p.original, doc)
                self.assertIn(p.cid, cids)
                self.assertTrue(p.contradicted in cids or any(c.startswith(p.contradicted + ".") for c in cids))
                self.assertNotEqual(p.cid, p.contradicted)
        self.assertEqual(render(clean), render(annotate(split_clauses(TEXT))))  # bản gốc không bị sửa

    def test_deterministic(self):
        clean = annotate(split_clauses(TEXT))
        a = [p.to_dict() for p in inject(clean, KINDS, 1, 3)[1]]
        b = [p.to_dict() for p in inject(clean, KINDS, 1, 3)[1]]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
