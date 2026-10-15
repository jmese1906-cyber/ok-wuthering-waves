import unittest
from unittest.mock import Mock, patch

from src.combat.DomainCompletionGuard import DomainCompletionGuard, SIMULATION_REWARD_TEXT


class Completed(Exception):
    pass


class Parent:
    def next_frame(self):
        return object()

    def combat_once(self):
        return 'finished'


class Probe(DomainCompletionGuard, Parent):
    domain_reward_text = SIMULATION_REWARD_TEXT

    def __init__(self, results):
        self._domain_combat_active = True
        self._in_combat = True
        self._domain_polling = False
        self._domain_next_poll = 0.0
        self._domain_reward_hits = 0
        self._domain_first_reward = None
        self.ocr = Mock(side_effect=results)
        self.log_info = Mock()
        self.screenshot = Mock()

    def _stop_completed_domain_combat(self):
        raise Completed()


class TestDomainCompletionGuard(unittest.TestCase):
    def test_combat_lifecycle_preserves_return_and_clears_flags(self):
        task = Probe([])
        self.assertEqual(task.combat_once(), 'finished')
        self.assertFalse(task._domain_combat_active)
        self.assertIsNone(task._domain_confirmed_elapsed)

    def test_only_exact_objective_matches(self):
        for text in ('领取奖励', '領取獎勵', 'Claim Rewards'):
            self.assertTrue(SIMULATION_REWARD_TEXT.fullmatch(text))
        for text in ('领取奖励后继续', '挑战中', '', '4/8'):
            self.assertFalse(SIMULATION_REWARD_TEXT.fullmatch(text))

    def test_animation_or_single_frame_cannot_stop_combo(self):
        task = Probe([[1], [], [1], []])
        task.skip_combat_check = True
        task.in_liberation = True
        with patch('src.combat.DomainCompletionGuard.time.monotonic', side_effect=[1, 2, 3, 4]):
            for _ in range(4):
                task.check_domain_completion()
        self.assertTrue(task._domain_combat_active)
        task.screenshot.assert_not_called()

    def test_two_separated_frames_interrupt_even_with_combat_skip(self):
        task = Probe([[1], [1]])
        task.skip_combat_check = True
        task.in_liberation = True
        with patch('src.combat.DomainCompletionGuard.time.monotonic', side_effect=[1, 1.1, 1.7]):
            task.check_domain_completion()
            task.check_domain_completion()
            with self.assertRaises(Completed):
                task.check_domain_completion()
        self.assertEqual(task.ocr.call_count, 2)
        frames = [call.kwargs['frame'] for call in task.ocr.call_args_list]
        self.assertIsNot(frames[0], frames[1])
        self.assertFalse(task._domain_combat_active)
        self.assertFalse(task._domain_polling)

    def test_zero_macro_wait_preserves_original_callback(self):
        task = Probe([])
        original = Mock(return_value='ok')
        self.assertEqual(task._wrap_domain_wait(original)(0), 'ok')
        original.assert_called_once_with(0)
        task.ocr.assert_not_called()

    def test_macro_wait_propagates_completion_before_more_inputs(self):
        task = Probe([])
        task.check_domain_completion = Mock(side_effect=Completed)
        original = Mock()
        with self.assertRaises(Completed):
            task._wrap_domain_wait(original)(2)
        original.assert_not_called()


if __name__ == '__main__':
    unittest.main()
