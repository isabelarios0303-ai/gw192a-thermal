package com.thermobaby.bridge

/**
 * GW192A radiometric decoder for Android — mirrors backend/app/thermal/decoder.py and the
 * validated logic in validate/validate_core.py.
 *
 * The GW192A (InfiRay/Xtherm-class UVC camera) delivers a DOUBLE-HEIGHT YUYV frame: the top half
 * is the visible/colorized image, the bottom half is 16-bit little-endian radiometric data.
 *
 *     T(degC) = raw16 / KELVIN_SCALE - KELVIN_OFFSET, then linear trim (gain/offset)
 *
 * Unlike a desktop browser, an Android native app (via libuvc/libausbc) can request the RAW
 * YUYV bytes, so the radiometric half survives and real temperature can be recovered.
 */
class ThermalDecoder(
    var width: Int = 192,
    var height: Int = 192,
    var kelvinScale: Float = 64f,
    var kelvinOffset: Float = 273.15f,
    var gain: Float = 1f,
    var offset: Float = 0f,
) {

    data class Stats(
        val tMin: Float,
        val tMax: Float,
        val tMean: Float,
        val hotX: Int,
        val hotY: Int,
        val coldX: Int,
        val coldY: Int,
    )

    fun rawToCelsius(raw: Int): Float =
        (raw.toFloat() / kelvinScale - kelvinOffset) * gain + offset

    /**
     * Decode the radiometric half from a raw frame buffer.
     *
     * @param frame raw bytes from the UVC callback (YUYV). May be the full double-height frame
     *              (2*W*H uint16) or just the radiometric half (W*H uint16).
     * @return Celsius matrix as a FloatArray of size width*height (row-major).
     */
    fun decode(frame: ByteArray): FloatArray {
        val total = width * height
        val u16Count = frame.size / 2
        // If the buffer holds the full double-height frame, the radiometric half is the bottom.
        val startU16 = if (u16Count >= 2 * total) total else 0
        val out = FloatArray(total)
        var bi = startU16 * 2 // byte index (little-endian uint16)
        for (i in 0 until total) {
            if (bi + 1 >= frame.size) break
            val lo = frame[bi].toInt() and 0xFF
            val hi = frame[bi + 1].toInt() and 0xFF
            val raw = (hi shl 8) or lo
            out[i] = rawToCelsius(raw)
            bi += 2
        }
        return out
    }

    fun computeStats(celsius: FloatArray): Stats {
        var tMin = Float.MAX_VALUE
        var tMax = -Float.MAX_VALUE
        var sum = 0f
        var hot = 0
        var cold = 0
        for (i in celsius.indices) {
            val v = celsius[i]
            sum += v
            if (v > tMax) { tMax = v; hot = i }
            if (v < tMin) { tMin = v; cold = i }
        }
        val mean = if (celsius.isNotEmpty()) sum / celsius.size else 0f
        return Stats(
            tMin = tMin,
            tMax = tMax,
            tMean = mean,
            hotX = hot % width,
            hotY = hot / width,
            coldX = cold % width,
            coldY = cold / width,
        )
    }

    /** Convert raw uint16 counts back (for sending KIND_RADIOMETRIC_U16). */
    fun celsiusToRaw(celsius: Float): Int {
        val base = (celsius - offset) / gain
        val raw = ((base + kelvinOffset) * kelvinScale).toInt()
        return raw.coerceIn(0, 0xFFFF)
    }
}
