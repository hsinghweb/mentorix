from app.rag.grounding_ingest import _infer_chunk_doc_type


def test_example_chunks_are_tagged():
    tagged = _infer_chunk_doc_type("chapter", "1.2 Theorem", "Solved Example 1: Let us solve...")
    assert tagged == "example"


def test_non_example_chunks_keep_base_doc_type():
    tagged = _infer_chunk_doc_type("chapter", "1.3 Concepts", "Definitions and properties.")
    assert tagged == "chapter"

