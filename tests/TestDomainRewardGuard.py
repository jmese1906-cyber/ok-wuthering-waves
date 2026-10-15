"""Exercise task guards without constructing a live game/input executor."""
import ast
import os
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def method(file, class_name, name):
    tree = ast.parse((ROOT / 'src/task' / file).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {'os': os, 'CannotFindException': RuntimeError,
                 'stamina_re': re.compile(r'(\d+)/(\d+)'), 'number_re': re.compile(r'(\d+)')}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), file, 'exec'), namespace)
    return namespace[name]


get_stamina = method('BaseWWTask.py', 'BaseWWTask', 'get_stamina')
use_stamina = method('BaseWWTask.py', 'BaseWWTask', 'use_stamina')
open_reward = method('DomainTask.py', 'DomainTask', 'open_domain_reward')


class TestDomainRewardGuard(unittest.TestCase):
    def test_missing_fraction_is_unknown_including_backup_only(self):
        for texts in ([], ['460'], ['unrecognized']):
            task = Mock()
            task.wait_ocr.return_value = [SimpleNamespace(name=text) for text in texts]
            self.assertEqual(get_stamina(task), (-1, -1, -1))
            task.info_set.assert_not_called()

    def test_zero_stamina_is_distinct_from_unknown(self):
        task = Mock()
        task.wait_ocr.return_value = [SimpleNamespace(name='0/240'), SimpleNamespace(name='460')]
        self.assertEqual(get_stamina(task), (0, 460, 460))

    def test_unknown_or_insufficient_never_clicks_reward(self):
        with patch.dict(os.environ, {'OK_DAILY_NO_REFILL': '1'}):
            for values, message in [((-1, -1, -1), 'reading unavailable'),
                                    ((4, 460, 464), 'insufficient natural stamina')]:
                task = Mock()
                task.get_stamina.return_value = values
                with self.assertRaisesRegex(RuntimeError, message):
                    use_stamina(task, once=40)
                task.click_dialog_right_button.assert_not_called()
                task.click_dialog_left_button.assert_not_called()

    def test_already_open_dialog_does_not_move_or_press_f(self):
        task = Mock()
        task.has_claim_stamina.return_value = True
        open_reward(task)
        task.walk_to_treasure.assert_not_called()
        task.pick_f.assert_not_called()

    def test_disappearing_prompt_reapproaches_before_reading_stamina(self):
        task = Mock()
        task.has_claim_stamina.return_value = False
        task.has_claim.return_value = False
        task.pick_f.side_effect = [False, True]
        task.wait_until.return_value = True
        open_reward(task)
        self.assertEqual(task.walk_to_treasure.call_count, 2)
        task.wait_until.assert_called_once()
        task.get_stamina.assert_not_called()

    def test_unopened_dialog_stops_after_three_attempts(self):
        task = Mock()
        task.has_claim_stamina.return_value = False
        task.has_claim.return_value = False
        task.pick_f.return_value = True
        task.wait_until.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'did not open after 3'):
            open_reward(task)
        self.assertEqual(task.pick_f.call_count, 3)
        task.screenshot.assert_called_once_with('domain_reward_not_open')
        task.get_stamina.assert_not_called()


if __name__ == '__main__':
    unittest.main()
