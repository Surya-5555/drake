

def test_odata_removed(compression_engine, large_redfish_json):
    """1. @odata removed"""
    compressed = compression_engine.compress(large_redfish_json)
    assert "@odata.id" not in compressed
    assert "@odata.context" not in compressed


def test_nulls_removed(compression_engine, large_redfish_json):
    """2. Nulls removed"""
    compressed = compression_engine.compress(large_redfish_json)
    # Check that keys with None values are pruned
    for key, value in compressed.items():
        assert value is not None


def test_internal_metadata_removed(compression_engine, large_redfish_json):
    """3. Internal metadata removed"""
    compressed = compression_engine.compress(large_redfish_json)
    # E.g., ETag or internal redfish links
    assert "Links" not in compressed or len(compressed["Links"]) == 0


def test_health_summary_generated(compression_engine, large_redfish_json):
    """4. Health summary generated"""
    compressed = compression_engine.compress(large_redfish_json)
    assert "Health" in compressed or "Status" in compressed
