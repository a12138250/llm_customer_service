from ec_as_ai.shared.timing import add_module_timing, attach_timing_to_messages


def test_add_module_timing_accumulates_repeated_module_duration():
    timing = {}

    add_module_timing(timing, "policy", 10.123)
    add_module_timing(timing, "policy", 4.456)

    assert timing["modules"]["policy"] == {
        "count": 2,
        "total_ms": 14.58,
        "last_ms": 4.46,
    }


def test_attach_timing_to_messages_preserves_existing_custom_payload():
    messages = [{"text": "好的", "custom": {"source": "rag"}}]
    timing = {"total_ms": 12.34}

    attach_timing_to_messages(messages, timing)

    assert messages[0]["custom"] == {
        "source": "rag",
        "timing": timing,
    }
