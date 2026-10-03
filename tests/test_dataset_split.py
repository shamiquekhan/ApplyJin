from evaluation.datasets.split import split_jsonl


def test_dataset_split_is_deterministic(tmp_path):
    source = tmp_path / "cases.jsonl"
    source.write_text("\n".join('{"id":"case-%d"}' % i for i in range(20)) + "\n")
    train_a, heldout_a = tmp_path / "train-a.jsonl", tmp_path / "heldout-a.jsonl"
    train_b, heldout_b = tmp_path / "train-b.jsonl", tmp_path / "heldout-b.jsonl"
    assert split_jsonl(source, train_a, heldout_a) == split_jsonl(source, train_b, heldout_b)
    assert train_a.read_text() == train_b.read_text()
    assert heldout_a.read_text() == heldout_b.read_text()