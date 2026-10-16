"""Graph wiring: compiles and honors the parse gate (catches wiring regressions)."""
import graph as G


def test_graph_compiles():
    assert G.build() is not None


def test_parse_limit_halts_before_extract():
    g = G.build()
    out = g.invoke({"submission_reference": "S",
                    "documents": [{"doc_id": f"d{i}"} for i in range(11)]})
    assert out["parse"]["halted"] is True
    assert "extracted" not in out


def test_text_docs_flow_to_completeness_halt():
    g = G.build()
    out = g.invoke({"submission_reference": "S", "documents": [{"doc_id": "d"}]})
    assert out["parse"]["halted"] is False
    assert out["completeness"]["can_evaluate"] is False
