"""
Dell MCP — Embedding Service
=============================

Provides semantic embeddings and similarity matrix computation for OpenAPI endpoints
using sentence-transformers.
"""

from typing import Any, Dict, List
import logging
import threading
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    pass  # Allow import to succeed if dependencies are missing during early load

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Singleton service for loading the semantic embedding model and computing similarities.
    Thread-safe implementation ensures the heavy ML model is only loaded once.
    """

    _instance = None
    _model = None
    _lock = threading.Lock()

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance

    def _get_model(self) -> "SentenceTransformer":
        """Lazy load the sentence-transformers model to save memory until needed."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
                        self._model = SentenceTransformer("all-MiniLM-L6-v2")
                        logger.info("Model loaded successfully.")
                    except Exception as err:
                        logger.error(f"Failed to load sentence-transformers model: {err}")
                        raise RuntimeError(f"Semantic embedding model failed to load: {err}") from err
        return self._model

    def format_endpoint_text(self, endpoint: Dict[str, Any]) -> str:
        """
        Combines semantic attributes of an endpoint into a single coherent text block
        for embedding generation. Extends to schemas if references are found.
        """
        method = endpoint.get("method", "")
        url = endpoint.get("url", "")
        summary = endpoint.get("summary", "")
        description = endpoint.get("description", "")
        tags = endpoint.get("tags", [])
        request_schema = endpoint.get("request_schema")
        response_schema = endpoint.get("response_schema")

        # Ensure tags is a list
        if isinstance(tags, str):
            tags = [tags]

        tag_str = ", ".join(tags)
        
        # Combine the fields prioritizing summary and description
        components = []
        if method and url:
            components.append(f"Endpoint: {method} {url}")
        if tags:
            components.append(f"Tags: {tag_str}")
        if summary:
            components.append(f"Summary: {summary}")
        if description:
            components.append(f"Description: {description}")
            
        # Parse $ref for request schema
        if request_schema and isinstance(request_schema, dict):
            ref = request_schema.get("$ref")
            if ref:
                schema_name = ref.split("/")[-1]
                components.append(f"Schema: {schema_name}")

        # Parse $ref for response schema
        if response_schema and isinstance(response_schema, dict):
            ref = response_schema.get("$ref")
            if ref:
                schema_name = ref.split("/")[-1]
                components.append(f"Schema: {schema_name}")
                
        return "\n".join(components)

    def generate_embeddings(self, endpoints: List[Dict[str, Any]]) -> np.ndarray:
        """
        Generates dense vector embeddings for a list of endpoints.
        """
        if not endpoints:
            return np.array([])
            
        texts = [self.format_endpoint_text(ep) for ep in endpoints]
        model = self._get_model()
        
        # Generate embeddings (returns a numpy array or torch tensor)
        embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings

    def compute_similarity_matrix(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Computes the cosine similarity matrix between all pairs of embeddings.
        Returns an NxN numpy array where N is the number of embeddings.
        """
        if embeddings.size == 0:
            return np.array([])
        return cosine_similarity(embeddings)
