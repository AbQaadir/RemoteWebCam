# Remote Webcam - Desktop Application

Windows desktop client that receives camera stream from your Android phone and makes it available as a virtual webcam.

## Features

- 📹 Receive MJPEG stream from Android app
- 🔌 Connect via Wi-Fi or USB (ADB)
- 📷 Virtual camera output for Zoom, Teams, OBS, etc.
- 🎨 Modern dark theme UI
- 📊 Real-time FPS and bandwidth stats
- 🔒 Local-only - no cloud required

## Requirements

- Windows 10/11
- Python 3.9+ (for development)
- [OBS Studio](https://obsproject.com/) (for virtual camera driver)
- ADB (optional, for USB connection)

## Quick Start

### Option 1: Run from Source

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

### Option 2: Build Executable

```bash
# Run the build script
build.bat
```

The EXE will be created in `dist/RemoteWebcam.exe`

## Usage

### Wi-Fi Connection
1. Connect your phone and PC to the same Wi-Fi network
2. Open the Android app and start streaming
3. Enter the IP address shown in the Android app
4. Click "Connect"

### USB Connection (Recommended)
1. Enable USB Debugging on your Android phone
2. Connect phone to PC via USB cable
3. The device will appear in the dropdown
4. Click "Connect via USB"

### Virtual Camera
1. Install OBS Studio (includes OBS Virtual Camera)
2. Connect to your phone's stream
3. Check "Enable Virtual Camera"
4. Select "OBS Virtual Camera" in Zoom/Teams settings

## Building the Installer

1. Install [Inno Setup](https://jrsoftware.org/isdownload.php)
2. Build the EXE first: `build.bat`
3. Open `installer.iss` in Inno Setup
4. Compile to create the installer

## Project Structure

```
desktop-app/
├── main.py              # Entry point
├── src/
│   ├── app.py           # Main PyQt6 application
│   ├── receiver.py      # MJPEG stream receiver
│   ├── virtual_cam.py   # Virtual camera output
│   └── adb_bridge.py    # ADB operations
├── requirements.txt     # Python dependencies
├── RemoteWebcam.spec    # PyInstaller config
├── installer.iss        # Inno Setup script
└── build.bat            # Build script
```
