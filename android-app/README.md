# Remote Webcam - Android App

Privacy-focused phone camera streaming app that turns your Android phone into a webcam.

## Features

- 📹 High-quality camera streaming via MJPEG
- 🔄 Front/Back camera switching
- 📐 Multiple resolution options (480p, 720p, 1080p)
- 🌐 Wi-Fi streaming to any device on your network
- 🔒 No cloud - data stays on your local network
- 📱 Background streaming with foreground service

## Building

### Requirements
- Android Studio Arctic Fox or later
- JDK 17
- Android SDK 34

### Steps

1. Open the project in Android Studio
2. Sync Gradle files
3. Run on your device or build APK:
   ```bash
   ./gradlew assembleDebug
   ```

## Usage

1. Connect your phone and PC to the same Wi-Fi network
2. Open the app and grant camera permission
3. Tap "Start Streaming"
4. Note the displayed URL (e.g., http://192.168.1.100:8080)
5. On your PC, open the URL in a browser or use the desktop app

## Stream Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Web page with embedded stream |
| `/video` | Raw MJPEG stream |
| `/snapshot` | Single JPEG frame |
| `/status` | JSON status info |
