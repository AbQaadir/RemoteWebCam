"""
Stream Receiver Module
Handles receiving and decoding MJPEG streams from the phone
"""

import cv2
import numpy as np
import requests
import threading
import time
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum


class ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class StreamStats:
    fps: float = 0.0
    frame_count: int = 0
    bytes_received: int = 0
    latency_ms: float = 0.0


class StreamReceiver:
    """Receives MJPEG stream from the phone and provides frames"""
    
    def __init__(self):
        self._stream_url: Optional[str] = None
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._current_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._status = ConnectionStatus.DISCONNECTED
        self._status_callback: Optional[Callable[[ConnectionStatus, str], None]] = None
        self._frame_callback: Optional[Callable[[np.ndarray], None]] = None
        self._stats = StreamStats()
        self._last_frame_time: float = 0
        self._frame_times: list = []
    
    @property
    def status(self) -> ConnectionStatus:
        return self._status
    
    @property
    def stats(self) -> StreamStats:
        return self._stats
    
    @property
    def is_connected(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED
    
    def set_status_callback(self, callback: Callable[[ConnectionStatus, str], None]):
        """Set callback for status changes"""
        self._status_callback = callback
    
    def set_frame_callback(self, callback: Callable[[np.ndarray], None]):
        """Set callback for new frames"""
        self._frame_callback = callback
    
    def _update_status(self, status: ConnectionStatus, message: str = ""):
        self._status = status
        if self._status_callback:
            self._status_callback(status, message)
    
    def connect(self, host: str, port: int = 8080):
        """Connect to the phone stream"""
        if self._running:
            self.disconnect()
        
        # Build stream URL
        if not host.startswith("http"):
            host = f"http://{host}"
        self._stream_url = f"{host}:{port}/video"
        
        self._running = True
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()
    
    def disconnect(self):
        """Disconnect from the stream"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._current_frame = None
        self._stats = StreamStats()
        self._update_status(ConnectionStatus.DISCONNECTED)
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the current frame (thread-safe)"""
        with self._frame_lock:
            return self._current_frame.copy() if self._current_frame is not None else None
    
    def _receive_loop(self):
        """Main receive loop - runs in a separate thread"""
        self._update_status(ConnectionStatus.CONNECTING, f"Connecting to {self._stream_url}...")
        
        try:
            # Connect with streaming enabled
            response = requests.get(
                self._stream_url,
                stream=True,
                timeout=10
            )
            response.raise_for_status()
            
            self._update_status(ConnectionStatus.CONNECTED, "Stream connected")
            
            # Read MJPEG stream
            bytes_buffer = b""
            
            for chunk in response.iter_content(chunk_size=4096):
                if not self._running:
                    break
                
                bytes_buffer += chunk
                self._stats.bytes_received += len(chunk)
                
                # Look for JPEG markers
                start = bytes_buffer.find(b'\xff\xd8')  # JPEG start
                end = bytes_buffer.find(b'\xff\xd9')    # JPEG end
                
                if start != -1 and end != -1 and end > start:
                    # Extract JPEG frame
                    jpeg_data = bytes_buffer[start:end + 2]
                    bytes_buffer = bytes_buffer[end + 2:]
                    
                    # Decode frame
                    frame = self._decode_frame(jpeg_data)
                    if frame is not None:
                        self._update_frame(frame)
            
        except requests.exceptions.ConnectionError as e:
            self._update_status(ConnectionStatus.ERROR, f"Connection failed: {str(e)}")
        except requests.exceptions.Timeout:
            self._update_status(ConnectionStatus.ERROR, "Connection timed out")
        except Exception as e:
            self._update_status(ConnectionStatus.ERROR, f"Error: {str(e)}")
        finally:
            if self._running:
                self._update_status(ConnectionStatus.DISCONNECTED)
            self._running = False
    
    def _decode_frame(self, jpeg_data: bytes) -> Optional[np.ndarray]:
        """Decode JPEG bytes to numpy array"""
        try:
            nparr = np.frombuffer(jpeg_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame
        except Exception:
            return None
    
    def _update_frame(self, frame: np.ndarray):
        """Update the current frame and calculate stats"""
        current_time = time.time()
        
        # Calculate FPS
        if self._last_frame_time > 0:
            self._frame_times.append(current_time - self._last_frame_time)
            # Keep only last 30 frame times
            if len(self._frame_times) > 30:
                self._frame_times.pop(0)
            
            if self._frame_times:
                avg_time = sum(self._frame_times) / len(self._frame_times)
                self._stats.fps = 1.0 / avg_time if avg_time > 0 else 0
        
        self._last_frame_time = current_time
        self._stats.frame_count += 1
        
        # Update frame (thread-safe)
        with self._frame_lock:
            self._current_frame = frame
        
        # Call frame callback
        if self._frame_callback:
            self._frame_callback(frame)


class OpenCVReceiver(StreamReceiver):
    """Alternative receiver using OpenCV's VideoCapture (more stable)"""
    
    def __init__(self):
        super().__init__()
        self._capture: Optional[cv2.VideoCapture] = None
    
    def connect(self, host: str, port: int = 8080):
        """Connect using OpenCV VideoCapture"""
        if self._running:
            self.disconnect()
        
        # Build stream URL
        if not host.startswith("http"):
            host = f"http://{host}"
        self._stream_url = f"{host}:{port}/video"
        
        self._running = True
        self._thread = threading.Thread(target=self._opencv_receive_loop, daemon=True)
        self._thread.start()
    
    def disconnect(self):
        """Disconnect and release capture"""
        self._running = False
        if self._capture:
            self._capture.release()
            self._capture = None
        super().disconnect()
    
    def _opencv_receive_loop(self):
        """Receive loop using OpenCV VideoCapture"""
        self._update_status(ConnectionStatus.CONNECTING, f"Connecting to {self._stream_url}...")
        
        try:
            self._capture = cv2.VideoCapture(self._stream_url)
            
            if not self._capture.isOpened():
                self._update_status(ConnectionStatus.ERROR, "Failed to open stream")
                return
            
            self._update_status(ConnectionStatus.CONNECTED, "Stream connected")
            
            while self._running:
                ret, frame = self._capture.read()
                
                if not ret:
                    if self._running:
                        self._update_status(ConnectionStatus.ERROR, "Lost connection")
                    break
                
                self._update_frame(frame)
            
        except Exception as e:
            self._update_status(ConnectionStatus.ERROR, f"Error: {str(e)}")
        finally:
            if self._capture:
                self._capture.release()
            if self._running:
                self._update_status(ConnectionStatus.DISCONNECTED)
            self._running = False
