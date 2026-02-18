"""
Unit tests for timing utilities.

Tests cover:
- Timer context manager
- @timed decorator
- PhaseTimer with checkpoints
- Metrics collection
- Log levels
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager

from hienfeld.utils.timing import Timer, timed, PhaseTimer


class TestTimer:
    """Tests for Timer context manager."""

    def test_timer_basic_usage(self):
        """Test basic timer usage."""
        with Timer("test operation") as timer:
            time.sleep(0.05)

        assert timer.elapsed >= 0.05

    def test_timer_elapsed_during_execution(self):
        """Test that elapsed time is available during execution."""
        with Timer("test operation") as timer:
            time.sleep(0.05)
            elapsed_during = timer.elapsed
            assert elapsed_during >= 0.05

    def test_timer_elapsed_after_execution(self):
        """Test that elapsed time is available after execution."""
        timer = Timer("test operation")
        with timer:
            time.sleep(0.05)

        assert timer.elapsed >= 0.05

    def test_timer_start_time(self):
        """Test that start time is recorded."""
        with Timer("test operation") as timer:
            assert timer.start_time is not None
            assert isinstance(timer.start_time, float)

    def test_timer_end_time(self):
        """Test that end time is recorded."""
        with Timer("test operation") as timer:
            pass

        assert timer.end_time is not None
        assert isinstance(timer.end_time, float)
        assert timer.end_time >= timer.start_time

    def test_timer_elapsed_zero_before_start(self):
        """Test elapsed time is 0 before start."""
        timer = Timer("test operation")
        assert timer.elapsed == 0.0

    def test_timer_elapsed_available_while_running(self):
        """Test elapsed time available while running."""
        timer = Timer("test operation")
        timer.__enter__()
        time.sleep(0.01)
        elapsed = timer.elapsed
        timer.__exit__(None, None, None)

        assert elapsed > 0

    def test_timer_name(self):
        """Test timer name is stored."""
        name = "my operation"
        timer = Timer(name)
        assert timer.name == name

    def test_timer_log_level_default(self):
        """Test default log level."""
        timer = Timer("test")
        assert timer.log_level == "INFO"

    def test_timer_log_level_custom(self):
        """Test custom log level."""
        timer = Timer("test", log_level="DEBUG")
        assert timer.log_level == "DEBUG"

    def test_timer_exception_handling(self):
        """Test timer handles exceptions gracefully."""
        with pytest.raises(ValueError):
            with Timer("failing operation"):
                raise ValueError("Test error")

    def test_timer_exception_not_suppressed(self):
        """Test that exceptions are not suppressed."""
        try:
            with Timer("test"):
                raise RuntimeError("Expected error")
        except RuntimeError as e:
            assert str(e) == "Expected error"

    @patch('hienfeld.utils.timing.logger')
    def test_timer_logs_start(self, mock_logger):
        """Test that timer logs operation start."""
        with Timer("test operation"):
            pass

        # Check that start was logged
        call_args = [str(call) for call in mock_logger.info.call_args_list]
        assert any("START" in str(call) for call in call_args)

    @patch('hienfeld.utils.timing.logger')
    def test_timer_logs_completion(self, mock_logger):
        """Test that timer logs operation completion."""
        with Timer("test operation"):
            pass

        # Check that completion was logged
        call_args = [str(call) for call in mock_logger.info.call_args_list]
        assert any("DONE" in str(call) for call in call_args)

    @patch('hienfeld.utils.timing.logger')
    def test_timer_logs_failure(self, mock_logger):
        """Test that timer logs operation failure."""
        try:
            with Timer("failing operation"):
                raise ValueError("error")
        except ValueError:
            pass

        # Check that failure was logged
        call_args = [str(call) for call in mock_logger.error.call_args_list]
        assert any("FAILED" in str(call) for call in call_args)


class TestTimedDecorator:
    """Tests for @timed decorator."""

    def test_timed_basic_usage(self):
        """Test basic @timed decorator usage."""
        @timed()
        def slow_function():
            time.sleep(0.05)
            return "result"

        result = slow_function()
        assert result == "result"

    def test_timed_preserves_return_value(self):
        """Test that @timed preserves function return value."""
        @timed()
        def get_value():
            return 42

        assert get_value() == 42

    def test_timed_with_custom_name(self):
        """Test @timed with custom operation name."""
        @timed("custom operation")
        def my_function():
            return "result"

        result = my_function()
        assert result == "result"

    def test_timed_with_custom_log_level(self):
        """Test @timed with custom log level."""
        @timed("operation", log_level="DEBUG")
        def my_function():
            return "result"

        result = my_function()
        assert result == "result"

    def test_timed_with_arguments(self):
        """Test @timed decorated function with arguments."""
        @timed()
        def add(a, b):
            return a + b

        result = add(5, 3)
        assert result == 8

    def test_timed_with_kwargs(self):
        """Test @timed decorated function with keyword arguments."""
        @timed()
        def greet(name, greeting="Hello"):
            return f"{greeting} {name}"

        result = greet("World", greeting="Hi")
        assert result == "Hi World"

    def test_timed_preserves_function_name(self):
        """Test that @timed preserves function name."""
        @timed()
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_timed_exception_propagation(self):
        """Test that @timed propagates exceptions."""
        @timed()
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

    @patch('hienfeld.utils.timing.logger')
    def test_timed_logs_execution(self, mock_logger):
        """Test that @timed logs execution."""
        @timed("test_operation")
        def my_function():
            pass

        my_function()

        # Should have logged something
        assert mock_logger.info.called or mock_logger.debug.called

    def test_timed_default_name_uses_function_name(self):
        """Test that default name is function name."""
        @timed()
        def my_operation():
            pass

        # Timer should use function name
        my_operation()  # Should not raise


class TestPhaseTimer:
    """Tests for PhaseTimer multi-phase operations."""

    def test_phasetimer_creation(self):
        """Test creating a PhaseTimer."""
        timer = PhaseTimer("Analysis")
        assert timer.operation_name == "Analysis"
        assert timer.start_time is not None

    def test_phasetimer_single_checkpoint(self):
        """Test single checkpoint."""
        timer = PhaseTimer("Analysis")
        time.sleep(0.05)
        elapsed = timer.checkpoint("Load data")

        assert elapsed >= 0.05
        assert len(timer.checkpoints) == 1
        assert timer.checkpoints[0]["name"] == "Load data"

    def test_phasetimer_multiple_checkpoints(self):
        """Test multiple checkpoints."""
        timer = PhaseTimer("Analysis")

        time.sleep(0.02)
        timer.checkpoint("Phase 1")

        time.sleep(0.02)
        timer.checkpoint("Phase 2")

        time.sleep(0.02)
        timer.checkpoint("Phase 3")

        assert len(timer.checkpoints) == 3
        assert timer.checkpoints[0]["name"] == "Phase 1"
        assert timer.checkpoints[1]["name"] == "Phase 2"
        assert timer.checkpoints[2]["name"] == "Phase 3"

    def test_phasetimer_checkpoint_timing(self):
        """Test that checkpoint times are measured correctly."""
        timer = PhaseTimer("Analysis")

        time.sleep(0.05)
        elapsed1 = timer.checkpoint("Phase 1")
        assert elapsed1 >= 0.05

        time.sleep(0.05)
        elapsed2 = timer.checkpoint("Phase 2")
        assert elapsed2 >= 0.05

    def test_phasetimer_total_time(self):
        """Test that total time is cumulative."""
        timer = PhaseTimer("Analysis")

        time.sleep(0.02)
        cp1 = timer.checkpoint("Phase 1")

        time.sleep(0.02)
        cp2 = timer.checkpoint("Phase 2")

        assert timer.checkpoints[1]["elapsed_total"] > timer.checkpoints[0]["elapsed_total"]

    def test_phasetimer_finish(self):
        """Test finishing the timer."""
        timer = PhaseTimer("Analysis")

        time.sleep(0.05)
        timer.checkpoint("Phase 1")

        result = timer.finish()

        assert result["operation"] == "Analysis"
        assert result["total_time"] >= 0.05
        assert len(result["checkpoints"]) == 1

    def test_phasetimer_checkpoint_returns_elapsed(self):
        """Test that checkpoint returns elapsed time."""
        timer = PhaseTimer("Analysis")

        time.sleep(0.05)
        elapsed = timer.checkpoint("Phase 1")

        assert isinstance(elapsed, float)
        assert elapsed >= 0.05

    def test_phasetimer_checkpoint_data_structure(self):
        """Test that checkpoint data has expected structure."""
        timer = PhaseTimer("Analysis")
        time.sleep(0.01)
        timer.checkpoint("test phase")

        cp = timer.checkpoints[0]
        assert "name" in cp
        assert "timestamp" in cp
        assert "elapsed_since_last" in cp
        assert "elapsed_total" in cp

    @patch('hienfeld.utils.timing.logger')
    def test_phasetimer_logs_start(self, mock_logger):
        """Test that PhaseTimer logs start."""
        timer = PhaseTimer("Test")
        assert mock_logger.info.called

    @patch('hienfeld.utils.timing.logger')
    def test_phasetimer_logs_checkpoints(self, mock_logger):
        """Test that PhaseTimer logs checkpoints."""
        timer = PhaseTimer("Test")
        timer.checkpoint("Phase 1")
        assert mock_logger.info.called

    @patch('hienfeld.utils.timing.logger')
    def test_phasetimer_logs_finish(self, mock_logger):
        """Test that PhaseTimer logs finish."""
        timer = PhaseTimer("Test")
        timer.checkpoint("Phase 1")
        timer.finish()
        assert mock_logger.info.called


class TestTimingIntegration:
    """Integration tests for timing utilities."""

    def test_timer_and_decorator_together(self):
        """Test using Timer and @timed together."""
        @timed("outer operation")
        def outer_function():
            with Timer("inner operation"):
                time.sleep(0.01)
            return "done"

        result = outer_function()
        assert result == "done"

    def test_phasetimer_with_operations(self):
        """Test PhaseTimer timing real operations."""
        timer = PhaseTimer("Analysis")

        # Simulate analysis phases
        time.sleep(0.01)
        timer.checkpoint("Load data")

        time.sleep(0.01)
        timer.checkpoint("Process data")

        time.sleep(0.01)
        timer.checkpoint("Generate results")

        result = timer.finish()

        assert result["total_time"] >= 0.03
        assert len(result["checkpoints"]) == 3

    def test_nested_timers(self):
        """Test nested Timer contexts."""
        with Timer("outer") as outer_timer:
            time.sleep(0.01)
            with Timer("inner") as inner_timer:
                time.sleep(0.01)

        assert outer_timer.elapsed > inner_timer.elapsed

    def test_phasetimer_percentage_calculation(self):
        """Test that PhaseTimer calculates percentages correctly."""
        timer = PhaseTimer("Test")

        time.sleep(0.02)
        timer.checkpoint("Phase 1")

        time.sleep(0.04)
        timer.checkpoint("Phase 2")

        result = timer.finish()
        total = result["total_time"]

        # Verify checkpoints sum to total (approximately)
        phase_times = [cp["elapsed_since_last"] for cp in result["checkpoints"]]
        assert abs(sum(phase_times) - total) < 0.01


class TestEdgeCases:
    """Tests for edge cases."""

    def test_timer_very_short_operation(self):
        """Test timing very short operations."""
        with Timer("quick op") as timer:
            pass

        assert timer.elapsed >= 0.0

    def test_timer_very_long_operation(self):
        """Test timing long operations."""
        with Timer("long op") as timer:
            time.sleep(0.2)

        assert timer.elapsed >= 0.2

    def test_timer_zero_duration(self):
        """Test timer with no actual work."""
        with Timer("no work") as timer:
            pass

        assert timer.elapsed >= 0.0

    def test_phasetimer_no_checkpoints(self):
        """Test PhaseTimer with no checkpoints."""
        timer = PhaseTimer("Test")
        result = timer.finish()

        assert result["operation"] == "Test"
        assert len(result["checkpoints"]) == 0

    def test_phasetimer_single_checkpoint(self):
        """Test PhaseTimer with single checkpoint."""
        timer = PhaseTimer("Test")
        timer.checkpoint("Only phase")
        result = timer.finish()

        assert len(result["checkpoints"]) == 1

    @patch('hienfeld.utils.timing.logger')
    def test_timer_custom_log_level_debug(self, mock_logger):
        """Test timer with DEBUG log level."""
        with Timer("test", log_level="DEBUG"):
            pass

        # Should call logger methods

    @patch('hienfeld.utils.timing.logger')
    def test_timer_exception_logs_error(self, mock_logger):
        """Test that timer logs errors on exception."""
        try:
            with Timer("failing"):
                raise RuntimeError("test error")
        except RuntimeError:
            pass

        # Should have logged the error
        assert mock_logger.error.called

    def test_timed_multiple_calls(self):
        """Test @timed decorator on function called multiple times."""
        call_count = 0

        @timed()
        def increment():
            nonlocal call_count
            call_count += 1
            return call_count

        assert increment() == 1
        assert increment() == 2
        assert increment() == 3

    def test_phasetimer_checkpoint_names_with_special_chars(self):
        """Test checkpoint names with special characters."""
        timer = PhaseTimer("Test")
        timer.checkpoint("Phase 1 - Data Loading (fast)")
        timer.checkpoint("Phase 2 - Processing [main]")

        assert timer.checkpoints[0]["name"] == "Phase 1 - Data Loading (fast)"
        assert timer.checkpoints[1]["name"] == "Phase 2 - Processing [main]"
