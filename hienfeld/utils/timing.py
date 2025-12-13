# hienfeld/utils/timing.py
"""
Performance timing utilities for development and debugging.
"""
import time
import functools
from typing import Callable, Any
from ..logging_config import get_logger

logger = get_logger('timing')


class Timer:
    """
    Context manager for timing code blocks.

    Usage:
        with Timer("My operation"):
            # code here
            pass
    """

    def __init__(self, name: str, log_level: str = "INFO"):
        self.name = name
        self.log_level = log_level.upper()
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = time.time()
        log_func = getattr(logger, self.log_level.lower(), logger.info)
        log_func(f"⏱️  START: {self.name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        elapsed = self.end_time - self.start_time

        if exc_type is not None:
            logger.error(f"❌ FAILED: {self.name} (after {elapsed:.2f}s) - {exc_type.__name__}: {exc_val}")
        else:
            log_func = getattr(logger, self.log_level.lower(), logger.info)
            log_func(f"✅ DONE: {self.name} ({elapsed:.2f}s)")

        return False  # Don't suppress exceptions

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        return 0.0


def timed(name: str = None, log_level: str = "DEBUG"):
    """
    Decorator for timing function execution.

    Usage:
        @timed("My function")
        def my_function():
            pass

    Args:
        name: Optional custom name for the operation
        log_level: Log level for timing messages (default: DEBUG)
    """
    def decorator(func: Callable) -> Callable:
        operation_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            with Timer(operation_name, log_level):
                return func(*args, **kwargs)

        return wrapper
    return decorator


class PhaseTimer:
    """
    Timer for tracking multi-phase operations with checkpoints.

    Usage:
        timer = PhaseTimer("Analysis")
        timer.checkpoint("Load data")
        # ... do work ...
        timer.checkpoint("Process data")
        # ... do work ...
        timer.finish()
    """

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = time.time()
        self.last_checkpoint = self.start_time
        self.checkpoints = []
        logger.info(f"🚀 BEGIN: {operation_name}")

    def checkpoint(self, phase_name: str) -> float:
        """
        Record a checkpoint and log the time since last checkpoint.

        Args:
            phase_name: Name of the phase being completed

        Returns:
            Elapsed time since last checkpoint in seconds
        """
        now = time.time()
        elapsed_since_last = now - self.last_checkpoint
        elapsed_total = now - self.start_time

        self.checkpoints.append({
            'name': phase_name,
            'timestamp': now,
            'elapsed_since_last': elapsed_since_last,
            'elapsed_total': elapsed_total
        })

        logger.info(
            f"📍 CHECKPOINT: {self.operation_name} → {phase_name} "
            f"(+{elapsed_since_last:.2f}s, total: {elapsed_total:.2f}s)"
        )

        self.last_checkpoint = now
        return elapsed_since_last

    def finish(self) -> dict:
        """
        Finish timing and log summary.

        Returns:
            Dictionary with timing statistics
        """
        total_time = time.time() - self.start_time

        logger.info(f"🏁 FINISH: {self.operation_name} (total: {total_time:.2f}s)")

        if self.checkpoints:
            logger.info(f"📊 Phase breakdown:")
            for cp in self.checkpoints:
                percentage = (cp['elapsed_since_last'] / total_time) * 100
                logger.info(
                    f"   • {cp['name']}: {cp['elapsed_since_last']:.2f}s ({percentage:.1f}%)"
                )

        return {
            'operation': self.operation_name,
            'total_time': total_time,
            'checkpoints': self.checkpoints
        }
