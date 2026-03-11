from talker.services.ingest import RawDocument, prepare_chunks, scan_knowledge_dir


def test_scan_knowledge_dir(tmp_path):
    clinical = tmp_path / "clinical"
    clinical.mkdir()
    (clinical / "depression.md").write_text("# Depression\nContent about depression.")
    (clinical / "anxiety.md").write_text("# Anxiety\nContent about anxiety.")

    docs = scan_knowledge_dir(str(tmp_path))
    assert len(docs) == 2
    types = {d.source_type for d in docs}
    assert "clinical" in types


def test_scan_knowledge_dir_ignores_files_at_root(tmp_path):
    (tmp_path / "readme.md").write_text("# Readme")
    clinical = tmp_path / "clinical"
    clinical.mkdir()
    (clinical / "test.md").write_text("# Test")

    docs = scan_knowledge_dir(str(tmp_path))
    assert len(docs) == 1


def test_prepare_chunks():
    doc = RawDocument(
        source_file="clinical/depression.md",
        source_type="clinical",
        title="Depression",
        content="# Depression\nPHQ-9 is used for screening.\n\n## Treatment\nCBT is effective.",
    )
    chunks = prepare_chunks(doc, max_size=500)
    assert len(chunks) >= 1
    assert any("PHQ-9" in c.text for c in chunks)


def test_prepare_chunks_sets_metadata():
    doc = RawDocument(
        source_file="clinical/test.md",
        source_type="clinical",
        title="Test",
        content="# Test\nSome content.",
    )
    chunks = prepare_chunks(doc, max_size=500)
    assert chunks[0].source_file == "clinical/test.md"
    assert chunks[0].metadata["source_type"] == "clinical"
