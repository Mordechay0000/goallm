"""
Unit tests for image processing queue and analyzers.
Ensures: simulated analyzer shape, queue callback semantics, callback never blocks task_done.
"""
import time
import unittest
from unittest.mock import MagicMock

from core.filters.image.image_status_db import (
    EXPECTED_RESULT_KEYS,
    save_analysis_result,
    get_image_status,
)
from core.filters.image.image_processing_queue import (
    ImageProcessingQueue,
    TaskStatus,
)
from core.filters.image.simulated_image_analyzer import (
    SimulatedImageAnalyzer,
    CONDITIONS_CHECK,
)


# --- Simulated analyzer ---


class TestSimulatedAnalyzer(unittest.TestCase):
    def test_returns_expected_shape(self):
        """Simulated analyzer must return dict with all CONDITIONS_CHECK keys and Yes/No values."""
        analyzer = SimulatedImageAnalyzer()
        self.assertEqual(set(analyzer.CONDITIONS_CHECK), set(CONDITIONS_CHECK))
        self.assertEqual(set(CONDITIONS_CHECK), set(EXPECTED_RESULT_KEYS))

        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c\x20\x24\x2e' \x24\x22\x2c\x23\x1c\x1c(7\x2d\x2c\x32\x31\x34\x34\x34\x1f'9=9;<>6\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfe\xfd\x1f\xf5\x0f\xff\xd9"
        result = analyzer.analyze_image(jpeg_bytes, "image/jpeg")
        self.assertIsInstance(result, dict)
        for k in EXPECTED_RESULT_KEYS:
            self.assertIn(k, result, f"missing key {k}")
            self.assertIn(result[k], ("Yes", "No"), f"invalid value for {k}: {result[k]}")
        self.assertEqual(len(result), len(EXPECTED_RESULT_KEYS))


# --- Queue: get_task, callback, resilience ---


class TestImageProcessingQueue(unittest.TestCase):
    def test_get_task_unknown_returns_none(self):
        """get_task with unknown id must return None (no KeyError)."""
        done = []
        def on_done(*args):
            done.append(args)
        analyzer = MagicMock()
        analyzer.analyze_image.return_value = {k: "No" for k in EXPECTED_RESULT_KEYS}
        q = ImageProcessingQueue(
            image_analyzer=analyzer,
            on_task_done=on_done,
            analysis_timeout_seconds=5,
            watchdog_interval_seconds=60,
            max_workers=1,
        )
        try:
            self.assertIsNone(q.get_task("nonexistent-id"))
        finally:
            q._shutdown.set()

    def test_enqueue_callback_called_with_done(self):
        """Enqueue one task; callback must be called once with status DONE and valid result."""
        done = []
        def on_done(task_id, status, result, image_details, error):
            done.append((task_id, status, result, image_details, error))
        analyzer = MagicMock()
        analyzer.analyze_image.return_value = {k: "No" for k in EXPECTED_RESULT_KEYS}
        q = ImageProcessingQueue(
            image_analyzer=analyzer,
            on_task_done=on_done,
            analysis_timeout_seconds=5,
            watchdog_interval_seconds=60,
            max_workers=1,
        )
        try:
            q.enqueue(b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg", {"image_hash": "abc123"})
            for _ in range(50):
                if done:
                    break
                time.sleep(0.1)
            self.assertEqual(len(done), 1)
            _tid, status, result, details, err = done[0]
            self.assertEqual(status, TaskStatus.DONE)
            self.assertIsNotNone(result)
            self.assertEqual(set(result.keys()), set(EXPECTED_RESULT_KEYS))
            self.assertEqual(details.get("image_hash"), "abc123")
        finally:
            q._shutdown.set()

    def test_callback_raise_does_not_block_task_done(self):
        """When on_task_done raises, queue must still call task_done() so join completes."""
        first_called = []
        second_called = []

        def on_done(task_id, status, result, image_details, error):
            if not first_called:
                first_called.append(1)
                raise RuntimeError("callback fails on purpose")
            second_called.append((task_id, status, result))

        analyzer = MagicMock()
        analyzer.analyze_image.return_value = {k: "No" for k in EXPECTED_RESULT_KEYS}
        q = ImageProcessingQueue(
            image_analyzer=analyzer,
            on_task_done=on_done,
            analysis_timeout_seconds=2,
            watchdog_interval_seconds=60,
            max_workers=1,
        )
        try:
            q.enqueue(b"\xff\xd8\xff\xe0", "image/jpeg", {"image_hash": "h1"})
            q.enqueue(b"\xff\xd8\xff\xe1", "image/jpeg", {"image_hash": "h2"})
            q.wait_until_done()
            self.assertEqual(len(first_called), 1)
            self.assertEqual(len(second_called), 1)
        finally:
            q._shutdown.set()


# --- DB save_analysis_result validation ---


class TestSaveAnalysisResult(unittest.TestCase):
    def test_valid(self):
        """save_analysis_result accepts valid dict and persists."""
        result = {k: "No" for k in EXPECTED_RESULT_KEYS}
        result["female_visible_9_plus"] = "Yes"
        save_analysis_result("test_hash_valid_123", result, image_url="http://x", width=100, height=100)
        info = get_image_status("test_hash_valid_123")
        self.assertIsNotNone(info)
        self.assertEqual(info["status"], "blocked")
        # Optional: clear_all_image_status() to remove test row; skip if using shared DB

    def test_missing_key_raises(self):
        """save_analysis_result raises ValueError when a required key is missing."""
        result = {k: "No" for k in EXPECTED_RESULT_KEYS}
        del result["female_visible_9_plus"]
        with self.assertRaises(ValueError) as ctx:
            save_analysis_result("test_hash_missing", result)
        self.assertIn("missing required keys", str(ctx.exception))

    def test_bad_value_raises(self):
        """save_analysis_result raises ValueError when value is not Yes/No."""
        result = {k: "No" for k in EXPECTED_RESULT_KEYS}
        result["female_visible_9_plus"] = "Maybe"
        with self.assertRaises(ValueError) as ctx:
            save_analysis_result("test_hash_bad", result)
        self.assertIn("must be 'Yes' or 'No'", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
