package com.remotewebcam.app

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.Collections

/**
 * Utility class for network operations
 */
object NetworkUtils {

    /**
     * Get the local IP address of the device on Wi-Fi
     */
    fun getLocalIpAddress(context: Context): String? {
        // Try using WifiManager first (most reliable for Wi-Fi)
        try {
            val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val wifiInfo = wifiManager.connectionInfo
            val ipInt = wifiInfo.ipAddress
            
            if (ipInt != 0) {
                return String.format(
                    "%d.%d.%d.%d",
                    ipInt and 0xff,
                    ipInt shr 8 and 0xff,
                    ipInt shr 16 and 0xff,
                    ipInt shr 24 and 0xff
                )
            }
        } catch (e: Exception) {
            // Fall through to alternative method
        }
        
        // Fallback: enumerate network interfaces
        return getIpFromNetworkInterfaces()
    }

    private fun getIpFromNetworkInterfaces(): String? {
        try {
            val interfaces = Collections.list(NetworkInterface.getNetworkInterfaces())
            for (networkInterface in interfaces) {
                // Skip loopback and inactive interfaces
                if (networkInterface.isLoopback || !networkInterface.isUp) continue
                
                // Prefer Wi-Fi interfaces
                val name = networkInterface.name.lowercase()
                if (!name.startsWith("wlan") && !name.startsWith("eth") && !name.startsWith("en")) {
                    continue
                }
                
                val addresses = Collections.list(networkInterface.inetAddresses)
                for (address in addresses) {
                    if (!address.isLoopbackAddress && address is Inet4Address) {
                        return address.hostAddress
                    }
                }
            }
        } catch (e: Exception) {
            // Return null if we can't get the IP
        }
        return null
    }

    /**
     * Check if the device is connected to Wi-Fi
     */
    fun isWifiConnected(context: Context): Boolean {
        val connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        
        return capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
    }

    /**
     * Get the SSID of the connected Wi-Fi network
     */
    fun getWifiSsid(context: Context): String? {
        try {
            val wifiManager = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val wifiInfo = wifiManager.connectionInfo
            val ssid = wifiInfo.ssid
            
            // Remove quotes if present
            return ssid?.replace("\"", "")?.takeIf { it != "<unknown ssid>" }
        } catch (e: Exception) {
            return null
        }
    }
}
