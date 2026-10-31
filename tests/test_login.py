import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from browser_login import sign_in_normally
from flow_engine import Stopped


class LoginTests(unittest.TestCase):
    def test_normal_login_then_close_before_automation(self):
        process = Mock()
        process.poll.side_effect = [None, 0]
        opener = Mock(return_value=process)
        confirm = Mock(return_value=True)
        with tempfile.TemporaryDirectory() as directory:
            with patch('browser_login.find_browser', return_value=Path('C:/Edge/msedge.exe')):
                sign_in_normally('msedge', Path(directory), lambda _: None, confirm, lambda: False, opener)
        arguments = opener.call_args.args[0]
        self.assertTrue(any(arg.startswith('--user-data-dir=') for arg in arguments))
        self.assertFalse(any('remote-debugging' in arg or 'automation' in arg for arg in arguments))
        self.assertEqual(confirm.call_count, 2)

    def test_cancel_does_not_continue(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('browser_login.find_browser', return_value=Path('C:/Edge/msedge.exe')):
                with self.assertRaises(Stopped):
                    sign_in_normally('msedge', Path(directory), lambda _: None, lambda _: False,
                                     lambda: False, Mock())

    def test_cancel_before_browser_launch(self):
        opener = Mock()
        with self.assertRaises(Stopped):
            sign_in_normally('msedge', Path('unused'), lambda _: None, lambda _: True,
                             lambda: True, opener)
        opener.assert_not_called()
