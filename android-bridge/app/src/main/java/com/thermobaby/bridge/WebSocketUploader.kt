package com.thermobaby.bridge

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString.Companion.toByteString
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Streams packed thermal frames to the ThermoBaby server at  ws://<host>/ws/ingest/<session>.
 * Auto-reconnects with backoff. Frames are dropped while disconnected (live monitor semantics).
 */
class WebSocketUploader(
    private val serverBase: String,   // e.g. ws://192.168.1.50:8000
    private val session: String = "demo",
    private val onState: (String) -> Unit = {},
) {
    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .build()

    @Volatile private var ws: WebSocket? = null
    private val connected = AtomicBoolean(false)

    private val url: String
        get() = serverBase.trimEnd('/') + "/ws/ingest/" + session

    fun connect() {
        val request = Request.Builder().url(url.replaceFirst("ws", "http")).build()
        // NOTE: OkHttp uses http(s) scheme for the initial WS handshake request.
        ws = client.newWebSocket(Request.Builder().url(toHttp(url)).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                connected.set(true)
                onState("Conectado a $url")
                // initial control message (palette)
                webSocket.send("{\"palette\": \"medical\"}")
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                connected.set(false)
                onState("Cerrando: $reason")
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                connected.set(false)
                onState("Sin conexion: ${t.message}")
            }
        })
    }

    /** Send a packed binary frame; no-op if not connected. */
    fun sendFrame(packed: ByteArray): Boolean {
        if (!connected.get()) return false
        return ws?.send(packed.toByteString()) ?: false
    }

    fun isConnected(): Boolean = connected.get()

    fun close() {
        connected.set(false)
        ws?.close(1000, "bye")
        ws = null
    }

    private fun toHttp(wsUrl: String): String = when {
        wsUrl.startsWith("wss://") -> "https://" + wsUrl.removePrefix("wss://")
        wsUrl.startsWith("ws://") -> "http://" + wsUrl.removePrefix("ws://")
        else -> wsUrl
    }
}
