"""
Virtual Camera Module
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
        
        # Try to import pyvirtualcam
        try:
            import pyvirtualcam
            self._pyvirtualcam = pyvirtualcam
            self._available = True
        except ImportError:
            print("Warning: pyvirtualcam not installed. Virtual camera disabled.")
            print("Install with: pip install pyvirtualcam")
            print("Also requires OBS Virtual Camera to be installed.")
    
    @property
    def is_available(self) -> bool:
        """Check if virtual camera is available"""
        return self._available
    
    @property
    def is_enabled(self) -> bool:
        """Check if virtual camera is currently enabled"""
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
    
    def send_frame(self, frame: np.ndarray):
        """Send a frame to the virtual camera"""
        if not self._enabled or self._camera is None:
            return
        
        with self._lock:
            try:
                # Resize frame if needed
                h, w = frame.shape[:2]
                if w != self._width or h != self._height:
                    import cv2
                    frame = cv2.resize(frame, (self._width, self._height))
                
                # Send frame
                self._camera.send(frame)
                self._camera.sleep_until_next_frame()
                
            except Exception as e:
                print(f"Error sending frame: {e}")
    
    def get_device_name(self) -> Optional[str]:
        """Get the virtual camera device name"""
        if self._camera:
            return self._camera.device
        return None


# Alternative: Use FFmpeg-based virtual camera (fallback)
class FFmpegVirtualCamera:
    """
    Fallback virtual camera using FFmpeg.
    Requires FFmpeg with dshow input device support.
    """
    
    def __init__(self):
        self._process = None
        self._enabled = False
        self._available = self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available"""
        import subprocess
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
    
    def start(self, width: int = 1280, height: int = 720, fps: int = 30) -> bool:
        """Start FFmpeg virtual camera output"""
        # This would require additional setup with a virtual camera driver
        # For now, this is a placeholder for future implementation
        return False
    
    def stop(self):
        """Stop FFmpeg process"""
        if self._process:
            self._process.terminate()
            self._process = None
        self._enabled = False
    
    def send_frame(self, frame: np.ndarray):
        """Send frame to FFmpeg"""
        pass
