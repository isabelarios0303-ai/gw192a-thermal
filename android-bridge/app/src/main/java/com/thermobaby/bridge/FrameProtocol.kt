package com.thermobaby.bridge

import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Binary frame protocol for /ws/ingest — must match backend/app/api/ws.py and the desktop
 * gateway (gateway/gw192a_gateway.py).
 *
 * Layout (little-endian):
 *   magic[4]="GW19" | version u8 | kind u8 | width u16 | height u16 | seq u32 | ts_ms u64 | payload
 *   kind: 1 = radiometric_u16, 2 = celsius_f32
 */
object FrameProtocol {
    private val MAGIC = byteArrayOf('G'.code.toByte(), 'W'.code.toByte(), '1'.code.toByte(), '9'.code.toByte())
    private const val VERSION: Int = 1
    const val KIND_RADIOMETRIC_U16 = 1
    const val KIND_CELSIUS_F32 = 2
    private const val HEADER_SIZE = 22

    /** Pack a Celsius matrix (row-major, width*height) as a KIND_CELSIUS_F32 frame. */
    fun packCelsius(celsius: FloatArray, width: Int, height: Int, seq: Int): ByteArray {
        val buf = ByteBuffer.allocate(HEADER_SIZE + celsius.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        writeHeader(buf, KIND_CELSIUS_F32, width, height, seq)
        for (v in celsius) buf.putFloat(v)
        return buf.array()
    }

    /** Pack raw uint16 radiometric counts as a KIND_RADIOMETRIC_U16 frame. */
    fun packRadiometric(rawU16: IntArray, width: Int, height: Int, seq: Int): ByteArray {
        val buf = ByteBuffer.allocate(HEADER_SIZE + rawU16.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        writeHeader(buf, KIND_RADIOMETRIC_U16, width, height, seq)
        for (v in rawU16) buf.putShort((v and 0xFFFF).toShort())
        return buf.array()
    }

    private fun writeHeader(buf: ByteBuffer, kind: Int, width: Int, height: Int, seq: Int) {
        buf.put(MAGIC)
        buf.put(VERSION.toByte())
        buf.put(kind.toByte())
        buf.putShort(width.toShort())
        buf.putShort(height.toShort())
        buf.putInt(seq)
        buf.putLong(System.currentTimeMillis())
    }
}
