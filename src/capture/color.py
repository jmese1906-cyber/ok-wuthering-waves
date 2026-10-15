"""Convert linear scRGB to the SDR images consumed by the existing recognizer.

The reference white is an explicit, device-specific calibration. It is not a
Windows brightness setting and must not be silently estimated from each scene.
"""

import math

import numpy as np


def scrgb_to_bgr(frame, reference_white):
    if not math.isfinite(reference_white) or not 1 <= reference_white <= 12.5:
        raise ValueError('reference_white must be finite and between 1 and 12.5')
    if frame.ndim != 3 or frame.shape[2] not in (3, 4) or frame.dtype.kind != 'f':
        raise ValueError('Expected float RGB/RGBA capture data')
    linear = frame[:, :, :3].astype(np.float32)
    if not np.isfinite(linear).all():
        raise ValueError('Capture contains non-finite color values')
    linear = np.maximum(linear / reference_white, 0)
    srgb = np.where(linear <= 0.0031308, 12.92 * linear,
                    1.055 * np.power(linear, 1 / 2.4) - 0.055)
    # Highlights above the calibrated white are clipped only after decoding
    # the original float data; dark and midtone detail remains available.
    return np.ascontiguousarray(np.rint(np.clip(srgb[:, :, ::-1], 0, 1) * 255).astype(np.uint8))


def decode_rgba16f(buffer, width, height, row_pitch):
    if width <= 0 or height <= 0 or row_pitch < width * 8 or row_pitch % 8:
        raise ValueError('Invalid RGBA16F texture layout')
    return np.frombuffer(buffer, dtype=np.float16, count=height * row_pitch // 2).reshape(
        height, row_pitch // 8, 4)[:, :width].copy()
