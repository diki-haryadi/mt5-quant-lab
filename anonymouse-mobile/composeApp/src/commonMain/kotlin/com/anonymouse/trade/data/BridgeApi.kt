package com.anonymouse.trade.data

import io.ktor.client.HttpClient
import io.ktor.client.request.delete
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.prepareGet
import io.ktor.client.request.setBody
import io.ktor.client.statement.bodyAsText
import io.ktor.client.statement.bodyAsChannel
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.utils.io.readUTF8Line
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull

/** event stream dari /v1/chat/stream (SSE). */
sealed interface BridgeEvent {
    data class Ready(val sessionId: String, val role: String) : BridgeEvent
    data class TextDelta(val delta: String) : BridgeEvent
    data class ToolUse(val name: String, val input: String) : BridgeEvent
    data class ToolResult(val summary: String) : BridgeEvent
    data class Artifact(val type: String, val url: String, val name: String) : BridgeEvent
    data class Done(val result: String) : BridgeEvent
    data class Err(val msg: String) : BridgeEvent
}

data class ChatStart(val jobId: String, val sessionId: String)

/** Klien bridge — base mis. http://ct108-tailscale:8090, token device. */
class BridgeApi(
    private val baseUrl: String,
    private val token: String,
    private val client: HttpClient = createHttpClient(),
) {
    private val json = Json { ignoreUnknownKeys = true }
    private fun url(path: String) = baseUrl.trimEnd('/') + path

    private fun io.ktor.client.request.HttpRequestBuilder.auth() {
        header("Authorization", "Bearer $token")
        contentType(ContentType.Application.Json)
    }

    suspend fun health(): String = client.get(url("/v1/health")) { auth() }.bodyAsText()

    suspend fun createSession(title: String): String {
        val r = client.post(url("/v1/sessions")) { auth(); setBody("{\"title\":\"$title\"}") }.bodyAsText()
        return json.parseToJsonElement(r).str("session_id")
    }

    suspend fun setRole(sessionId: String, role: String) =
        client.post(url("/v1/role")) { auth(); setBody("{\"session_id\":\"$sessionId\",\"role\":\"$role\"}") }.bodyAsText()

    suspend fun confirm(sessionId: String) =
        client.post(url("/v1/confirm")) { auth(); setBody("{\"session_id\":\"$sessionId\"}") }.bodyAsText()

    suspend fun deleteSession(sessionId: String) =
        client.delete(url("/v1/sessions/$sessionId")) { auth() }.bodyAsText()

    suspend fun registerPush(fcmToken: String) =
        client.post(url("/v1/push/register")) { auth(); setBody("{\"fcm_token\":\"${fcmToken.jsonEscape()}\"}") }.bodyAsText()

    /** ambil snapshot precomputed (instan, tanpa Claude). name: home|signals|forward_forex|forward_idx. */
    suspend fun getCache(name: String): String =
        client.get(url("/v1/cache/$name")) { auth() }.bodyAsText()

    /** PnL forex REAL-TIME langsung dari MT5 (untuk polling tiap beberapa detik). */
    suspend fun getLiveForex(): String =
        client.get(url("/v1/live/forex")) { auth() }.bodyAsText()

    /** daftar strategi + pair (server-driven). */
    suspend fun getMeta(): String = client.get(url("/v1/meta")) { auth() }.bodyAsText()

    /** riwayat backtest dari RAG. */
    suspend fun getRuns(limit: Int = 30): String = client.get(url("/v1/runs?limit=$limit")) { auth() }.bodyAsText()

    /** snapshot paper-trade crypto momentum (futures) — instan, tanpa Claude. */
    suspend fun getCrypto(): String = client.get(url("/v1/crypto")) { auth() }.bodyAsText()

    /** backtest CEPAT via engine langsung (detik). */
    suspend fun getBacktest(strategy: String, pair: String, capital: Int, risk: Float, period: Int, tf: String = "M15"): String =
        client.get(url("/v1/backtest?strategy=$strategy&pair=$pair&capital=$capital&risk=$risk&period=$period&tf=$tf")) { auth() }.bodyAsText()

    suspend fun sendChat(message: String, sessionId: String?, role: String): ChatStart {
        val body = buildString {
            append("{\"message\":\"").append(message.jsonEscape()).append("\"")
            if (sessionId != null) append(",\"session_id\":\"$sessionId\"")
            append(",\"role\":\"$role\"}")
        }
        val r = client.post(url("/v1/chat")) { auth(); setBody(body) }.bodyAsText()
        val o = json.parseToJsonElement(r)
        return ChatStart(o.str("job_id"), o.str("session_id"))
    }

    /** kirim 1 prompt, tunggu selesai, kembalikan teks final (result). onEvent utk progres live. */
    suspend fun runToCompletion(message: String, role: String, sessionId: String? = null,
                                onEvent: (BridgeEvent) -> Unit = {}): String {
        val start = sendChat(message, sessionId, role)
        var out = ""
        streamJob(start.jobId).collect { ev ->
            onEvent(ev)
            when (ev) {
                is BridgeEvent.Done -> out = ev.result
                is BridgeEvent.Err -> if (out.isEmpty()) out = "ERR: ${ev.msg}"
                else -> {}
            }
        }
        return out
    }

    /** stream event SSE untuk job. */
    fun streamJob(jobId: String): Flow<BridgeEvent> = flow {
        client.prepareGet(url("/v1/chat/stream/$jobId")) { auth() }.execute { resp ->
            val ch = resp.bodyAsChannel()
            while (true) {
                val line = ch.readUTF8Line() ?: break
                if (!line.startsWith("data:")) continue
                val payload = line.removePrefix("data:").trim()
                if (payload.isEmpty()) continue
                val ev = parseEvent(payload) ?: continue
                emit(ev)
                if (ev is BridgeEvent.Done || ev is BridgeEvent.Err) break
            }
        }
    }

    private fun parseEvent(payload: String): BridgeEvent? {
        val o = runCatching { json.parseToJsonElement(payload) as JsonObject }.getOrNull() ?: return null
        return when (o.str("type")) {
            "ready" -> BridgeEvent.Ready(o.str("session_id"), o.str("role"))
            "text" -> BridgeEvent.TextDelta(o.str("delta"))
            "tool_use" -> BridgeEvent.ToolUse(o.str("name"), o.str("input"))
            "tool_result" -> BridgeEvent.ToolResult(o.str("summary"))
            "artifact" -> BridgeEvent.Artifact(o.str("type"), o.str("url"), o.str("name"))
            "done" -> BridgeEvent.Done(o.str("result"))
            "error" -> BridgeEvent.Err(o.str("msg"))
            else -> null
        }
    }
}

private fun kotlinx.serialization.json.JsonElement.str(key: String): String =
    (this as? JsonObject)?.get(key)?.jsonPrimitive?.contentOrNull ?: ""

private fun String.jsonEscape(): String = buildString {
    for (c in this@jsonEscape) when (c) {
        '"' -> append("\\\""); '\\' -> append("\\\\"); '\n' -> append("\\n")
        '\r' -> append("\\r"); '\t' -> append("\\t"); else -> append(c)
    }
}

/** engine HTTP per-platform. */
expect fun createHttpClient(): HttpClient

/** Konfigurasi koneksi bridge (LAN/Tailscale CT108). TODO: pindah ke Settings/DataStore. */
object BridgeConfig {
    var baseUrl = "http://192.168.0.220:8090"
    var token = "571defca9fc68bdfc2c8ab482206fa04dd0968913e85ae15"
    val configured: Boolean get() = token.isNotBlank()
}

/** factory bersama; null kalau token belum diisi. */
fun bridgeApi(): BridgeApi? = if (BridgeConfig.configured) BridgeApi(BridgeConfig.baseUrl, BridgeConfig.token) else null
