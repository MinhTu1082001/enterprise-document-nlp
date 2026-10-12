"""Xuất kết quả: results.json và report.html (một file, không thư viện, không mạng).

Trang HTML gồm: bảng điểm theo cấu hình, hợp đồng đã cài lỗi với tô màu
(xanh = bắt đúng, đỏ = bỏ sót, vàng = báo thừa), và đồ thị điều khoản vẽ bằng SVG.
"""
from __future__ import annotations

import html
import json
import math

from .graph import ClauseGraph
from .score import Alignment

_COLORS = {"DEFINES": "#2a7fd4", "EXCEPTIONS": "#d4592a", "DEPENDS_ON": "#6b6b6b"}


def _svg_graph(g: ClauseGraph, size: int = 640) -> str:
    nodes = [cid for cid in g.order if g.clauses[cid].kind != "heading"]
    n = len(nodes)
    r = size / 2 - 50
    pos = {}
    for i, cid in enumerate(nodes):
        a = 2 * math.pi * i / n
        pos[cid] = (size / 2 + r * math.cos(a), size / 2 + r * math.sin(a))
    parts = [f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" font-family="sans-serif" font-size="11">']
    for e in g.edges:
        if e.src in pos and e.dst in pos:
            (x1, y1), (x2, y2) = pos[e.src], pos[e.dst]
            parts.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
                         f'stroke="{_COLORS.get(e.kind, "#999")}" stroke-width="1.2" opacity="0.7">'
                         f'<title>{e.src} {e.kind} {e.dst}: {html.escape(e.evidence)}</title></line>')
    for cid, (x, y) in pos.items():
        k = g.clauses[cid].kind
        fill = {"definitional": "#dbe9ff", "exception": "#ffe0d1", "conditional": "#fff4c2"}.get(k, "#eee")
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="16" fill="{fill}" stroke="#444"/>'
                     f'<text x="{x:.0f}" y="{y + 4:.0f}" text-anchor="middle">{cid}</text>')
    y0 = 14
    for kind, col in _COLORS.items():
        parts.append(f'<line x1="10" y1="{y0}" x2="40" y2="{y0}" stroke="{col}" stroke-width="2"/>'
                     f'<text x="46" y="{y0 + 4}">{kind}</text>')
        y0 += 16
    parts.append("</svg>")
    return "".join(parts)


def _highlight(document: str, gold: list[dict], preds: list[str], al: Alignment) -> str:
    """Tô màu theo kết quả ghép: bọc span bằng <mark>. Làm đơn giản: thay thế chuỗi."""
    marks = []
    matched_g = {i for gs, _ in al.matched for i in gs}
    matched_p = {j for _, ps in al.matched for j in ps}
    for i, g in enumerate(gold):
        marks.append((g["span"], "ok" if i in matched_g else "miss", f'{g["kind"]} (chuẩn, {g["cid"]})'))
    for j, p in enumerate(preds):
        if j not in matched_p:
            marks.append((p, "extra", "báo thừa"))
    text = html.escape(document)
    for span, cls, title in sorted(marks, key=lambda m: -len(m[0])):
        esc = html.escape(span)
        if esc in text:
            text = text.replace(esc, f'<mark class="{cls}" title="{html.escape(title)}">{esc}</mark>', 1)
    return text.replace("\n\n", "<br><br>")


def write_report(path: str, document: str, gold: list[dict], results: dict, g: ClauseGraph, perts: list[dict]) -> None:
    rows = []
    for name, res in results.items():
        al: Alignment = res["alignment"]
        rows.append(f"<tr><td>{name}</td><td>{al.tp}</td><td>{al.fn}</td><td>{al.fp}</td>"
                    f"<td>{al.precision:.2f}</td><td>{al.recall:.2f}</td><td>{al.f1:.2f}</td>"
                    f"<td>{al.miss_rate:.2f}</td><td>{al.extra_rate:.2f}</td><td>{res['calls']}</td></tr>")
    names = list(results)
    kinds = sorted({k for res in results.values() for k in res["per_kind"]})
    kind_rows = ["<tr><th>Loại lỗi</th>" + "".join(f"<th>{n}</th>" for n in names) + "</tr>"]
    for kind in kinds:
        cells = "".join(f"<td>{results[n]['per_kind'][kind].tp}/{results[n]['per_kind'][kind].tp + results[n]['per_kind'][kind].fn}</td>"
                        if kind in results[n]["per_kind"] else "<td>-</td>" for n in names)
        kind_rows.append(f"<tr><td>{kind}</td>{cells}</tr>")
    sections = []
    for name, res in results.items():
        sections.append(f"<h3>{name}</h3><div class=doc>{_highlight(document, gold, res['pred_spans'], res['alignment'])}</div>")
    pert_rows = "".join(
        f"<tr><td>{p['kind']}</td><td>{p['cid']}</td><td>{p['contradicted']}</td><td>{html.escape(p['explanation'])}</td></tr>"
        for p in perts)
    page = f"""<!doctype html><html lang="vi"><meta charset="utf-8"><title>Demo rà soát hợp đồng</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;line-height:1.45}}
table{{border-collapse:collapse;margin:12px 0}}td,th{{border:1px solid #ccc;padding:4px 8px;text-align:left}}
.doc{{white-space:pre-wrap;font-size:14px;border:1px solid #ddd;padding:12px;max-height:480px;overflow:auto}}
mark.ok{{background:#c8f5c8}}mark.miss{{background:#ffc9c9}}mark.extra{{background:#fff0a8}}</style>
<h1>Demo rà soát hợp đồng: phát hiện lỗi xuyên điều khoản</h1>
<p>Lỗi cài theo CLAUSE [1]; đồ thị điều khoản theo COMPACT [6]; chấm bằng location_alignment của [1].</p>
<h2>Kết quả theo cấu hình</h2>
<table><tr><th>Cấu hình</th><th>TP</th><th>FN (miss)</th><th>FP (extra)</th><th>P</th><th>R</th><th>F1</th>
<th>Miss rate</th><th>Extra rate</th><th>Lần gọi LLM</th></tr>{''.join(rows)}</table>
<p>Bắt được / tổng theo loại lỗi:</p><table>{''.join(kind_rows)}</table>
<h2>Lỗi đã cài ({len(perts)})</h2>
<table><tr><th>Loại</th><th>Ở điều khoản</th><th>Mâu thuẫn với</th><th>Giải thích</th></tr>{pert_rows}</table>
<h2>Hợp đồng đã cài lỗi, tô theo kết quả</h2>
<p><mark class=ok>bắt đúng</mark> <mark class=miss>bỏ sót</mark> <mark class=extra>báo thừa</mark></p>
{''.join(sections)}
<h2>Đồ thị điều khoản ({len(g.edges)} cạnh)</h2>{_svg_graph(g)}
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def write_json(path: str, gold: list[dict], results: dict, g: ClauseGraph) -> None:
    out = {"gold": gold, "graph": g.to_json(), "results": {}}
    for name, res in results.items():
        al: Alignment = res["alignment"]
        out["results"][name] = {
            "tp": al.tp, "fn": al.fn, "fp": al.fp, "precision": al.precision, "recall": al.recall, "f1": al.f1,
            "miss_rate": al.miss_rate, "extra_rate": al.extra_rate, "llm_calls": res["calls"],
            "tokens": res.get("tokens"), "seconds": res.get("seconds"),
            "per_kind": {k: {"found": a.tp, "total": a.tp + a.fn} for k, a in res["per_kind"].items()},
            "predictions": res["predictions"],
        }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
