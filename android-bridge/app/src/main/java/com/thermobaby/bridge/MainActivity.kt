package com.thermobaby.bridge

import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.thermobaby.bridge.databinding.ActivityMainBinding
import java.util.concurrent.atomic.AtomicInteger

/**
 * ThermoBaby Android Bridge — main screen.
 *
 * Responsibilities:
 *  - request USB permission for the attached GW192A (UVC) device,
 *  - open the RAW UVC stream via AndroidUSBCamera (libausbc) and receive raw frame callbacks,
 *  - decode the radiometric half to Celsius (ThermalDecoder), show live stats locally,
 *  - optionally forward frames to the ThermoBaby server (WebSocketUploader, "bridge mode").
 *
 * INTEGRATION NOTE (marked // AJUSTAR):
 *  The exact libausbc API for attaching a raw-frame callback varies slightly across versions
 *  (e.g. MultiCameraClient / CameraUVC + addRawDataCallBack/addFrameCallback). The thermal math,
 *  protocol, and networking below are complete and validated; wire the callback to `onRawFrame`
 *  and adjust the geometry (width/height) once for the specific unit, exactly like we calibrated
 *  the desktop gateway. See README.md.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    // GW192A geometry (single half). The double-height frame is W x (H*2). AJUSTAR per unit.
    private val decoder = ThermalDecoder(width = 192, height = 192)
    private var uploader: WebSocketUploader? = null
    private val seq = AtomicInteger(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.serverUrl.setText("ws://192.168.1.50:8000")

        binding.connectBtn.setOnClickListener { toggleBridge() }
        binding.startCameraBtn.setOnClickListener { startCamera() }

        binding.status.text = getString(R.string.status_idle)
    }

    private fun startCamera() {
        // AJUSTAR: open the UVC device with AndroidUSBCamera here.
        //
        // Typical flow with libausbc:
        //   1) Request USB permission for the attached UVC device (the OS shows a dialog).
        //   2) Open it choosing the RAW format (do NOT let it convert to RGB) at the
        //      double-height resolution (e.g. 192 x 384). This is the key step that preserves
        //      the radiometric half — the same thing we force on desktop with CONVERT_RGB=0.
        //   3) Register a raw-frame callback and forward each frame to onRawFrame(bytes).
        //
        // Pseudocode (adapt to the libausbc version pinned in build.gradle.kts):
        //
        //   cameraClient = MultiCameraClient(this, deviceConnectCallback)
        //   camera = CameraUVC(this, usbDevice)
        //   camera.setUsbControlBlock(ctrlBlock)
        //   camera.openCamera(surfaceOrNull, cameraRequest)   // request YUYV @ 192x384
        //   camera.addRawDataCallBack(object : IFrameCallback {
        //       override fun onFrame(frame: ByteArray) { onRawFrame(frame) }
        //   })
        //
        binding.status.text = getString(R.string.status_camera_hint)
        Toast.makeText(this, R.string.status_camera_hint, Toast.LENGTH_LONG).show()
    }

    /**
     * Called for every raw UVC frame. Decodes temperature, updates the local readout, and (if the
     * bridge is connected) forwards the frame to the ThermoBaby server.
     */
    fun onRawFrame(frame: ByteArray) {
        val celsius = decoder.decode(frame)
        val stats = decoder.computeStats(celsius)

        runOnUiThread {
            binding.readout.text = getString(
                R.string.readout_fmt,
                stats.tMax, stats.tMin, stats.tMean
            )
            binding.alert.text = bodyAlert(stats.tMax)
        }

        uploader?.let { up ->
            if (up.isConnected()) {
                val packed = FrameProtocol.packCelsius(celsius, decoder.width, decoder.height,
                    seq.getAndIncrement())
                up.sendFrame(packed)
            }
        }
    }

    private fun bodyAlert(peak: Float): String = when {
        peak >= 38f -> getString(R.string.alert_crit_high)
        peak < 36f -> getString(R.string.alert_crit_low)
        peak > 37.5f -> getString(R.string.alert_warn_high)
        peak < 36.5f -> getString(R.string.alert_warn_low)
        else -> getString(R.string.alert_ok)
    }

    private fun toggleBridge() {
        if (uploader?.isConnected() == true) {
            uploader?.close()
            uploader = null
            binding.connectBtn.setText(R.string.connect)
            binding.status.text = getString(R.string.status_idle)
            return
        }
        val base = binding.serverUrl.text?.toString()?.trim().orEmpty()
        if (base.isEmpty()) {
            Toast.makeText(this, R.string.err_no_url, Toast.LENGTH_SHORT).show()
            return
        }
        uploader = WebSocketUploader(base, session = "demo") { state ->
            runOnUiThread { binding.status.text = state }
        }.also { it.connect() }
        binding.connectBtn.setText(R.string.disconnect)
    }

    override fun onDestroy() {
        uploader?.close()
        super.onDestroy()
    }
}
