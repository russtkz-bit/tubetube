import threading
import unittest
from unittest import mock

from tubetube.downloader import OperationCancelled, _interruptible_sleep


class TestInterruptibleSleep(unittest.TestCase):
    def test_sleeps_in_steps_without_cancel_event(self):
        with mock.patch("tubetube.downloader.time.sleep") as mock_sleep:
            _interruptible_sleep(1.5, None)
        # 1.5s с шагом 0.5с -> 3 вызова time.sleep
        self.assertEqual(mock_sleep.call_count, 3)

    def test_raises_when_cancelled_before_start(self):
        ev = threading.Event()
        ev.set()
        with self.assertRaises(OperationCancelled):
            _interruptible_sleep(5, ev)

    def test_stops_early_when_cancelled_mid_sleep(self):
        ev = threading.Event()
        call_count = 0

        def fake_sleep(_):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                ev.set()  # отмена наступает посреди паузы

        with mock.patch("tubetube.downloader.time.sleep", side_effect=fake_sleep):
            with self.assertRaises(OperationCancelled):
                _interruptible_sleep(10, ev)

        # Не должно было досидеть все 20 шагов до конца 10-секундной паузы
        self.assertLess(call_count, 20)


if __name__ == "__main__":
    unittest.main()
