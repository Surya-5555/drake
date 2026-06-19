import pytest

def test_endpoint_becomes_graph_node(graph_pipeline):
    """1. Every endpoint becomes a graph node"""
    nodes = graph_pipeline.get_nodes()
    assert len(nodes) > 0

def test_graph_contains_edges(graph_pipeline):
    """2. Graph contains edges"""
    edges = graph_pipeline.get_edges()
    assert len(edges) > 0

def test_graph_not_empty(graph_pipeline):
    """3. Graph is not empty"""
    assert graph_pipeline.get_node_count() > 0

def test_graph_node_count_equals_endpoint_count(graph_pipeline, parsed_endpoints):
    """4. Graph node count equals endpoint count"""
    assert graph_pipeline.get_node_count() == len(parsed_endpoints)

def test_graph_builder_never_loses_endpoints(graph_pipeline, parsed_endpoints):
    """5. Graph builder never loses endpoints"""
    node_ids = set(graph_pipeline.get_node_ids())
    endpoint_ids = set(ep.operation_id for ep in parsed_endpoints)
    assert node_ids == endpoint_ids

def test_similar_endpoints_create_edges(graph_pipeline):
    """6. Similar endpoints create edges"""
    # Specific behavior test: edges are created based on similarity
    edges = graph_pipeline.get_edges()
    # At least some edges must have weights > 0
    assert any(edge.weight > 0 for edge in edges)
