#!/usr/bin/env python3
"""
Performance benchmark script for measuring optimization impact.

Usage:
    python scripts/benchmark_performance.py --mode balanced --rows 1660
"""
import sys
import time
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hienfeld.config import load_config, AnalysisMode
from hienfeld.domain.clause import Clause
from hienfeld.services.clustering_service import ClusteringService
from hienfeld.services.similarity_service import RapidFuzzSimilarityService
from hienfeld.logging_config import setup_logging, get_logger

# Setup logging
setup_logging()
logger = get_logger('benchmark')


def generate_test_clauses(count: int) -> list:
    """Generate synthetic test clauses"""
    clauses = []

    # Base templates
    templates = [
        "Deze polis dekt schade aan {item} tot een bedrag van {bedrag}",
        "Uitgesloten zijn schades door {oorzaak} en {oorzaak2}",
        "De verzekering geldt voor {locatie} en omgeving",
        "Eigen risico bedraagt {bedrag} per gebeurtenis",
        "Dekking is van toepassing op {tijdstip} tot {tijdstip2}",
    ]

    # Variations
    items = ["gebouw", "inventaris", "goederen", "voertuig", "machines"]
    bedragen = ["€5.000", "€10.000", "€25.000", "€50.000", "€100.000"]
    oorzaken = ["opzet", "oorlog", "natuurrampen", "kernenergie", "terrorisme"]
    locaties = ["Nederland", "Europa", "wereldwijd", "vestigingsadres", "het verzekerde"]
    tijden = ["01-01-2024", "01-07-2024", "datum aanvraag", "ingangsdatum"]

    import random
    random.seed(42)  # Reproducible

    for i in range(count):
        template = random.choice(templates)
        text = template.format(
            item=random.choice(items),
            bedrag=random.choice(bedragen),
            oorzaak=random.choice(oorzaken),
            oorzaak2=random.choice(oorzaken),
            locatie=random.choice(locaties),
            tijdstip=random.choice(tijden),
            tijdstip2=random.choice(tijden)
        )

        # Add some variation
        if i % 10 == 0:
            text = text.upper()
        if i % 7 == 0:
            text = f"Let op: {text}"

        clause = Clause(
            id=f"TEST-{i:05d}",
            raw_text=text,
            simplified_text=text.lower().strip(),
            source_policy_number=f"POL-{i % 100:03d}",
            source_file_name="benchmark.csv"
        )
        clauses.append(clause)

    return clauses


def benchmark_clustering(clauses: list, mode: str, config):
    """Benchmark clustering performance"""
    logger.info("=" * 80)
    logger.info(f"BENCHMARK: Clustering {len(clauses)} clauses in {mode.upper()} mode")
    logger.info("=" * 80)

    # Apply mode
    analysis_mode = AnalysisMode(mode)
    config.semantic.apply_mode(analysis_mode)

    # Create services
    base_similarity = RapidFuzzSimilarityService(
        threshold=config.clustering.similarity_threshold
    )

    # Try to use hybrid similarity if available
    try:
        from hienfeld.services.hybrid_similarity_service import HybridSimilarityService
        from hienfeld.services.nlp_service import NLPService

        nlp_service = NLPService(config)
        if nlp_service.is_available:
            similarity_service = HybridSimilarityService(config)
            logger.info("✅ Using HybridSimilarityService")
        else:
            similarity_service = base_similarity
            logger.info("⚠️ NLP not available, using RapidFuzz only")
    except ImportError:
        similarity_service = base_similarity
        logger.info("⚠️ Hybrid similarity not available, using RapidFuzz only")

    clustering_service = ClusteringService(
        config=config,
        similarity_service=similarity_service
    )

    # Warm-up (load models)
    logger.info("Warming up (loading models)...")
    warmup_clauses = clauses[:10]
    clustering_service.cluster_clauses(warmup_clauses)
    logger.info("✅ Warm-up complete")

    # Actual benchmark
    logger.info(f"Starting benchmark with {len(clauses)} clauses...")

    start_time = time.time()
    clusters, clause_to_cluster = clustering_service.cluster_clauses(clauses)
    end_time = time.time()

    duration = end_time - start_time

    # Statistics
    logger.info("=" * 80)
    logger.info("RESULTS:")
    logger.info("=" * 80)
    logger.info(f"Total time: {duration:.2f}s ({duration/60:.2f} minutes)")
    logger.info(f"Clauses: {len(clauses)}")
    logger.info(f"Clusters: {len(clusters)}")
    logger.info(f"Avg cluster size: {len(clauses) / len(clusters):.1f}")
    logger.info(f"Throughput: {len(clauses) / duration:.1f} clauses/second")
    logger.info("=" * 80)

    # Get statistics if hybrid service
    if hasattr(similarity_service, 'get_statistics'):
        stats = similarity_service.get_statistics()
        logger.info("Similarity Statistics:")
        for key, value in stats.items():
            if isinstance(value, dict):
                logger.info(f"  {key}:")
                for k, v in value.items():
                    logger.info(f"    {k}: {v}")
            else:
                logger.info(f"  {key}: {value}")
        logger.info("=" * 80)

    return {
        'duration': duration,
        'clauses': len(clauses),
        'clusters': len(clusters),
        'throughput': len(clauses) / duration,
        'mode': mode
    }


def main():
    parser = argparse.ArgumentParser(description='Benchmark clustering performance')
    parser.add_argument('--mode', default='balanced', choices=['fast', 'balanced', 'accurate'],
                        help='Analysis mode')
    parser.add_argument('--rows', type=int, default=1660,
                        help='Number of test rows')
    parser.add_argument('--dev-mode', action='store_true',
                        help='Enable developer mode logging')

    args = parser.parse_args()

    # Set dev mode if requested
    if args.dev_mode:
        import os
        os.environ['HIENFELD_DEV_MODE'] = '1'

    # Load config
    config = load_config()

    # Generate test data
    logger.info(f"Generating {args.rows} test clauses...")
    clauses = generate_test_clauses(args.rows)
    logger.info(f"✅ Generated {len(clauses)} test clauses")

    # Run benchmark
    result = benchmark_clustering(clauses, args.mode, config)

    # Summary
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"Mode: {result['mode'].upper()}")
    print(f"Clauses: {result['clauses']}")
    print(f"Clusters: {result['clusters']}")
    print(f"Duration: {result['duration']:.2f}s ({result['duration']/60:.2f} min)")
    print(f"Throughput: {result['throughput']:.1f} clauses/sec")
    print("=" * 80)

    # Compare to baseline (approximate)
    baseline_times = {
        'fast': 240,      # 4 minutes
        'balanced': 620,  # 10+ minutes
        'accurate': 1547  # 25+ minutes
    }

    baseline = baseline_times.get(args.mode, 600)
    speedup = baseline / result['duration']

    print(f"\n📊 PERFORMANCE vs BASELINE (1660 rows):")
    print(f"   Baseline (v1.0): ~{baseline}s ({baseline/60:.1f} min)")
    print(f"   Current (v1.1): {result['duration']:.0f}s ({result['duration']/60:.1f} min)")
    print(f"   Speedup: {speedup:.2f}x faster! 🚀")
    print("=" * 80)

    return 0


if __name__ == '__main__':
    sys.exit(main())
