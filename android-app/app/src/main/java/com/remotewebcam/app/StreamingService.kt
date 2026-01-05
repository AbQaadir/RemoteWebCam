package com.remotewebcam.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.os.Binder
import android.os.Build
import android.os.IBinder
import android.util.Log
import android.util.Size
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import java.io.ByteArrayOutputStream
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class StreamingService : Service(), LifecycleOwner {

    companion object {
        const val EXTRA_RESOLUTION = "resolution"
        const val EXTRA_USE_FRONT_CAMERA = "use_front_camera"
        private const val CHANNEL_ID = "streaming_channel"
        private const val NOTIFICATION_ID = 1
        private const val TAG = "StreamingService"
    }

    private val binder = LocalBinder()
    private lateinit var lifecycleRegistry: LifecycleRegistry
    private var cameraExecutor: ExecutorService? = null
    private var streamingServer: StreamingServer? = null
    private var cameraProvider: ProcessCameraProvider? = null
    
    private var useFrontCamera = false
    private var currentResolution = "1280x720"
    private var jpegQuality = 80

    inner class LocalBinder : Binder() {
        fun getService(): StreamingService = this@StreamingService
    }

    override fun onCreate() {
        super.onCreate()
        lifecycleRegistry = LifecycleRegistry(this)
        lifecycleRegistry.currentState = Lifecycle.State.CREATED
        cameraExecutor = Executors.newSingleThreadExecutor()
        
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        currentResolution = intent?.getStringExtra(EXTRA_RESOLUTION) ?: "1280x720"
        useFrontCamera = intent?.getBooleanExtra(EXTRA_USE_FRONT_CAMERA, false) ?: false
        
        startForegroundNotification()
        startStreaming()
        
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder = binder
    
    override val lifecycle: Lifecycle
        get() = lifecycleRegistry

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Camera Streaming",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows when camera is streaming"
            }
            
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun startForegroundNotification() {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Remote Webcam")
            .setContentText("Streaming camera to PC...")
            .setSmallIcon(R.drawable.ic_camera)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun startStreaming() {
        lifecycleRegistry.currentState = Lifecycle.State.STARTED
        
        // Start HTTP server
        streamingServer = StreamingServer().also {
            it.start()
            Log.i(TAG, "Streaming server started on port ${StreamingServer.DEFAULT_PORT}")
        }
        
        // Start camera capture
        startCameraCapture()
    }

    private fun startCameraCapture() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        
        cameraProviderFuture.addListener({
            cameraProvider = cameraProviderFuture.get()
            
            val resolution = parseResolution(currentResolution)
            
            val imageAnalysis = ImageAnalysis.Builder()
                .setTargetResolution(resolution)
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
            
            imageAnalysis.setAnalyzer(cameraExecutor!!) { imageProxy ->
                processFrame(imageProxy)
            }
            
            val cameraSelector = if (useFrontCamera) {
                CameraSelector.DEFAULT_FRONT_CAMERA
            } else {
                CameraSelector.DEFAULT_BACK_CAMERA
            }
            
            try {
                cameraProvider?.unbindAll()
                cameraProvider?.bindToLifecycle(
                    this,
                    cameraSelector,
                    imageAnalysis
                )
                lifecycleRegistry.currentState = Lifecycle.State.RESUMED
            } catch (e: Exception) {
                Log.e(TAG, "Failed to bind camera: ${e.message}")
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun processFrame(imageProxy: ImageProxy) {
        try {
            val jpeg = imageProxyToJpeg(imageProxy)
            if (jpeg != null) {
                streamingServer?.updateFrame(jpeg)
            }
        } finally {
            imageProxy.close()
        }
    }

    private fun imageProxyToJpeg(imageProxy: ImageProxy): ByteArray? {
        return try {
            val yBuffer = imageProxy.planes[0].buffer
            val uBuffer = imageProxy.planes[1].buffer
            val vBuffer = imageProxy.planes[2].buffer

            val ySize = yBuffer.remaining()
            val uSize = uBuffer.remaining()
            val vSize = vBuffer.remaining()

            val nv21 = ByteArray(ySize + uSize + vSize)

            yBuffer.get(nv21, 0, ySize)
            vBuffer.get(nv21, ySize, vSize)
            uBuffer.get(nv21, ySize + vSize, uSize)

            val yuvImage = YuvImage(
                nv21,
                ImageFormat.NV21,
                imageProxy.width,
                imageProxy.height,
                null
            )

            val outputStream = ByteArrayOutputStream()
            yuvImage.compressToJpeg(
                Rect(0, 0, imageProxy.width, imageProxy.height),
                jpegQuality,
                outputStream
            )
            
            outputStream.toByteArray()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to convert frame to JPEG: ${e.message}")
            null
        }
    }

    private fun parseResolution(resolution: String): Size {
        val parts = resolution.split("x")
        return if (parts.size == 2) {
            Size(parts[0].toInt(), parts[1].toInt())
        } else {
            Size(1280, 720)
        }
    }

    fun updateResolution(resolution: String) {
        currentResolution = resolution
        cameraProvider?.unbindAll()
        startCameraCapture()
    }

    fun switchCamera(useFront: Boolean) {
        useFrontCamera = useFront
        cameraProvider?.unbindAll()
        startCameraCapture()
    }

    fun setJpegQuality(quality: Int) {
        jpegQuality = quality.coerceIn(10, 100)
    }

    override fun onDestroy() {
        super.onDestroy()
        lifecycleRegistry.currentState = Lifecycle.State.DESTROYED
        streamingServer?.stop()
        cameraProvider?.unbindAll()
        cameraExecutor?.shutdown()
    }
}
