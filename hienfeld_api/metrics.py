# hienfeld_api/metrics.py
"""
Prometheus metrics for the Hienfeld VB Converter API.

This module defines all application metrics and provides utility functions
for instrumenting FastAPI endpoints.

Usage:
    from hienfeld_api.metrics import (
        analysis_requests_total,
        analysis_duration_seconds,
        record_request,
    )

Metrics exposed:
    - vb_analysis_requests_total: Counter of analysis requests by status
    - vb_analysis_errors_total: Counter of analysis errors by type
    - vb_analysis_duration_seconds: Histogram of analysis duration
    - vb_active_jobs: Gauge of currently active jobs
    - vb_http_requests_total: Counter of HTTP requests by endpoint/method/status
    - vb_http_request_duration_seconds: Histogram of HTTP request duration
    - vb_clustering_duration_seconds: Histogram of clustering phase duration
    - vb_rows_processed_total: Counter of processed rows
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

# ---------------------------------------------------------------------------
# Application Info
# ---------------------------------------------------------------------------

app_info = Info(
    "vb_converter",
    "Information about the VB Converter application",
)

# Set application info at module load time
app_info.info({
    "version": "4.3",
    "component": "api",
})


# ---------------------------------------------------------------------------
# Counters - Track totals of events
# ---------------------------------------------------------------------------

analysis_requests_total = Counter(
    "vb_analysis_requests_total",
    "Total number of analysis requests",
    ["status"],  # started, completed, failed, cancelled
)

analysis_errors_total = Counter(
    "vb_analysis_errors_total",
    "Total number of analysis errors",
    ["error_type"],  # validation, processing, timeout, unknown
)

http_requests_total = Counter(
    "vb_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

rows_processed_total = Counter(
    "vb_rows_processed_total",
    "Total number of rows processed in analyses",
    ["analysis_mode"],  # fast, balanced, accurate
)


# ---------------------------------------------------------------------------
# Gauges - Track current values
# ---------------------------------------------------------------------------

active_jobs = Gauge(
    "vb_active_jobs",
    "Number of currently active analysis jobs",
)

cache_entries = Gauge(
    "vb_cache_entries",
    "Number of entries in service cache",
    ["cache_type"],  # nlp, embeddings, tfidf
)


# ---------------------------------------------------------------------------
# Histograms - Track distributions of values
# ---------------------------------------------------------------------------

# Analysis duration buckets: 10s, 30s, 1m, 2m, 5m, 10m, 15m, 30m
analysis_duration_seconds = Histogram(
    "vb_analysis_duration_seconds",
    "Time spent processing an analysis job",
    ["analysis_mode"],  # fast, balanced, accurate
    buckets=[10, 30, 60, 120, 300, 600, 900, 1800],
)

# HTTP request duration buckets: 10ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s
http_request_duration_seconds = Histogram(
    "vb_http_request_duration_seconds",
    "Time spent processing HTTP requests",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Pipeline phase durations
clustering_duration_seconds = Histogram(
    "vb_clustering_duration_seconds",
    "Time spent in clustering phase",
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

ingestion_duration_seconds = Histogram(
    "vb_ingestion_duration_seconds",
    "Time spent in file ingestion phase",
    buckets=[0.5, 1, 2, 5, 10, 30],
)

export_duration_seconds = Histogram(
    "vb_export_duration_seconds",
    "Time spent generating Excel export",
    buckets=[0.5, 1, 2, 5, 10, 30],
)


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------


def get_metrics() -> bytes:
    """
    Generate Prometheus metrics in text format.

    Returns:
        Prometheus metrics as bytes (text/plain; version=0.0.4)
    """
    return generate_latest(REGISTRY)


def get_content_type() -> str:
    """
    Get the content type for Prometheus metrics.

    Returns:
        Content type string for Prometheus exposition format
    """
    return CONTENT_TYPE_LATEST


@contextmanager
def track_duration(histogram: Histogram, labels: Optional[dict] = None):
    """
    Context manager to track duration of a code block.

    Usage:
        with track_duration(analysis_duration_seconds, {"analysis_mode": "balanced"}):
            run_analysis()
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        if labels:
            histogram.labels(**labels).observe(duration)
        else:
            histogram.observe(duration)


def track_request(method: str, endpoint: str):
    """
    Decorator to track HTTP request metrics.

    Usage:
        @app.get("/api/status/{job_id}")
        @track_request("GET", "/api/status")
        async def get_status(job_id: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            status_code = 200
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                # Try to extract status code from HTTPException
                status_code = getattr(e, "status_code", 500)
                raise
            finally:
                duration = time.perf_counter() - start_time
                http_requests_total.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=str(status_code),
                ).inc()
                http_request_duration_seconds.labels(
                    method=method,
                    endpoint=endpoint,
                ).observe(duration)
        return wrapper
    return decorator


def record_analysis_start():
    """Record that an analysis job has started."""
    analysis_requests_total.labels(status="started").inc()
    active_jobs.inc()


def record_analysis_complete(duration: float, analysis_mode: str, row_count: int):
    """
    Record that an analysis job has completed successfully.

    Args:
        duration: Total duration in seconds
        analysis_mode: Mode used (fast, balanced, accurate)
        row_count: Number of rows processed
    """
    analysis_requests_total.labels(status="completed").inc()
    active_jobs.dec()
    analysis_duration_seconds.labels(analysis_mode=analysis_mode).observe(duration)
    rows_processed_total.labels(analysis_mode=analysis_mode).inc(row_count)


def record_analysis_error(error_type: str):
    """
    Record an analysis error.

    Args:
        error_type: Type of error (validation, processing, timeout, unknown)
    """
    analysis_requests_total.labels(status="failed").inc()
    analysis_errors_total.labels(error_type=error_type).inc()
    active_jobs.dec()


def record_analysis_cancelled():
    """Record that an analysis job was cancelled."""
    analysis_requests_total.labels(status="cancelled").inc()
    active_jobs.dec()


def update_cache_metrics(nlp_count: int = 0, embeddings_count: int = 0, tfidf_count: int = 0):
    """
    Update cache entry gauges.

    Args:
        nlp_count: Number of NLP model cache entries
        embeddings_count: Number of embeddings cache entries
        tfidf_count: Number of TF-IDF vectorizer cache entries
    """
    cache_entries.labels(cache_type="nlp").set(nlp_count)
    cache_entries.labels(cache_type="embeddings").set(embeddings_count)
    cache_entries.labels(cache_type="tfidf").set(tfidf_count)
