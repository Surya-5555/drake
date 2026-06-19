import pytest
from pathlib import Path

def test_metrics_calculates_endpoint_count(metrics_engine, mock_openapi_path):
    """Metrics engine correctly calculates: Endpoint Count"""
    metrics = metrics_engine.generate(mock_openapi_path)
    assert metrics.endpoint_count > 0

def test_metrics_calculates_workflow_count(metrics_engine, mock_openapi_path):
    """Metrics engine correctly calculates: Workflow Count"""
    metrics = metrics_engine.generate(mock_openapi_path)
    assert metrics.workflow_count > 0

def test_metrics_calculates_coverage(metrics_engine, mock_openapi_path):
    """Metrics engine correctly calculates: Coverage"""
    metrics = metrics_engine.generate(mock_openapi_path)
    assert 0.0 <= metrics.coverage_percent <= 100.0

def test_metrics_calculates_reduction_percentage(metrics_engine, mock_openapi_path):
    """Metrics engine correctly calculates: Reduction Percentage"""
    metrics = metrics_engine.generate(mock_openapi_path)
    assert 0.0 <= metrics.reduction_percent <= 100.0

def test_metrics_calculates_token_savings(metrics_engine, mock_openapi_path):
    """Metrics engine correctly calculates: Token Savings"""
    metrics = metrics_engine.generate(mock_openapi_path)
    assert 0.0 <= metrics.token_savings_percent <= 100.0
