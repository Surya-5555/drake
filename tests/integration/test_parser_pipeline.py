import pytest


def test_openapi_loads_successfully(mock_openapi_spec):
    """1. OpenAPI file loads successfully"""
    assert mock_openapi_spec.exists()
    assert mock_openapi_spec.stat().st_size > 0


def test_every_endpoint_becomes_endpoint_object(parser_pipeline):
    """2. Every endpoint becomes an Endpoint object"""
    endpoints = parser_pipeline.get_endpoints()
    assert len(endpoints) > 0
    assert all(hasattr(ep, "path") and hasattr(ep, "method") for ep in endpoints)


def test_endpoint_properties_extracted_correctly(parser_pipeline):
    """3. Path, Method, Summary, Description are extracted correctly"""
    endpoints = parser_pipeline.get_endpoints()
    for ep in endpoints:
        assert ep.path.startswith("/")
        assert ep.method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]
        assert getattr(ep, "summary", None) is not None
        assert getattr(ep, "description", None) is not None


def test_invalid_openapi_rejected(parser_pipeline):
    """4. Invalid OpenAPI specs are rejected"""
    with pytest.raises(Exception):
        parser_pipeline.load_spec("invalid_spec.json")


def test_empty_openapi_rejected(parser_pipeline):
    """5. Empty OpenAPI specs are rejected"""
    with pytest.raises(Exception):
        parser_pipeline.load_spec("empty_spec.json")


def test_endpoint_count_matches_spec(parser_pipeline, mock_openapi_spec_count):
    """6. Endpoint count matches spec"""
    endpoints = parser_pipeline.get_endpoints()
    assert len(endpoints) == mock_openapi_spec_count
