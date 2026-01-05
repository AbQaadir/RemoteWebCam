"""
Remote Webcam - Desktop Application
Main entry point for the Windows desktop client
"""

import sys
import os

# Add the src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import RemoteWebcamApp


def main():
    """Main entry point"""
    app = RemoteWebcamApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
