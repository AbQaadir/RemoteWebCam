"""
Remote Webcam Desktop Application
Main application with PyQt6 GUI
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QFrame, QGroupBox,
    QCheckBox, QStatusBar, QMessageBox, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QImage, QPixmap, QIcon, QAction, QPalette, QColor
import cv2
import numpy as np

from .receiver import OpenCVReceiver, ConnectionStatus
from .virtual_cam import VirtualCamera
from .adb_bridge import ADBBridge, AndroidDevice
from typing import List, Optional


class FrameWorker(QThread):
    """Worker thread for receiving and processing frames"""
    frame_ready = pyqtSignal(np.ndarray)
    status_changed = pyqtSignal(str, str)  # status, message
    
    def __init__(self, receiver: OpenCVReceiver):
        super().__init__()
        self._receiver = receiver
        self._receiver.set_frame_callback(self._on_frame)
        self._receiver.set_status_callback(self._on_status)
    
    def _on_frame(self, frame: np.ndarray):
        self.frame_ready.emit(frame)
    
    def _on_status(self, status: ConnectionStatus, message: str):
        self.status_changed.emit(status.value, message)


class RemoteWebcamApp:
    """Main application class"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Remote Webcam")
        self.app.setOrganizationName("RemoteWebcam")
        
        # Set dark theme
        self._apply_dark_theme()
        
        # Create main window
        self.window = MainWindow()
    
    def _apply_dark_theme(self):
        """Apply dark color scheme"""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(13, 17, 23))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 246, 252))
        palette.setColor(QPalette.ColorRole.Base, QColor(22, 27, 34))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(33, 38, 45))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(22, 27, 34))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(240, 246, 252))
        palette.setColor(QPalette.ColorRole.Text, QColor(240, 246, 252))
        palette.setColor(QPalette.ColorRole.Button, QColor(33, 38, 45))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(240, 246, 252))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Link, QColor(88, 166, 255))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(88, 166, 255))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        
        self.app.setPalette(palette)
        
        # Set stylesheet for additional styling
        self.app.setStyleSheet("""
            QMainWindow {
                background-color: #0d1117;
            }
            QGroupBox {
                border: 1px solid #30363d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
            QPushButton {
                background-color: #238636;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
            QPushButton:pressed {
                background-color: #1a7f37;
            }
            QPushButton:disabled {
                background-color: #21262d;
                color: #6e7681;
            }
            QPushButton#secondaryBtn {
                background-color: #21262d;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #30363d;
            }
            QPushButton#dangerBtn {
                background-color: #da3633;
            }
            QPushButton#dangerBtn:hover {
                background-color: #f85149;
            }
            QLineEdit, QComboBox {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
                min-height: 20px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #58a6ff;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QLabel#previewLabel {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
            QStatusBar {
                background-color: #161b22;
                border-top: 1px solid #30363d;
            }
        """)
    
    def run(self) -> int:
        """Run the application"""
        self.window.show()
        return self.app.exec()


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Remote Webcam")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        
        # Components
        self._receiver = OpenCVReceiver()
        self._virtual_cam = VirtualCamera()
        self._adb = ADBBridge()
        self._frame_worker: Optional[FrameWorker] = None
        
        # State
        self._connected = False
        self._virtual_cam_enabled = False
        
        # Setup UI
        self._setup_ui()
        self._setup_tray()
        self._setup_timers()
        
        # Start ADB device monitoring
        self._adb.set_device_callback(self._on_devices_changed)
        self._adb.start_device_monitor()
        self._refresh_devices()
    
    def _setup_ui(self):
        """Setup the user interface"""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Preview area
        preview_group = QGroupBox("Camera Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self._preview_label = QLabel()
        self._preview_label.setObjectName("previewLabel")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(360)
        self._preview_label.setText("No stream connected")
        preview_layout.addWidget(self._preview_label)
        
        # Stats label
        self._stats_label = QLabel("FPS: -- | Frames: 0")
        self._stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._stats_label)
        
        layout.addWidget(preview_group)
        
        # Connection settings
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout(conn_group)
        
        # Wi-Fi connection row
        wifi_layout = QHBoxLayout()
        wifi_layout.addWidget(QLabel("Address:"))
        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText("192.168.1.100")
        wifi_layout.addWidget(self._host_input, 1)
        
        wifi_layout.addWidget(QLabel("Port:"))
        self._port_input = QLineEdit("8080")
        self._port_input.setMaximumWidth(80)
        wifi_layout.addWidget(self._port_input)
        
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._toggle_connection)
        wifi_layout.addWidget(self._connect_btn)
        
        conn_layout.addLayout(wifi_layout)
        
        # USB connection row
        usb_layout = QHBoxLayout()
        usb_layout.addWidget(QLabel("USB Device:"))
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(200)
        usb_layout.addWidget(self._device_combo, 1)
        
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("secondaryBtn")
        self._refresh_btn.clicked.connect(self._refresh_devices)
        usb_layout.addWidget(self._refresh_btn)
        
        self._usb_connect_btn = QPushButton("Connect via USB")
        self._usb_connect_btn.setObjectName("secondaryBtn")
        self._usb_connect_btn.clicked.connect(self._connect_usb)
        usb_layout.addWidget(self._usb_connect_btn)
        
        conn_layout.addLayout(usb_layout)
        
        layout.addWidget(conn_group)
        
        # Virtual camera settings
        vcam_group = QGroupBox("Virtual Camera")
        vcam_layout = QHBoxLayout(vcam_group)
        
        self._vcam_checkbox = QCheckBox("Enable Virtual Camera")
        self._vcam_checkbox.setEnabled(self._virtual_cam.is_available)
        self._vcam_checkbox.toggled.connect(self._toggle_virtual_cam)
        vcam_layout.addWidget(self._vcam_checkbox)
        
        self._vcam_status = QLabel()
        if self._virtual_cam.is_available:
            self._vcam_status.setText("Ready (OBS Virtual Camera)")
        else:
            self._vcam_status.setText("⚠️ pyvirtualcam not installed")
            self._vcam_status.setStyleSheet("color: #f0883e;")
        vcam_layout.addWidget(self._vcam_status, 1)
        
        layout.addWidget(vcam_group)
        
        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")
    
    def _setup_tray(self):
        """Setup system tray icon"""
        self._tray = QSystemTrayIcon(self)
        # Use a basic icon - in production you'd use a proper icon file
        self._tray.setToolTip("Remote Webcam")
        
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        tray_menu.addAction(quit_action)
        
        self._tray.setContextMenu(tray_menu)
    
    def _setup_timers(self):
        """Setup update timers"""
        # Stats update timer
        self._stats_timer = QTimer()
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start(500)  # Update every 500ms
    
    def _refresh_devices(self):
        """Refresh USB device list"""
        self._device_combo.clear()
        
        if not self._adb.is_available:
            self._device_combo.addItem("ADB not available")
            self._usb_connect_btn.setEnabled(False)
            return
        
        devices = self._adb.get_devices()
        if devices:
            for device in devices:
                label = f"{device.model or device.serial}"
                if device.product:
                    label += f" ({device.product})"
                self._device_combo.addItem(label, device.serial)
            self._usb_connect_btn.setEnabled(True)
        else:
            self._device_combo.addItem("No devices found")
            self._usb_connect_btn.setEnabled(False)
    
    def _on_devices_changed(self, devices: List[AndroidDevice]):
        """Called when USB device list changes"""
        self._refresh_devices()
    
    def _toggle_connection(self):
        """Toggle stream connection"""
        if self._connected:
            self._disconnect()
        else:
            self._connect_wifi()
    
    def _connect_wifi(self):
        """Connect via Wi-Fi"""
        host = self._host_input.text().strip()
        if not host:
            QMessageBox.warning(self, "Error", "Please enter the phone's IP address")
            return
        
        try:
            port = int(self._port_input.text())
        except ValueError:
            port = 8080
        
        self._connect_to_stream(host, port)
    
    def _connect_usb(self):
        """Connect via USB (ADB)"""
        device_serial = self._device_combo.currentData()
        if not device_serial:
            QMessageBox.warning(self, "Error", "No device selected")
            return
        
        # Start port forwarding
        if self._adb.start_port_forwarding(device_serial):
            self._status_bar.showMessage("USB port forwarding established")
            self._connect_to_stream("127.0.0.1", 8080)
        else:
            QMessageBox.warning(self, "Error", "Failed to establish USB connection")
    
    def _connect_to_stream(self, host: str, port: int):
        """Connect to the stream"""
        self._status_bar.showMessage(f"Connecting to {host}:{port}...")
        
        # Setup frame worker
        self._frame_worker = FrameWorker(self._receiver)
        self._frame_worker.frame_ready.connect(self._on_frame)
        self._frame_worker.status_changed.connect(self._on_status_changed)
        
        # Connect
        self._receiver.connect(host, port)
        
        self._connected = True
        self._connect_btn.setText("Disconnect")
        self._connect_btn.setObjectName("dangerBtn")
        self._connect_btn.setStyle(self._connect_btn.style())  # Force style refresh
    
    def _disconnect(self):
        """Disconnect from stream"""
        self._receiver.disconnect()
        self._adb.stop_all_forwarding()
        
        self._connected = False
        self._connect_btn.setText("Connect")
        self._connect_btn.setObjectName("")
        self._connect_btn.setStyle(self._connect_btn.style())
        
        self._preview_label.clear()
        self._preview_label.setText("No stream connected")
        self._status_bar.showMessage("Disconnected")
        
        # Disable virtual camera
        if self._virtual_cam_enabled:
            self._vcam_checkbox.setChecked(False)
    
    def _on_frame(self, frame: np.ndarray):
        """Handle new frame from receiver"""
        # Convert BGR to RGB for Qt
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        
        # Create QImage and display
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Scale to fit preview label while maintaining aspect ratio
        pixmap = QPixmap.fromImage(qt_image)
        scaled = pixmap.scaled(
            self._preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._preview_label.setPixmap(scaled)
        
        # Send to virtual camera if enabled
        if self._virtual_cam_enabled:
            self._virtual_cam.send_frame(frame)
    
    def _on_status_changed(self, status: str, message: str):
        """Handle status change from receiver"""
        if status == "connected":
            self._status_bar.showMessage("✓ Stream connected")
        elif status == "error":
            self._status_bar.showMessage(f"✗ {message}")
        elif status == "disconnected":
            self._status_bar.showMessage("Disconnected")
    
    def _update_stats(self):
        """Update stats display"""
        if self._connected:
            stats = self._receiver.stats
            self._stats_label.setText(
                f"FPS: {stats.fps:.1f} | Frames: {stats.frame_count} | "
                f"Data: {stats.bytes_received / 1024 / 1024:.1f} MB"
            )
    
    def _toggle_virtual_cam(self, enabled: bool):
        """Toggle virtual camera output"""
        if enabled:
            if self._virtual_cam.start():
                self._virtual_cam_enabled = True
                device = self._virtual_cam.get_device_name()
                self._vcam_status.setText(f"Active: {device}")
                self._vcam_status.setStyleSheet("color: #3fb950;")
            else:
                self._vcam_checkbox.setChecked(False)
                QMessageBox.warning(
                    self, "Error",
                    "Failed to start virtual camera.\n"
                    "Make sure OBS Virtual Camera is installed."
                )
        else:
            self._virtual_cam.stop()
            self._virtual_cam_enabled = False
            self._vcam_status.setText("Ready (OBS Virtual Camera)")
            self._vcam_status.setStyleSheet("")
    
    def _quit(self):
        """Quit the application"""
        self._disconnect()
        self._adb.stop_device_monitor()
        QApplication.quit()
    
    def closeEvent(self, event):
        """Handle window close"""
        self._quit()
        event.accept()
