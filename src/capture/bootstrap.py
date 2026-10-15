import json
import os
from pathlib import Path

DEFAULT_PROFILE = Path(__file__).resolve().parents[2] / 'configs' / 'capture-profile.json'


def configure_capture(config):
    """Apply to every entry that imports config, including the official CLI."""
    selected = os.environ.get('OK_WW_CAPTURE_PROFILE')
    path = Path(selected) if selected else DEFAULT_PROFILE
    if not selected and not path.is_file():
        return
    profile = json.loads(path.read_text(encoding='utf-8'))
    if profile.get('mode') == 'legacy_bgra8':
        return
    if profile.get('mode') != 'calibrated_hdr_float' or profile.get('schema') != 1:
        raise ValueError('Unknown capture profile; no automatic fallback')
    if not profile.get('calibration_note'):
        raise ValueError('An explicit calibration_note is required for HDR capture')
    from src.capture.hdr_wgc import make_capture_class
    capture_class = make_capture_class(profile['reference_white'])
    from ok.device.capture_methods import update
    update.WindowsGraphicsCaptureMethod = capture_class
    config['windows']['capture_method'] = ['WGC']
