# hienfeld/services/analysis/analysis_pipeline.py
"""
Analysis pipeline coordinator.

Implements the waterfall pattern where strategies are executed
in order until one returns a non-None result.
"""

from typing import Callable, Dict, List, Optional

from hienfeld.domain.cluster import Cluster
from hienfeld.domain.analysis import AnalysisAdvice, AdviceCode, ConfidenceLevel
from hienfeld.services.interfaces import IAnalysisStrategy, AnalysisContext
from hienfeld.logging_config import get_logger

logger = get_logger("analysis.pipeline")


class AnalysisPipeline:
    """
    Coordinates analysis strategies in a waterfall pattern.

    Strategies are executed in order by step_order until one returns
    a non-None result. If all strategies return None, a default
    fallback advice is generated.

    Default strategies (in order):
    - Step 0: AdminCheckStrategy
    - Step 0.5: CustomInstructionsStrategy
    - Step 1: ClauseLibraryStrategy
    - Step 2: ConditionsMatchStrategy
    - Step 3: FallbackStrategy

    Example usage:
        pipeline = AnalysisPipeline()
        pipeline.add_strategy(AdminCheckStrategy())
        pipeline.add_strategy(ConditionsMatchStrategy())

        advice = pipeline.analyze_cluster(cluster, context)
    """

    def __init__(self, strategies: Optional[List[IAnalysisStrategy]] = None) -> None:
        """
        Initialize the pipeline.

        Args:
            strategies: Optional list of strategies to add
        """
        self._strategies: List[IAnalysisStrategy] = []

        if strategies:
            for strategy in strategies:
                self.add_strategy(strategy)

    def add_strategy(self, strategy: IAnalysisStrategy) -> None:
        """
        Add a strategy to the pipeline.

        Strategies are automatically sorted by step_order.

        Args:
            strategy: Strategy to add
        """
        self._strategies.append(strategy)
        self._strategies.sort(key=lambda s: s.step_order)
        logger.debug(f"Added strategy: {strategy}")

    def remove_strategy(self, step_order: float) -> bool:
        """
        Remove a strategy by its step_order.

        Args:
            step_order: The step_order of the strategy to remove

        Returns:
            True if strategy was removed, False if not found
        """
        for i, strategy in enumerate(self._strategies):
            if strategy.step_order == step_order:
                removed = self._strategies.pop(i)
                logger.debug(f"Removed strategy: {removed}")
                return True
        return False

    @property
    def strategies(self) -> List[IAnalysisStrategy]:
        """Get list of strategies in execution order."""
        return list(self._strategies)

    def analyze_cluster(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> AnalysisAdvice:
        """
        Analyze a single cluster using all strategies.

        Executes strategies in order until one returns advice.
        If no strategy matches, returns a fallback advice.

        Args:
            cluster: Cluster to analyze
            context: Analysis context

        Returns:
            AnalysisAdvice from first matching strategy or fallback
        """
        for strategy in self._strategies:
            # Check if strategy can handle this cluster
            if not strategy.can_handle(cluster, context):
                continue

            # Try to analyze
            advice = strategy.analyze(cluster, context)

            if advice is not None:
                logger.debug(
                    f"Cluster {cluster.id} matched by {strategy.step_name}: "
                    f"{advice.advice_code}"
                )
                return advice

        # No strategy matched - create fallback
        logger.warning(f"No strategy matched cluster {cluster.id}, using fallback")
        return self._create_fallback_advice(cluster, context)

    def analyze_clusters(
        self,
        clusters: List[Cluster],
        context: AnalysisContext,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Dict[str, AnalysisAdvice]:
        """
        Analyze multiple clusters.

        Args:
            clusters: List of clusters to analyze
            context: Analysis context (shared)
            progress_callback: Optional progress callback (0-100)

        Returns:
            Dict mapping cluster_id -> AnalysisAdvice
        """
        advice_map: Dict[str, AnalysisAdvice] = {}
        total = len(clusters)

        # Track stats per strategy
        strategy_hits: Dict[str, int] = {s.step_name: 0 for s in self._strategies}
        strategy_hits["Fallback"] = 0

        for i, cluster in enumerate(clusters):
            # Analyze cluster
            advice = self.analyze_cluster(cluster, context)
            advice_map[cluster.id] = advice

            # Track which strategy matched
            matched = False
            for strategy in self._strategies:
                if strategy.can_handle(cluster, context):
                    test_advice = strategy.analyze(cluster, context)
                    if test_advice is not None:
                        strategy_hits[strategy.step_name] += 1
                        matched = True
                        break

            if not matched:
                strategy_hits["Fallback"] += 1

            # Progress callback
            if progress_callback and total > 0:
                pct = int((i + 1) / total * 100)
                progress_callback(pct)

        # Log statistics
        logger.info(f"Pipeline analyzed {total} clusters:")
        for name, count in strategy_hits.items():
            if count > 0:
                pct = count / total * 100 if total > 0 else 0
                logger.info(f"   {name}: {count} ({pct:.1f}%)")

        return advice_map

    def _create_fallback_advice(
        self,
        cluster: Cluster,
        context: AnalysisContext
    ) -> AnalysisAdvice:
        """
        Create fallback advice when no strategy matches.

        Args:
            cluster: Cluster that wasn't matched
            context: Analysis context

        Returns:
            Default AnalysisAdvice
        """
        return AnalysisAdvice(
            cluster_id=cluster.id,
            advice_code=AdviceCode.HANDMATIG_CHECKEN.value,
            reason="Geen advies gegenereerd door pipeline",
            confidence=ConfidenceLevel.LAAG.value,
            reference_article="-",
            category="UNKNOWN",
            cluster_name=cluster.name,
            frequency=cluster.frequency,
        )

    @classmethod
    def create_default(cls) -> "AnalysisPipeline":
        """
        Create a pipeline with default strategies.

        Returns:
            Configured AnalysisPipeline with all standard strategies
        """
        from .strategies import (
            AdminCheckStrategy,
            CustomInstructionsStrategy,
            ClauseLibraryStrategy,
            ConditionsMatchStrategy,
            FallbackStrategy,
        )

        pipeline = cls()
        pipeline.add_strategy(AdminCheckStrategy())
        pipeline.add_strategy(CustomInstructionsStrategy())
        pipeline.add_strategy(ClauseLibraryStrategy())
        pipeline.add_strategy(ConditionsMatchStrategy())
        pipeline.add_strategy(FallbackStrategy())

        return pipeline

    def __repr__(self) -> str:
        strategy_names = [f"{s.step_name}({s.step_order})" for s in self._strategies]
        return f"AnalysisPipeline([{', '.join(strategy_names)}])"
