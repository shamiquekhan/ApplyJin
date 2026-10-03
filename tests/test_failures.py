from hermes.inference.failures import FailureCode, classify_failure


def test_failure_taxonomy_classifies_provider_errors():
    assert classify_failure(TimeoutError("provider timeout")) == FailureCode.MODEL_TIMEOUT
    assert classify_failure(RuntimeError("CUDA out of memory")) == FailureCode.MODEL_OOM
    assert classify_failure(ValueError("invalid JSON")) == FailureCode.MODEL_INVALID_OUTPUT