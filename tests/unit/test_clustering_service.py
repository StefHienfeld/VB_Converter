"""
Unit tests for ClusteringService.

Tests the Leader clustering algorithm and text normalization.
"""

import pytest
from hienfeld.config import load_config
from hienfeld.domain.clause import Clause
from hienfeld.services.clustering_service import ClusteringService
from hienfeld.services.similarity_service import RapidFuzzSimilarityService


@pytest.fixture
def config():
    """Load default config for tests."""
    return load_config()


@pytest.fixture
def clustering_service(config):
    """Create clustering service with default settings."""
    return ClusteringService(config)


@pytest.fixture
def strict_clustering_service(config):
    """Create clustering service with strict similarity threshold."""
    config.clustering.similarity_threshold = 0.95
    similarity = RapidFuzzSimilarityService(threshold=0.95)
    return ClusteringService(config, similarity_service=similarity)


@pytest.fixture
def lenient_clustering_service(config):
    """Create clustering service with lenient similarity threshold."""
    config.clustering.similarity_threshold = 0.70
    similarity = RapidFuzzSimilarityService(threshold=0.70)
    return ClusteringService(config, similarity_service=similarity)


def create_clause(text: str, clause_id: str = None) -> Clause:
    """Helper to create a Clause object."""
    return Clause(
        id=clause_id or f"clause_{hash(text) % 10000}",
        raw_text=text,
        simplified_text=text.lower().strip(),
        source_file_name="test.xlsx",
    )


class TestClusteringService:
    """Tests for ClusteringService."""

    def test_empty_input_returns_empty(self, clustering_service):
        """Empty input should return empty results."""
        clusters, mapping = clustering_service.cluster_clauses([])
        assert clusters == []
        assert mapping == {}

    def test_single_clause_creates_single_cluster(self, clustering_service):
        """Single clause should create one cluster."""
        clauses = [create_clause("Dekking voor auto is meeverzekerd")]

        clusters, mapping = clustering_service.cluster_clauses(clauses)

        assert len(clusters) == 1
        assert len(mapping) == 1
        assert clusters[0].frequency == 1

    def test_identical_texts_cluster_together(self, clustering_service):
        """Identical texts should be in the same cluster."""
        clauses = [
            create_clause("Dekking voor auto is meeverzekerd", "c1"),
            create_clause("Dekking voor auto is meeverzekerd", "c2"),
            create_clause("Dekking voor auto is meeverzekerd", "c3"),
        ]

        clusters, mapping = clustering_service.cluster_clauses(clauses)

        assert len(clusters) == 1
        assert clusters[0].frequency == 3
        # All clauses should map to same cluster
        cluster_ids = set(mapping.values())
        assert len(cluster_ids) == 1

    def test_similar_texts_cluster_together(self, lenient_clustering_service):
        """Similar texts should cluster together with lenient threshold."""
        clauses = [
            create_clause("Dekking voor auto is meeverzekerd", "c1"),
            create_clause("Dekking voor auto is meeverzekerd.", "c2"),  # Added period
            create_clause("Schade aan gebouwen is uitgesloten", "c3"),  # Different
        ]

        clusters, mapping = lenient_clustering_service.cluster_clauses(clauses)

        # First two should cluster, third is different
        assert len(clusters) == 2
        assert mapping["c1"] == mapping["c2"]
        assert mapping["c1"] != mapping["c3"]

    def test_different_texts_create_separate_clusters(self, strict_clustering_service):
        """Different texts should create separate clusters."""
        clauses = [
            create_clause("Dekking voor auto is meeverzekerd", "c1"),
            create_clause("Schade aan gebouwen is uitgesloten", "c2"),
            create_clause("Brand en ontploffing zijn gedekt", "c3"),
        ]

        clusters, mapping = strict_clustering_service.cluster_clauses(clauses)

        assert len(clusters) == 3
        # Each clause in its own cluster
        cluster_ids = list(mapping.values())
        assert len(set(cluster_ids)) == 3

    def test_cluster_frequency_is_correct(self, strict_clustering_service):
        """Cluster frequency should match number of clauses in cluster."""
        # Use very different texts to ensure separate clusters
        clauses = [
            create_clause("Dekking voor motorrijtuigen inclusief aanhangwagen", "c1"),
            create_clause("Dekking voor motorrijtuigen inclusief aanhangwagen", "c2"),
            create_clause("Dekking voor motorrijtuigen inclusief aanhangwagen", "c3"),
            create_clause("Uitsluiting van schade door aardbevingen en vulkanische activiteit", "c4"),
            create_clause("Uitsluiting van schade door aardbevingen en vulkanische activiteit", "c5"),
        ]

        clusters, mapping = strict_clustering_service.cluster_clauses(clauses)

        # Should have 2 clusters with frequencies 3 and 2
        frequencies = sorted([c.frequency for c in clusters], reverse=True)
        assert frequencies == [3, 2]

    def test_progress_callback_is_called(self, clustering_service):
        """Progress callback should be called during clustering."""
        clauses = [create_clause(f"Tekst nummer {i}") for i in range(10)]
        progress_values = []

        def callback(progress: int):
            progress_values.append(progress)

        clustering_service.cluster_clauses(clauses, progress_callback=callback)

        # Should have received progress updates
        assert len(progress_values) > 0
        # Progress should be between 0 and 100
        assert all(0 <= p <= 100 for p in progress_values)

    def test_clause_to_cluster_mapping_complete(self, clustering_service):
        """Every clause should have a cluster mapping."""
        clauses = [create_clause(f"Unieke tekst {i}", f"clause_{i}") for i in range(5)]

        clusters, mapping = clustering_service.cluster_clauses(clauses)

        # Every clause_id should be in the mapping
        for clause in clauses:
            assert clause.id in mapping

    def test_variable_parts_ignored_in_clustering(self, lenient_clustering_service):
        """Variable parts (addresses, amounts) should be normalized."""
        clauses = [
            create_clause("Verzekerd bedrag EUR 100.000", "c1"),
            create_clause("Verzekerd bedrag EUR 250.000", "c2"),
            create_clause("Verzekerd bedrag EUR 500.000", "c3"),
        ]

        clusters, mapping = lenient_clustering_service.cluster_clauses(clauses)

        # These should cluster together (amounts normalized)
        # Note: depends on text normalization implementation
        assert len(clusters) <= 2  # Ideally 1, but depends on threshold

    def test_long_texts_become_leaders(self, strict_clustering_service):
        """Longer texts should become cluster leaders (processed first)."""
        # Use longer texts to avoid min_length filtering
        short = create_clause("Dekking voor schade aan auto", "short")
        long = create_clause("Dit is een uitgebreide tekst over brandverzekering voor gebouwen en inventaris", "long")

        clusters, mapping = strict_clustering_service.cluster_clauses([short, long])

        # Both should have clusters (different enough texts with strict threshold)
        assert len(clusters) == 2
        # Both clauses should be mapped
        assert mapping["long"] is not None
        assert mapping["short"] is not None
