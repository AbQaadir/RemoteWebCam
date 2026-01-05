package com.remotewebcam.app

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.view.View
import android.view.WindowManager
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.remotewebcam.app.databinding.ActivityMainBinding
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var cameraExecutor: ExecutorService
    
    private var streamingService: StreamingService? = null
    private var isServiceBound = false
    private var isStreaming = false
    private var currentCameraSelector = CameraSelector.DEFAULT_BACK_CAMERA
    
    private val resolutions = arrayOf("480p", "720p", "1080p")
    private val resolutionValues = arrayOf("640x480", "1280x720", "1920x1080")
    private var selectedResolution = "1280x720"
    
    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as StreamingService.LocalBinder
            streamingService = binder.getService()
            isServiceBound = true
        }
        
        override fun onServiceDisconnected(name: ComponentName?) {
            streamingService = null
            isServiceBound = false
        }
    }
    
    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val allGranted = permissions.entries.all { it.value }
        if (allGranted) {
            startCamera()
        } else {
            Toast.makeText(this, "Camera permission is required", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Enable edge-to-edge display
        WindowCompat.setDecorFitsSystemWindows(window, false)
        
        // Keep screen on while app is open
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        
        // Hide system bars for immersive camera experience
        hideSystemBars()
        
        cameraExecutor = Executors.newSingleThreadExecutor()
        
        setupUI()
        requestPermissions()
    }
    
    private fun hideSystemBars() {
        val windowInsetsController = WindowCompat.getInsetsController(window, window.decorView)
        windowInsetsController.systemBarsBehavior = 
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        windowInsetsController.hide(WindowInsetsCompat.Type.systemBars())
    }
    
    private fun setupUI() {
        // Resolution spinner
        val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_item, resolutions)
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        binding.spinnerResolution.adapter = adapter
        binding.spinnerResolution.setSelection(1) // Default 720p
        
        binding.spinnerResolution.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                selectedResolution = resolutionValues[position]
                if (isStreaming) {
                    streamingService?.updateResolution(selectedResolution)
                }
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
        
        // Camera switch FAB
        binding.btnSwitchCamera.setOnClickListener {
            currentCameraSelector = if (currentCameraSelector == CameraSelector.DEFAULT_BACK_CAMERA) {
                CameraSelector.DEFAULT_FRONT_CAMERA
            } else {
                CameraSelector.DEFAULT_BACK_CAMERA
            }
            startCamera()
            if (isStreaming) {
                streamingService?.switchCamera(currentCameraSelector == CameraSelector.DEFAULT_FRONT_CAMERA)
            }
        }
        
        // Start/Stop streaming FAB
        binding.btnStartStop.setOnClickListener {
            if (isStreaming) {
                stopStreaming()
            } else {
                startStreaming()
            }
        }
        
        // Status text click to toggle IP card visibility
        binding.tvStatus.setOnClickListener {
            toggleIpCardVisibility()
        }
        
        // Also allow clicking the card to hide it
        binding.cardIpAddress.setOnClickListener {
            toggleIpCardVisibility()
        }
        
        // Display IP address
        updateIpAddress()
    }
    
    private var isIpCardVisible = false
    
    private fun toggleIpCardVisibility() {
        isIpCardVisible = !isIpCardVisible
        if (isIpCardVisible) {
            binding.cardIpAddress.visibility = View.VISIBLE
            binding.cardIpAddress.alpha = 0f
            binding.cardIpAddress.animate().alpha(1f).setDuration(200).start()
        } else {
            binding.cardIpAddress.animate().alpha(0f).setDuration(200).withEndAction {
                binding.cardIpAddress.visibility = View.GONE
            }.start()
        }
        updateStatusText()
    }
    
    private fun updateStatusText() {
        val arrow = if (isIpCardVisible) "▲" else "▼"
        if (isStreaming) {
            binding.tvStatus.text = "● LIVE $arrow"
        } else {
            binding.tvStatus.text = "● OFFLINE $arrow"
        }
    }
    
    private fun updateIpAddress() {
        val ipAddress = NetworkUtils.getLocalIpAddress(this)
        val port = StreamingServer.DEFAULT_PORT
        if (ipAddress != null) {
            binding.tvIpAddress.text = "http://$ipAddress:$port"
            binding.tvConnectionInfo.text = "Connect your PC"
        } else {
            binding.tvIpAddress.text = "No Wi-Fi"
            binding.tvConnectionInfo.text = "Connect to Wi-Fi"
        }
    }
    
    private fun requestPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.CAMERA
        )
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        
        val permissionsToRequest = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        
        if (permissionsToRequest.isEmpty()) {
            startCamera()
        } else {
            permissionLauncher.launch(permissionsToRequest.toTypedArray())
        }
    }
    
    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()
            
            val preview = Preview.Builder()
                .build()
                .also {
                    it.setSurfaceProvider(binding.previewView.surfaceProvider)
                }
            
            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    this,
                    currentCameraSelector,
                    preview
                )
            } catch (e: Exception) {
                Toast.makeText(this, "Failed to start camera: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }, ContextCompat.getMainExecutor(this))
    }
    
    private fun startStreaming() {
        val intent = Intent(this, StreamingService::class.java).apply {
            putExtra(StreamingService.EXTRA_RESOLUTION, selectedResolution)
            putExtra(StreamingService.EXTRA_USE_FRONT_CAMERA, 
                currentCameraSelector == CameraSelector.DEFAULT_FRONT_CAMERA)
        }
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        
        bindService(intent, serviceConnection, Context.BIND_AUTO_CREATE)
        
        isStreaming = true
        updateStreamingUI()
        Toast.makeText(this, "Streaming started", Toast.LENGTH_SHORT).show()
    }
    
    private fun stopStreaming() {
        if (isServiceBound) {
            unbindService(serviceConnection)
            isServiceBound = false
        }
        
        stopService(Intent(this, StreamingService::class.java))
        streamingService = null
        
        isStreaming = false
        updateStreamingUI()
        Toast.makeText(this, "Streaming stopped", Toast.LENGTH_SHORT).show()
    }
    
    private fun updateStreamingUI() {
        if (isStreaming) {
            // Change to stop button
            binding.btnStartStop.setImageResource(R.drawable.ic_stop)
            binding.btnStartStop.backgroundTintList = ContextCompat.getColorStateList(this, R.color.stop_red)
            binding.tvStatus.setTextColor(getColor(R.color.live_green))
            binding.tvHint.text = "Tap to stop streaming"
            // Auto-show IP card when streaming starts
            if (!isIpCardVisible) {
                toggleIpCardVisibility()
            }
        } else {
            // Change to record button
            binding.btnStartStop.setImageResource(R.drawable.ic_record)
            binding.btnStartStop.backgroundTintList = ContextCompat.getColorStateList(this, R.color.accent_secondary)
            binding.tvStatus.setTextColor(getColor(R.color.offline_gray))
            binding.tvHint.text = "Tap to start streaming"
        }
        updateStatusText()
    }
    
    override fun onResume() {
        super.onResume()
        hideSystemBars()
        updateIpAddress()
    }
    
    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdown()
        if (isServiceBound) {
            unbindService(serviceConnection)
        }
    }
}
