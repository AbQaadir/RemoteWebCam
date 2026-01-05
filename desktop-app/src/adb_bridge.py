"""
ADB Bridge Module
Handles Android Debug Bridge operations for USB connectivity
"""

import subprocess
import threading
import time
from typing import Optional, List, Callable
from dataclasses import dataclass


@dataclass
class AndroidDevice:
    serial: str
    state: str
    model: Optional[str] = None
    product: Optional[str] = None


class ADBBridge:
    """Handles ADB operations for USB connection to Android devices"""
    
    DEFAULT_LOCAL_PORT = 8080
    DEFAULT_REMOTE_PORT = 8080
    
    def __init__(self):
        self._adb_path = "adb"
        self._port_forwarding_active = False
        self._connected_device: Optional[AndroidDevice] = None
        self._device_callback: Optional[Callable[[List[AndroidDevice]], None]] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitoring = False
    
    @property
    def is_available(self) -> bool:
        """Check if ADB is available"""
        return self._run_adb(["version"]) is not None
    
    @property
    def connected_device(self) -> Optional[AndroidDevice]:
        return self._connected_device
    
    @property
    def is_forwarding(self) -> bool:
        return self._port_forwarding_active
    
    def set_device_callback(self, callback: Callable[[List[AndroidDevice]], None]):
        """Set callback for device list changes"""
        self._device_callback = callback
    
    def _run_adb(self, args: List[str], timeout: int = 10) -> Optional[str]:
        """Run an ADB command and return output"""
        try:
            result = subprocess.run(
                [self._adb_path] + args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception:
            return None
    
    def get_devices(self) -> List[AndroidDevice]:
        """Get list of connected Android devices"""
        output = self._run_adb(["devices", "-l"])
        if not output:
            return []
        
        devices = []
        lines = output.split('\n')[1:]  # Skip header
        
        for line in lines:
            line = line.strip()
            if not line or 'offline' in line:
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]
                
                # Parse additional info
                model = None
                product = None
                for part in parts[2:]:
                    if part.startswith("model:"):
                        model = part.split(":")[1]
                    elif part.startswith("product:"):
                        product = part.split(":")[1]
                
                devices.append(AndroidDevice(
                    serial=serial,
                    state=state,
                    model=model,
                    product=product
                ))
        
        return devices
    
    def start_port_forwarding(
        self,
        device_serial: Optional[str] = None,
        local_port: int = DEFAULT_LOCAL_PORT,
        remote_port: int = DEFAULT_REMOTE_PORT
    ) -> bool:
        """Start ADB port forwarding"""
        args = ["forward"]
        
        if device_serial:
            args = ["-s", device_serial] + args
        
        args.extend([f"tcp:{local_port}", f"tcp:{remote_port}"])
        
        result = self._run_adb(args)
        if result is not None or result == "":
            self._port_forwarding_active = True
            
            # Set connected device
            devices = self.get_devices()
            if device_serial:
                self._connected_device = next(
                    (d for d in devices if d.serial == device_serial),
                    None
                )
            elif devices:
                self._connected_device = devices[0]
            
            return True
        
        return False
    
    def stop_port_forwarding(
        self,
        local_port: int = DEFAULT_LOCAL_PORT
    ) -> bool:
        """Stop ADB port forwarding"""
        result = self._run_adb(["forward", "--remove", f"tcp:{local_port}"])
        self._port_forwarding_active = False
        self._connected_device = None
        return result is not None
    
    def stop_all_forwarding(self) -> bool:
        """Stop all ADB port forwarding"""
        result = self._run_adb(["forward", "--remove-all"])
        self._port_forwarding_active = False
        self._connected_device = None
        return result is not None
    
    def start_device_monitor(self):
        """Start monitoring for device connections"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_device_monitor(self):
        """Stop device monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
            self._monitor_thread = None
    
    def _monitor_loop(self):
        """Background loop to monitor device connections"""
        last_devices = []
        
        while self._monitoring:
            devices = self.get_devices()
            
            # Check if device list changed
            current_serials = {d.serial for d in devices}
            last_serials = {d.serial for d in last_devices}
            
            if current_serials != last_serials:
                last_devices = devices
                if self._device_callback:
                    self._device_callback(devices)
            
            time.sleep(2)  # Check every 2 seconds
    
    def get_device_ip(self, device_serial: Optional[str] = None) -> Optional[str]:
        """Get the IP address of a connected device (if on Wi-Fi)"""
        args = []
        if device_serial:
            args = ["-s", device_serial]
        
        args.extend(["shell", "ip", "route", "get", "1"])
        output = self._run_adb(args)
        
        if output:
            # Parse: "1.0.0.0 via 192.168.1.1 dev wlan0 src 192.168.1.100"
            parts = output.split()
            try:
                src_idx = parts.index("src")
                return parts[src_idx + 1]
            except (ValueError, IndexError):
                pass
        
        return None
