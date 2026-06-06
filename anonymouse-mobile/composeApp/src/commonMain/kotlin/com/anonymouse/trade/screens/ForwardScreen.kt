package com.anonymouse.trade.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.anonymouse.trade.AppState
import com.anonymouse.trade.ToastData
import com.anonymouse.trade.data.*
import com.anonymouse.trade.theme.Dimens
import com.anonymouse.trade.theme.theme
import com.anonymouse.trade.ui.*

@Composable
fun ForwardScreen(st: AppState) {
    val pal = theme
    var mk by remember { mutableStateOf("forex") }
    var events by remember { mutableStateOf(DB.notifEvents) }
    val market = DB.markets.getValue(mk)

    var fwd by remember { mutableStateOf<FwdDto?>(null) }
    var loading by remember { mutableStateOf(false) }
    var refreshKey by remember { mutableStateOf(0) }
    LaunchedEffect(mk, refreshKey) {
        fwd = null
        val api = bridgeApi()
        if (api == null) { fwd = mockForward(mk); return@LaunchedEffect }
        loading = true
        val text = runCatching { if (mk == "crypto") api.getCrypto() else api.getCache("forward_$mk") }.getOrNull()
        val parsed = if (mk == "crypto") text?.let { parseCrypto(it) } else text?.let { parseForward(it) }
        fwd = parsed?.takeIf { it.balance > 0 || it.positions.isNotEmpty() } ?: mockForward(mk)
        loading = false
    }
    // PnL forex REAL-TIME (polling 4 detik) — override snapshot saat market=forex
    var liveFx by remember { mutableStateOf<LiveForex?>(null) }
    var priceHist by remember { mutableStateOf<Map<String, List<Float>>>(emptyMap()) }
    LaunchedEffect(mk) {
        liveFx = null
        if (mk != "forex") return@LaunchedEffect
        val api = bridgeApi() ?: return@LaunchedEffect
        while (true) {
            runCatching { api.getLiveForex() }.getOrNull()?.let { parseLiveForex(it) }?.let { lf ->
                liveFx = lf
                priceHist = priceHist.toMutableMap().apply {
                    lf.positions.forEach { p ->
                        val cur = (this[p.sym] ?: emptyList()).toMutableList()
                        cur.add(p.mark.toFloat())
                        while (cur.size > 40) cur.removeAt(0)
                        this[p.sym] = cur
                    }
                }
            }
            kotlinx.coroutines.delay(4000)
        }
    }
    val fx = if (mk == "forex") liveFx else null

    val data = fwd ?: mockForward(mk)
    val positions = fx?.positions?.map { FwdPosDto(it.sym, it.side, it.qty, it.entry, it.mark, it.pnlPct, it.pnl) } ?: data.positions
    val balanceShown = fx?.balance ?: data.balance
    val equity = data.equity.map { it.toFloat() }.ifEmpty { listOf(balanceShown.toFloat(), balanceShown.toFloat()) }
    val openPnl = fx?.openPnlPct ?: data.openPnlPct
    val winners = positions.count { it.pnlPct >= 0 }
    val live = fx != null || data.source != "mock"
    val realtime = fx != null

    fun fmt(n: Double): String = when (if (fx != null) "USD" else data.currency) {
        "IDR" -> "Rp " + n.fmt0()
        else -> if (mk == "forex" && n < 1000) (kotlin.math.round(n * 10000) / 10000.0).toString() else "$" + n.fmt0()
    }

    Column(Modifier.fillMaxSize()) {
        TopBar("Forward test", "Live paper-test · data dari CT108", big = true,
            right = {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IconBtn("refresh") { if (!loading) refreshKey++ }
                    IconBtn("chat") { st.showChat = true }
                }
            })
        ChipRow {
            DB.markets.values.forEach { m -> Chip("${m.glyph}  ${m.label}", mk == m.key, m.color) { mk = m.key } }
        }
        Spacer(Modifier.height(8.dp))
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
            if (loading) {
                MCard {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Icon("refresh", 20.dp, pal.accent)
                        TextUi("Mengambil posisi ${market.label} dari server…", 13, color = pal.textDim)
                    }
                }
                Spacer(Modifier.height(Dimens.gap))
            }
            // running banner
            MCard {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Box(Modifier.size(44.dp).clip(RoundedCornerShape(12.dp)).background(market.color.copy(alpha = 0.16f)),
                        contentAlignment = Alignment.Center) { Icon("forward", 22.dp, market.color) }
                    Column(Modifier.weight(1f)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                            Head(if (mk == "idx") "ARA paper" else "Regime-aware", 14)
                            Badge(if (realtime) "Real-time" else if (live) "Live" else "Mock", if (live) Tone.up else Tone.neutral, leading = { if (live) LiveDot(5.dp) })
                            Badge("Paper", Tone.violet)
                        }
                        TextUi(if (realtime) "${market.venue} · MT5 real-time · refresh 4s" else "${market.venue} · ${data.source}", 11, color = pal.textMute)
                    }
                }
            }
            Spacer(Modifier.height(Dimens.gap))
            // stats 2x2
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Box(Modifier.weight(1f)) { MStat("Balance / equity", fmt(balanceShown), if (realtime) "real-time" else if (live) "live" else "demo", icon = "wallet") }
                Box(Modifier.weight(1f)) {
                    MStat("Open P&L", (if (openPnl >= 0) "+" else "") + "${openPnl.round2()}%",
                        if (fx != null) (if (fx.profit >= 0) "+$" else "-$") + kotlin.math.abs(fx.profit).round2() else "${positions.size} posisi",
                        deltaDown = openPnl < 0, icon = "trending")
                }
            }
            Spacer(Modifier.height(12.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Box(Modifier.weight(1f)) { MStat("Win rate", "${if (data.winRate > 0) data.winRate else if (positions.isEmpty()) 0 else winners * 100 / positions.size}%", "paper", icon = "chart") }
                Box(Modifier.weight(1f)) { MStat("Market", market.label, market.venue.substringBefore(" ·"), icon = "globe", iconColor = market.color) }
            }
            Spacer(Modifier.height(Dimens.gap))
            // equity
            MCard {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Column { TextUi("Equity", 12, FontWeight.SemiBold, pal.textMute); Mono(fmt(balanceShown), 20, FontWeight.Bold) }
                    Badge(if (realtime) "Real-time · MT5" else if (live) "Live · CT108" else "Demo", if (live) Tone.up else Tone.neutral, leading = { if (realtime) LiveDot(5.dp) })
                }
                Spacer(Modifier.height(10.dp))
                AreaChart(equity, 150.dp, market.color)
            }
            Spacer(Modifier.height(Dimens.gap))
            // positions
            Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp), horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically) {
                Head("Open positions", 16); Badge("${positions.size} open", Tone.neutral)
            }
            Spacer(Modifier.height(8.dp))
            if (positions.isEmpty()) {
                MCard { TextUi("Tidak ada posisi terbuka.", 13, color = pal.textMute) }
            } else Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                positions.forEach { p ->
                    MCard(pad = 13.dp) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Column(Modifier.weight(1f)) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Mono(p.sym, 14, FontWeight.Bold); DirTag(p.side)
                                }
                                Mono("${p.qty} @ ${fmt(p.entry)}", 11, FontWeight.Normal, pal.textMute)
                            }
                            val hist = priceHist[p.sym] ?: emptyList()
                            if (hist.size >= 2) Spark(hist, p.pnl >= 0, 56.dp, 28.dp)
                            Column(horizontalAlignment = Alignment.End) {
                                Mono(fmt(p.mark), 13, FontWeight.Bold)
                                Mono((if (p.pnlPct >= 0) "+" else "") + "${p.pnlPct.round2()}%", 12, FontWeight.Bold, if (p.pnlPct >= 0) pal.up else pal.down)
                                if (p.pnl != 0.0) Mono((if (p.pnl >= 0) "+$" else "-$") + kotlin.math.abs(p.pnl).round2(), 11, FontWeight.SemiBold, if (p.pnl >= 0) pal.up else pal.down)
                            }
                        }
                    }
                }
            }
            Spacer(Modifier.height(Dimens.gap))
            // notifications
            MCard(pad = 0.dp) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 13.dp),
                    horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon("bell", 16.dp, pal.accent); Head("Notifications", 14)
                    }
                    Btn("Test", BtnVariant.soft, icon = "send") {
                        st.push(ToastData("Test alert", "Routed to WhatsApp · ${market.label} paper", "send", "Anonymouse · ${market.label}"))
                    }
                }
                Box(Modifier.fillMaxWidth().height(1.dp).background(pal.borderSoft))
                Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(11.dp)) {
                    DB.notifChannels.forEach { c ->
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(11.dp)) {
                            Box(Modifier.size(32.dp).clip(RoundedCornerShape(9.dp)).background(c.color.copy(alpha = 0.2f)),
                                contentAlignment = Alignment.Center) { Head(c.name.take(1), 14, FontWeight.ExtraBold, c.color) }
                            Column(Modifier.weight(1f)) { TextUi(c.name, 13, FontWeight.SemiBold); Mono(c.target, 11, FontWeight.Normal, pal.textMute) }
                            if (c.connected) Badge("Linked", Tone.up, leading = { Icon("check", 11.dp, pal.up) })
                            else Btn("Connect", BtnVariant.soft, icon = "link") {}
                        }
                    }
                }
                Box(Modifier.fillMaxWidth().height(1.dp).background(pal.borderSoft))
                Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                    TextUi("Alert me on", 11, FontWeight.SemiBold, pal.textMute)
                    events.forEach { e ->
                        Row(Modifier.fillMaxWidth().padding(vertical = 7.dp), horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically) {
                            TextUi(e.label, 13, color = pal.textDim)
                            MToggle(e.on) { events = events.map { if (it.id == e.id) it.copy(on = !it.on) else it } }
                        }
                    }
                }
            }
            Spacer(Modifier.height(Dimens.gap))
            // live feed (dari server, kalau ada)
            if (data.feed.isNotEmpty()) {
                MCard(pad = 0.dp) {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)) { LiveDot(); Head("Live feed", 14) }
                    data.feed.forEach { f ->
                        val tone = when (f.kind) { "entry" -> pal.accent; "tp" -> pal.up; "sl" -> pal.down; else -> pal.textMute }
                        val ic = when (f.kind) { "entry" -> "signals"; "tp" -> "arrowUp"; "sl" -> "arrowDown"; else -> "search" }
                        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 9.dp),
                            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(11.dp)) {
                            Icon(ic, 15.dp, tone); TextUi(f.txt, 12, color = pal.text, modifier = Modifier.weight(1f)); Mono(f.t, 10, FontWeight.Normal, pal.textMute)
                        }
                    }
                }
            }
            Spacer(Modifier.height(28.dp))
        }
    }
}
