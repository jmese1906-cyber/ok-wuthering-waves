"""Opt-in FLOAT WGC adapter for the tested ok-script 2.0.8 implementation."""

import ctypes
import hashlib
import time
from pathlib import Path

from src.capture.color import decode_rgba16f, scrgb_to_bgr


SUPPORTED_WGC_SHA256 = '948883dada14c5537e989b86e308954fb887ce40510ef8d4981b965b4da9475f'


def make_capture_class(reference_white):
    from ok.device.capture_methods import windows_graphics as original
    from ok.rotypes.Windows.Graphics.DirectX import DirectXPixelFormat

    digest = hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()
    if digest != SUPPORTED_WGC_SHA256:
        raise RuntimeError('HDR capture adapter: unvalidated ok-script capture implementation; '
                           'keep the pinned framework or revalidate before enabling')
    # Validate before creating a Direct3D device.
    import numpy as np
    scrgb_to_bgr(np.zeros((1, 1, 4), dtype=np.float16), reference_white)

    class HdrWindowsGraphicsCaptureMethod(original.WindowsGraphicsCaptureMethod):
        name = 'Windows Graphics Capture (calibrated FLOAT)'

        def __init__(self, hwnd_window):
            self._float_pool = None
            self._format_logged = False
            self._conversion_error = None
            self._format_transition_deadline = 0
            super().__init__(hwnd_window)

        def _start_or_stop(self, capture_cursor=False):
            result = super()._start_or_stop(capture_cursor)
            with self.lock:
                if result and self.frame_pool is not None and self._float_pool is not self.frame_pool:
                    # The base creates a session without requesting a frame.
                    # Recreate before accepting any frame for recognition.
                    try:
                        self.reset_framepool(self.last_size)
                        self._float_pool = self.frame_pool
                    except Exception:
                        self.close()
                        raise
            return result

        def reset_framepool(self, size, reset_device=False):
            with self.lock:
                if self.cputex:
                    self.cputex.Release()
                    self.cputex = None
                if reset_device:
                    # Reuse the framework's device recreation path.
                    self.create_device()
                self.frame_pool.Recreate(self.rtdevice, DirectXPixelFormat.R16G16B16A16Float, 2, size)
                self._format_transition_deadline = time.monotonic() + 2
                self._float_pool = self.frame_pool

        def convert_dx_frame(self, frame):
            if not frame or self.dxdevice is None or self.immediatedc is None:
                return None
            if (frame.ContentSize.Width != self.last_size.Width or
                    frame.ContentSize.Height != self.last_size.Height):
                self.last_size = frame.ContentSize
                self.reset_framepool(self.last_size)
                return None
            texture = None
            mapped = False
            context = self.immediatedc
            try:
                texture = frame.Surface.astype(self.IDirect3DDxgiInterfaceAccess).GetInterface(
                    self.d3d11.ID3D11Texture2D.GUID).astype(self.d3d11.ID3D11Texture2D)
                desc = texture.GetDesc()
                # WGC may deliver a queued BGRA8 frame from the original
                # session after Recreate. Never decode it as FLOAT. Ignore it
                # only during the bounded transition; persistent mismatch fails.
                if int(desc.Format) == 87 and time.monotonic() < self._format_transition_deadline:
                    return None
                if int(desc.Format) != 10:
                    raise RuntimeError(f'Expected RGBA16F texture, received format {desc.Format}')
                if self.cputex is None:
                    desc.Usage = self.d3d11.D3D11_USAGE_STAGING
                    desc.CPUAccessFlags = self.d3d11.D3D11_CPU_ACCESS_READ
                    desc.BindFlags = 0
                    desc.MiscFlags = 0
                    self.cputex = self.dxdevice.CreateTexture2D(ctypes.byref(desc), None)
                context.CopyResource(self.cputex, texture)
                info = context.Map(self.cputex, 0, self.d3d11.D3D11_MAP_READ, 0)
                mapped = True
                buffer = ctypes.string_at(info.pData, self.last_size.Height * info.RowPitch)
                raw = decode_rgba16f(buffer, self.last_size.Width, self.last_size.Height, info.RowPitch)
                result = scrgb_to_bgr(raw, reference_white)
                if not self._format_logged:
                    original.logger.info(f'HDR capture adapter: RGBA16F -> BGR8, reference_white={reference_white}; '
                                         'device calibration, no display settings changed')
                    self._format_logged = True
                return result
            except OSError as error:
                if error.winerror in (self.d3d11.DXGI_ERROR_DEVICE_REMOVED, self.d3d11.DXGI_ERROR_DEVICE_RESET):
                    self._conversion_error = RuntimeError('HDR capture device was reset; recreate the capture object '
                                                          'or restart the application')
                    return None
                self._conversion_error = error
                return None
            except Exception as error:
                self._conversion_error = error
                return None
            finally:
                if mapped:
                    context.Unmap(self.cputex, 0)
                if texture is not None:
                    texture.Release()

        def do_get_frame(self):
            if self._conversion_error:
                raise RuntimeError('HDR capture conversion failed; no fallback frame supplied') from self._conversion_error
            result = super().do_get_frame()
            if self._conversion_error:
                raise RuntimeError('HDR capture conversion failed; no fallback frame supplied') from self._conversion_error
            return result

    return HdrWindowsGraphicsCaptureMethod
