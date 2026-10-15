import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from src.capture.color import decode_rgba16f, scrgb_to_bgr
from src.capture.bootstrap import configure_capture
from src.personal_distribution import configure_personal_distribution


class TestHdrCaptureAdapter(unittest.TestCase):
    def test_standard_srgb_and_channel_order(self):
        image = np.array([[[0.0, 0.18, 1.0, 1.0], [2.0, 0.0, 0.0, 1.0]]], dtype=np.float16)
        result = scrgb_to_bgr(image, 1.0)
        np.testing.assert_allclose(result, [[[255, 118, 0], [0, 0, 255]]], atol=1)
        self.assertEqual(result.dtype, np.uint8)
        self.assertTrue(result.flags.c_contiguous)

    def test_float_padding_does_not_enter_image(self):
        padded = np.zeros((2, 4, 4), dtype=np.float16)
        padded[:, :3] = .25
        padded[:, 3] = 9
        image = decode_rgba16f(padded.tobytes(), 3, 2, 32)
        self.assertEqual(image.shape, (2, 3, 4))
        self.assertTrue((image == .25).all())
        with self.assertRaises(ValueError):
            decode_rgba16f(padded.tobytes(), 3, 2, 16)

    def test_bad_calibration_and_invalid_float_fail_closed(self):
        image = np.zeros((2, 2, 4), dtype=np.float16)
        for value in (0, float('nan'), float('inf'), 20):
            with self.assertRaises(ValueError):
                scrgb_to_bgr(image, value)
        image[0, 0, 0] = float('nan')
        with self.assertRaises(ValueError):
            scrgb_to_bgr(image, 2)

    def test_default_and_legacy_do_not_install_adapter(self):
        config = {'windows': {'capture_method': ['WGC', 'BitBlt_RenderFull']}}
        with patch.dict(os.environ, {}, clear=True):
            configure_capture(config)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'profile.json'
            path.write_text(json.dumps({'mode': 'legacy_bgra8'}), encoding='utf-8')
            with patch.dict(os.environ, {'OK_WW_CAPTURE_PROFILE': str(path)}):
                configure_capture(config)
        self.assertEqual(config['windows']['capture_method'], ['WGC', 'BitBlt_RenderFull'])

    def test_incomplete_profile_stops_before_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'profile.json'
            path.write_text(json.dumps({'schema': 1, 'mode': 'calibrated_hdr_float'}), encoding='utf-8')
            with patch.dict(os.environ, {'OK_WW_CAPTURE_PROFILE': str(path)}):
                with self.assertRaises(ValueError):
                    configure_capture({})

    def test_installed_profile_is_used_without_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'capture-profile.json'
            path.write_text(json.dumps({'schema': 1, 'mode': 'calibrated_hdr_float'}), encoding='utf-8')
            with patch.dict(os.environ, {}, clear=True), patch('src.capture.bootstrap.DEFAULT_PROFILE', path):
                with self.assertRaises(ValueError):
                    configure_capture({})

    def test_personal_config_removes_upstream_launcher_upgrade(self):
        config = {'version': '3.7.4', 'update_pyappify': {'zip_url': 'upstream'}}
        configure_personal_distribution(config)
        self.assertNotIn('update_pyappify', config)
        self.assertIn('personal.hdr1', config['version'])


if __name__ == '__main__':
    unittest.main()
