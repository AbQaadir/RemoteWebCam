package com.remotewebcam.app

import android.util.Log
import fi.iki.elonen.NanoHTTPD
import java.io.ByteArrayInputStream
import java.io.PipedInputStream
import java.io.PipedOutputStream

/**
 * Lightweight HTTP server that serves MJPEG stream
 * 
 * Endpoints:
 * - / : Simple HTML page with embedded video
 * - /video : Raw MJPEG stream for direct consumption
 * - /snapshot : Single JPEG frame
 */
class StreamingServer(port: Int = DEFAULT_PORT) : NanoHTTPD(port) {

    companion object {
        const val DEFAULT_PORT = 8080
        private const val TAG = "StreamingServer"
        private const val BOUNDARY = "frame"
    }

    @Volatile
    private var currentFrame: ByteArray? = null
    private val frameListeners = mutableListOf<FrameListener>()
    private val lock = Object()

    interface FrameListener {
        fun onFrame(jpeg: ByteArray)
    }

    override fun serve(session: IHTTPSession): Response {
        val uri = session.uri
        
        return when {
            uri == "/" -> serveHomePage()
            uri == "/video" || uri == "/stream" -> serveMjpegStream(session)
            uri == "/snapshot" || uri == "/frame" -> serveSnapshot()
            uri == "/status" -> serveStatus()
            else -> newFixedLengthResponse(Response.Status.NOT_FOUND, "text/plain", "Not Found")
        }
    }

    private fun serveHomePage(): Response {
        val html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Remote Webcam</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    * { margin: 0; padding: 0; box-sizing: border-box; }
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                        min-height: 100vh;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        color: #fff;
                        padding: 20px;
                    }
                    h1 {
                        font-size: 2rem;
                        margin-bottom: 20px;
                        background: linear-gradient(90deg, #00d4ff, #7b2cbf);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                    }
                    .container {
                        background: rgba(255, 255, 255, 0.05);
                        border-radius: 20px;
                        padding: 20px;
                        backdrop-filter: blur(10px);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3);
                    }
                    img {
                        max-width: 100%;
                        border-radius: 12px;
                        display: block;
                    }
                    .status {
                        margin-top: 15px;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        font-size: 0.9rem;
                        color: #4ade80;
                    }
                    .dot {
                        width: 10px;
                        height: 10px;
                        background: #4ade80;
                        border-radius: 50%;
                        animation: pulse 2s infinite;
                    }
                    @keyframes pulse {
                        0%, 100% { opacity: 1; }
                        50% { opacity: 0.5; }
                    }
                    .info {
                        margin-top: 20px;
                        font-size: 0.8rem;
                        color: rgba(255, 255, 255, 0.6);
                        text-align: center;
                    }
                </style>
            </head>
            <body>
                <h1>📹 Remote Webcam</h1>
                <div class="container">
                    <img src="/video" alt="Camera Stream">
                    <div class="status">
                        <span class="dot"></span>
                        <span>Live Stream</span>
                    </div>
                </div>
                <p class="info">Stream is running. Use this feed in your desktop app or browser.</p>
            </body>
            </html>
        """.trimIndent()
        
        return newFixedLengthResponse(Response.Status.OK, "text/html", html)
    }

    private fun serveMjpegStream(session: IHTTPSession): Response {
        val pipedOutput = PipedOutputStream()
        val pipedInput = PipedInputStream(pipedOutput, 1024 * 1024) // 1MB buffer
        
        val listener = object : FrameListener {
            override fun onFrame(jpeg: ByteArray) {
                try {
                    val header = "--$BOUNDARY\r\n" +
                            "Content-Type: image/jpeg\r\n" +
                            "Content-Length: ${jpeg.size}\r\n\r\n"
                    
                    pipedOutput.write(header.toByteArray())
                    pipedOutput.write(jpeg)
                    pipedOutput.write("\r\n".toByteArray())
                    pipedOutput.flush()
                } catch (e: Exception) {
                    Log.d(TAG, "Client disconnected")
                    removeFrameListener(this)
                    try { pipedOutput.close() } catch (_: Exception) {}
                }
            }
        }
        
        addFrameListener(listener)
        
        val response = newChunkedResponse(
            Response.Status.OK,
            "multipart/x-mixed-replace; boundary=$BOUNDARY",
            pipedInput
        )
        
        response.addHeader("Cache-Control", "no-cache, no-store, must-revalidate")
        response.addHeader("Pragma", "no-cache")
        response.addHeader("Expires", "0")
        response.addHeader("Connection", "close")
        
        return response
    }

    private fun serveSnapshot(): Response {
        val frame = currentFrame
        return if (frame != null) {
            newFixedLengthResponse(
                Response.Status.OK,
                "image/jpeg",
                ByteArrayInputStream(frame),
                frame.size.toLong()
            )
        } else {
            newFixedLengthResponse(Response.Status.SERVICE_UNAVAILABLE, "text/plain", "No frame available")
        }
    }

    private fun serveStatus(): Response {
        val json = """{"status": "running", "port": $DEFAULT_PORT, "hasFrame": ${currentFrame != null}}"""
        return newFixedLengthResponse(Response.Status.OK, "application/json", json)
    }

    fun updateFrame(jpeg: ByteArray) {
        currentFrame = jpeg
        
        synchronized(lock) {
            frameListeners.toList().forEach { listener ->
                try {
                    listener.onFrame(jpeg)
                } catch (e: Exception) {
                    frameListeners.remove(listener)
                }
            }
        }
    }

    private fun addFrameListener(listener: FrameListener) {
        synchronized(lock) {
            frameListeners.add(listener)
        }
    }

    private fun removeFrameListener(listener: FrameListener) {
        synchronized(lock) {
            frameListeners.remove(listener)
        }
    }

    override fun stop() {
        synchronized(lock) {
            frameListeners.clear()
        }
        super.stop()
    }
}
