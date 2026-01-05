"""
Virtual Camera Module - Optimized for low latency
Handles routing frames to a virtual camera device for use in Zoom, Teams, etc.
"""

import numpy as np
from typing import Optional
import threading


class VirtualCamera:
    """Wrapper for pyvirtualcam to output frames to a virtual camera"""
    
    def __init__(self):
        self._camera = None
        self._enabled = False
        self._width = 1280
        self._height = 720
        self._fps = 30
        self._lock = threading.Lock()
        self._pyvirtualcam = None
        self._available = False
        self._cv2 = None
        
        # Cache for resize parameters (avoids recalculation)
        self._last_input_shape = None
        self._crop_params = None
        
        # Try to import dependencies
        try:
            import pyvirtualcam
            import cv2
            self._pyvirtualcam = pyvirtualcam
            self._cv2 = cv2
            self._available = True
        except ImportError:
            print("Warning: pyvirtualcam not installed. Virtual camera disabled.")
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled and self._camera is not None
    
    def start(self, width: int = 1280, height: int = 720, fps: int = 30) -> bool:
        """Start the virtual camera"""
        if not self._available:
            return False
        
        with self._lock:
            if self._camera is not None:
                return True
            
            try:
                self._width = width
                self._height = height
                self._fps = fps
                
                self._camera = self._pyvirtualcam.Camera(
                    width=width,
                    height=height,
                    fps=fps,
                    fmt=self._pyvirtualcam.PixelFormat.BGR
                )
                self._enabled = True
                print(f"Virtual camera started: {self._camera.device}")
                return True
                
            except Exception as e:
                print(f"Failed to start virtual camera: {e}")
                self._camera = None
                self._enabled = False
                return False
    
    def stop(self):
        """Stop the virtual camera"""
        with self._lock:
            if self._camera is not None:
                try:
                    self._camera.close()
                except Exception:
                    pass
                self._camera = None
            self._enabled = False
            self._last_input_shape = None
            self._crop_params = None
    
    def _calculate_crop_params(self, h: int, w: int):
        """Calculate crop parameters for 16:9 conversion (cached)"""
        target_aspect = 16 / 9
        current_aspect = w / h
        
        if abs(current_aspect - target_aspect) < 0.01:
            # Already 16:9
            self._crop_params = (0, 0, w, h, False)
        elif current_aspect < target_aspect:
            # Portrait - crop top/bottom
            new_height = int(w / target_aspect)
            y_offset = (h - new_height) // 2
            self._crop_params = (0, y_offset, w, new_height, True)
        else:
            # Wider than 16:9 - crop left/right
            new_width = int(h * target_aspect)
            x_offset = (w - new_width) // 2
            self._crop_params = (x_offset, 0, new_width, h, True)
    
    def send_frame(self, frame: np.ndarray):
        """Send a frame to the virtual camera (optimized for speed)"""
        if not self._enabled or self._camera is None:
            return
        
        try:
            h, w = frame.shape[:2]
            
            # Recalculate crop params only if frame size changed
            if self._last_input_shape != (h, w):
                self._last_input_shape = (h, w)
                self._calculate_crop_params(h, w)
            
            # Fast crop if needed
            x, y, cw, ch, needs_crop = self._crop_params
            if needs_crop:
                frame = frame[y:y+ch, x:x+cw]
            
            # Fast resize using INTER_LINEAR (fastest with decent quality)
            if frame.shape[1] != self._width or frame.shape[0] != self._height:
                frame = self._cv2.resize(
                    frame, 
                    (self._width, self._height),
                    interpolation=self._cv2.INTER_LINEAR
                )
            
            # Send immediately
            self._camera.send(frame)
            
        except Exception as e:
            pass  # Silently ignore errors to prevent log spam
    
    def get_device_name(self) -> Optional[str]:
        """Get the virtual camera device name"""
        if self._camera:
            return self._camera.device
        return None


# Simplified fallback class
class FFmpegVirtualCamera:
    """Placeholder for FFmpeg-based virtual camera"""
    
    def __init__(self):
        self._available = False
    
    @property
    def is_available(self) -> bool:
        return False
    
    @property
    def is_enabled(self) -> bool:
        return False
    
    def start(self, width: int = 1280, height: int = 720, fps: int = 30) -> bool:
        return False
    
    def stop(self):
        pass
    
    def send_frame(self, frame: np.ndarray):
        pass
