package com.canorus.odysseus;

import android.accessibilityservice.AccessibilityService;
import android.app.Notification;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.Settings;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Motor autónomo do Agente Odysseus integrado com /agent/step (messages + SSE + tool_calls + fragmentos de texto):
 * - Envia sempre `messages` (system + histórico multi-turno assistant/tool + estado atual do ecrã e imagem Set-of-Mark)
 * - Inclui definições de `tools` Android UI (com fallback automático se o servidor impuser schema próprio)
 * - Lê streams SSE com `tool_calls` fragmentados (OpenAI delta.tool_calls, Anthropic input_json_delta, objetos tool_call)
 *   e fragmentos de texto (`delta.content`, `<think>`, `<tool_call>`, blocos JSON ou resposta final em texto natural)
 * - Mantém proteções AgentSafety, visibilidade obrigatória do botão ⏹ PARAR e corte imediato do socket HTTP
 */
public class AgentService extends Service {

    static final String ACTION_START_GOAL = "com.canorus.odysseus.AGENT_START";
    static final String ACTION_STOP = "com.canorus.odysseus.AGENT_STOP";
    static final String ACTION_SHOW_OVERLAY = "com.canorus.odysseus.AGENT_OVERLAY";
    static final String ACTION_HIDE_OVERLAY = "com.canorus.odysseus.AGENT_HIDE_OVERLAY";
    static final String EXTRA_GOAL = "goal";

    private static final int NOTIF_ID = 88;
    private static final int CONFIRM_APPROVE = 1;
    private static final int CONFIRM_SKIP = 0;
    private static final int CONFIRM_STOP = -1;
    private static final int MAX_HISTORY_TURNS = 8;

    private final Handler main = new Handler(Looper.getMainLooper());
    private final AtomicBoolean running = new AtomicBoolean(false);
    private final AtomicBoolean abort = new AtomicBoolean(false);
    private Thread worker;
    private volatile CountDownLatch activeGate;
    static final String CONTROL_WINDOW = "Odysseus agent controls";
    private volatile HttpURLConnection activeConn;
    private volatile long lastPreviewUpdateMs = 0;

    private WindowManager wm;
    private WindowManager.LayoutParams overlayLp;
    private LinearLayout overlayRoot;
    private TextView bubbleBtn;
    private LinearLayout quickPanel;
    private LinearLayout runningBar;
    private TextView stepLabel;
    private LinearLayout confirmBox;
    private TextView confirmText;
    private final AtomicInteger confirmChoice = new AtomicInteger(CONFIRM_STOP);

    /** Registo completo de um turno concluído para manter `messages` 100% válido em chamadas seguintes. */
    private static final class StepTurn {
        final String userPromptCompact;
        final String assistantText;
        final String assistantFallbackText;
        final JSONArray rawToolCalls;
        final JSONArray toolResults;
        final String plainResultSummary;

        StepTurn(String userPromptCompact, String assistantText, String assistantFallbackText,
                 JSONArray rawToolCalls, JSONArray toolResults, String plainResultSummary) {
            this.userPromptCompact = userPromptCompact;
            this.assistantText = assistantText == null ? "" : assistantText;
            this.assistantFallbackText = assistantFallbackText == null ? "" : assistantFallbackText;
            this.rawToolCalls = rawToolCalls;
            this.toolResults = toolResults;
            this.plainResultSummary = plainResultSummary == null ? "" : plainResultSummary;
        }
    }

    /** Resultado normalizado de uma resposta SSE/JSON de /agent/step. */
    private static final class StepResponse {
        final JSONObject decision;
        final String assistantText;
        final String assistantFallbackText;
        final JSONArray rawToolCalls;
        final String primaryToolCallId;
        final String primaryToolName;

        StepResponse(JSONObject decision, String assistantText, String assistantFallbackText,
                     JSONArray rawToolCalls, String primaryToolCallId, String primaryToolName) {
            this.decision = decision;
            this.assistantText = assistantText == null ? "" : assistantText;
            this.assistantFallbackText = assistantFallbackText == null ? "" : assistantFallbackText;
            this.rawToolCalls = rawToolCalls;
            this.primaryToolCallId = primaryToolCallId;
            this.primaryToolName = primaryToolName;
        }
    }

    /** Acumulador para `tool_calls` recebidos completos ou fragmentados em múltiplos eventos SSE. */
    private static final class ToolCallAccum {
        final int index;
        String id = "";
        final StringBuilder nameBuf = new StringBuilder();
        final StringBuilder argsBuf = new StringBuilder();
        JSONObject argsObj = null;

        ToolCallAccum(int index) {
            this.index = index;
        }

        void mergeId(String incomingId) {
            if (incomingId != null && !incomingId.isEmpty()) {
                this.id = incomingId;
            }
        }

        void mergeName(String incomingName) {
            if (incomingName == null || incomingName.isEmpty()) return;
            String cur = nameBuf.toString();
            if (cur.isEmpty()) {
                nameBuf.append(incomingName);
            } else if (!cur.equals(incomingName)) {
                nameBuf.append(incomingName);
            }
        }

        void appendArgsChunk(String chunk) {
            if (chunk != null && !chunk.isEmpty()) {
                argsBuf.append(chunk);
            }
        }

        void setArgsObject(JSONObject obj) {
            if (obj != null) {
                this.argsObj = obj;
            }
        }

        String resolvedId(int step) {
            return (id == null || id.isEmpty()) ? ("call_" + step + "_" + index) : id;
        }

        String resolvedName() {
            return nameBuf.toString().trim();
        }

        JSONObject resolvedArgsObject() {
            if (argsObj != null) return argsObj;
            String raw = argsBuf.toString().trim();
            if (raw.isEmpty()) return new JSONObject();
            try {
                return new JSONObject(raw);
            } catch (Exception e) {
                int s = raw.indexOf('{');
                int end = raw.lastIndexOf('}');
                if (s >= 0 && end > s) {
                    try { return new JSONObject(raw.substring(s, end + 1)); }
                    catch (Exception ignored) { }
                }
                return new JSONObject();
            }
        }

        String resolvedArgsString() {
            String raw = argsBuf.toString().trim();
            if (!raw.isEmpty()) {
                try {
                    new JSONObject(raw);
                    return raw;
                } catch (Exception ignored) { }
            }
            return resolvedArgsObject().toString();
        }
    }

    static void startGoal(Context ctx, String goal) {
        if (goal == null || goal.trim().isEmpty()) return;
        Intent i = new Intent(ctx, AgentService.class)
                .setAction(ACTION_START_GOAL)
                .putExtra(EXTRA_GOAL, goal.trim());
        ContextCompat.startForegroundService(ctx, i);
    }

    static void stopAgent(Context ctx) {
        try {
            ctx.startService(new Intent(ctx, AgentService.class).setAction(ACTION_STOP));
        } catch (Exception ignored) { }
    }

    static void showIdleOverlay(Context ctx) {
        if (!Settings.canDrawOverlays(ctx)) return;
        ContextCompat.startForegroundService(ctx,
                new Intent(ctx, AgentService.class).setAction(ACTION_SHOW_OVERLAY));
    }

    static void hideOverlay(Context ctx) {
        try {
            ctx.startService(new Intent(ctx, AgentService.class).setAction(ACTION_HIDE_OVERLAY));
        } catch (Exception ignored) { }
    }

    private static String serverCookieForUrl(String base, String target) {
        try {
            URL a = new URL(base), b = new URL(target);
            int ap = a.getPort() < 0 ? a.getDefaultPort() : a.getPort();
            int bp = b.getPort() < 0 ? b.getDefaultPort() : b.getPort();
            if (a.getProtocol().equalsIgnoreCase(b.getProtocol()) && a.getHost().equalsIgnoreCase(b.getHost()) && ap == bp)
                return CookieManager.getInstance().getCookie(target);
        } catch (Exception ignored) { }
        return null;
    }

    /** Teste rápido de diagnóstico nas Definições enviando um campo `messages` válido a /agent/step. */
    static String probeEndpoint(Context ctx) {
        HttpURLConnection c = null;
        try {
            String url = resolveEndpointUrl(ctx);
            String authHeader = AppSettings.agentAuthHeader(ctx);
            String authVal = "/api/android-agent/step".equals(AppSettings.agentEndpoint(ctx)) ? "" : AppSettings.formatAgentAuthValue(ctx);
            String base = AppSettings.serverUrl(ctx);
            String cookie = serverCookieForUrl(base, url);
            String model = AppSettings.sp(ctx).getString("agent_model", "").trim();

            c = (HttpURLConnection) new URL(url).openConnection();
            c.setRequestMethod("POST");
            c.setInstanceFollowRedirects(false);
            c.setConnectTimeout(8000);
            c.setReadTimeout(20000);
            c.setRequestProperty("Content-Type", "application/json");
            c.setRequestProperty("Accept", "text/event-stream, application/json");
            c.setRequestProperty("Accept-Encoding", "identity");
            if (!authVal.isEmpty()) c.setRequestProperty(authHeader, authVal);
            if (cookie != null && !cookie.isEmpty()) c.setRequestProperty("Cookie", cookie);
            c.setDoOutput(true);

            JSONArray msgs = new JSONArray()
                    .put(new JSONObject().put("role", "user").put("content", "Responde apenas OK."));
            JSONObject ping = new JSONObject()
                    .put("messages", msgs)
                    .put("stream", true);
            if (!model.isEmpty()) ping.put("model", model);
            if (AppSettings.sp(ctx).getBoolean("agent_server_model", false) && "/api/android-agent/step".equals(AppSettings.agentEndpoint(ctx))) {
                ping.put("endpoint_id", AppSettings.sp(ctx).getString("agent_endpoint_id", ""));
            }

            try (OutputStream os = c.getOutputStream()) {
                os.write(ping.toString().getBytes(StandardCharsets.UTF_8));
            }

            int code = c.getResponseCode();
            String ct = c.getHeaderField("Content-Type");
            InputStream raw = code < 400 ? c.getInputStream() : c.getErrorStream();
            StringBuilder sample = new StringBuilder();
            if (raw != null) {
                try (BufferedReader br = new BufferedReader(new InputStreamReader(raw, StandardCharsets.UTF_8))) {
                    String line;
                    int lines = 0;
                    while (lines < 6 && (line = br.readLine()) != null) {
                        if (line.trim().isEmpty()) continue;
                        if (sample.length() > 0) sample.append(" | ");
                        sample.append(line.length() > 90 ? line.substring(0, 90) + "…" : line);
                        lines++;
                        if (line.contains("[DONE]")) break;
                    }
                } catch (Exception ignored) { }
            }
            if (code == 401 || code == 403) {
                return "❌ HTTP " + code + " (Não autorizado) — verifica o Token e o cabeçalho (" + authHeader + ").";
            }
            if (code == 404) {
                return "❌ HTTP 404 — a rota " + url + " não existe no servidor.";
            }
            if (code >= 400) {
                return "❌ HTTP " + code + " em " + url + (sample.length() == 0 ? "" : "\nDetalhe: " + sample);
            }
            return "✅ Ligação e schema `messages` OK (HTTP " + code
                    + (ct != null ? ", " + ct : "") + ")"
                    + (sample.length() == 0 ? "" : "\nAmostra SSE: " + sample);
        } catch (Exception e) {
            return "❌ Falha de ligação: " + (e.getMessage() == null ? e.toString() : e.getMessage());
        } finally {
            if (c != null) c.disconnect();
        }
    }

    static String resolveEndpointUrl(Context ctx) throws Exception {
        String base = AppSettings.serverUrl(ctx);
        String path = AppSettings.agentEndpoint(ctx);
        if (path.startsWith("https://") || path.startsWith("http://")) return path;
        if (base == null || base.isEmpty()) throw new Exception(L.t("Abre o Odysseus e inicia sessão primeiro"));
        return base + (path.startsWith("/") ? path : "/" + path);
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        AppSettings.applyServer(this);
        Channels.ensureAll(this);
        startFgNotification(L.t("Agente Odysseus pronto"));

        String action = intent == null ? null : intent.getAction();
        if (ACTION_STOP.equals(action)) {
            triggerImmediateStop(L.t("Agente parado pelo utilizador."));
            if (!AppSettings.sp(this).getBoolean("agent_overlay", false)) {
                removeOverlay();
                stopForeground(true);
                stopSelf();
            } else {
                switchToIdleMode();
            }
            return START_NOT_STICKY;
        }

        if (ACTION_HIDE_OVERLAY.equals(action)) {
            triggerImmediateStop(null);
            removeOverlay();
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }

        ensureOverlay();

        if (ACTION_START_GOAL.equals(action)) {
            String goal = intent.getStringExtra(EXTRA_GOAL);
            if (goal != null && !goal.trim().isEmpty()) {
                launchGoalLoop(goal.trim());
            }
        } else {
            switchToIdleMode();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        triggerImmediateStop(null);
        removeOverlay();
        super.onDestroy();
    }

    private void startFgNotification(String statusText) {
        PendingIntent openPi = PendingIntent.getActivity(this, 80,
                new Intent(this, AgentPromptActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stopPi = PendingIntent.getService(this, 81,
                new Intent(this, AgentService.class).setAction(ACTION_STOP),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

        Notification n = new NotificationCompat.Builder(this, Channels.SYNC_FG)
                .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setContentTitle("Odysseus · Agente")
                .setContentText(statusText)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setOngoing(true)
                .setSilent(true)
                .setContentIntent(openPi)
                .addAction(0, L.t("⏹ Parar"), stopPi)
                .build();
        try {
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            } else {
                startForeground(NOTIF_ID, n);
            }
        } catch (Exception ignored) { }
    }

    private void triggerImmediateStop(String toastMsg) {
        abort.set(true);
        running.set(false);
        confirmChoice.set(CONFIRM_STOP);
        CountDownLatch gate = activeGate;
        if (gate != null) gate.countDown();
        final HttpURLConnection conn = activeConn;
        activeConn = null;
        if (conn != null) {
            Bg.run(() -> { try { conn.disconnect(); } catch (Exception ignored) { } });
        }
        if (worker != null) worker.interrupt();
        if (toastMsg != null) {
            main.post(() -> Toast.makeText(this, toastMsg, Toast.LENGTH_SHORT).show());
        }
    }

    private void ensureOverlay() {
        if (overlayRoot != null || !Settings.canDrawOverlays(this)) return;
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        if (wm == null) return;

        boolean ryoku = "ryoku".equals(AppSettings.sp(this).getString("ui_theme", ""));
        int bgCol = ryoku ? 0xEE0a0a0a : 0xEE282c34;
        int fgCol = ryoku ? 0xFFcdc4ba : 0xFFE5E9F0;
        int acCol = ryoku ? 0xFFce5e32 : 0xFF7C9CFF;

        overlayRoot = new LinearLayout(this);
        overlayRoot.setOrientation(LinearLayout.VERTICAL);
        overlayRoot.setId(View.generateViewId());

        bubbleBtn = new TextView(this);
        bubbleBtn.setText("🤖");
        bubbleBtn.setTextSize(20);
        bubbleBtn.setGravity(Gravity.CENTER);
        int bSize = dp(48);
        GradientDrawable circle = new GradientDrawable();
        circle.setColor(bgCol);
        circle.setCornerRadius(bSize / 2f);
        circle.setStroke(dp(2), acCol);
        bubbleBtn.setBackground(circle);
        overlayRoot.addView(bubbleBtn, new LinearLayout.LayoutParams(bSize, bSize));

        quickPanel = new LinearLayout(this);
        quickPanel.setOrientation(LinearLayout.HORIZONTAL);
        quickPanel.setGravity(Gravity.CENTER_VERTICAL);
        quickPanel.setPadding(dp(8), dp(6), dp(8), dp(6));
        quickPanel.setBackground(roundedBg(bgCol, acCol, dp(14)));
        quickPanel.setVisibility(View.GONE);

        Button voiceBtn = smallBtn("🎤", acCol, Color.WHITE);
        voiceBtn.setOnClickListener(v -> {
            quickPanel.setVisibility(View.GONE);
            bubbleBtn.setVisibility(View.VISIBLE);
            startActivity(new Intent(this, AgentPromptActivity.class)
                    .putExtra("voice", true)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        });
        Button promptBtn = smallBtn(L.t("Comando…"), 0xFF3d4452, fgCol);
        promptBtn.setOnClickListener(v -> {
            quickPanel.setVisibility(View.GONE);
            bubbleBtn.setVisibility(View.VISIBLE);
            startActivity(new Intent(this, AgentPromptActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        });
        Button closePanel = smallBtn("✕", 0xFF3d4452, fgCol);
        closePanel.setOnClickListener(v -> {
            quickPanel.setVisibility(View.GONE);
            bubbleBtn.setVisibility(View.VISIBLE);
        });
        quickPanel.addView(voiceBtn);
        quickPanel.addView(promptBtn);
        quickPanel.addView(closePanel);
        overlayRoot.addView(quickPanel);

        runningBar = new LinearLayout(this);
        runningBar.setOrientation(LinearLayout.HORIZONTAL);
        runningBar.setGravity(Gravity.CENTER_VERTICAL);
        runningBar.setPadding(dp(10), dp(6), dp(8), dp(6));
        runningBar.setBackground(roundedBg(bgCol, acCol, dp(14)));
        runningBar.setVisibility(View.GONE);

        stepLabel = new TextView(this);
        stepLabel.setTextColor(fgCol);
        stepLabel.setTextSize(13);
        stepLabel.setMaxWidth(dp(210));
        stepLabel.setSingleLine(true);
        runningBar.addView(stepLabel);

        Button killBtn = smallBtn("⏹ PARAR", 0xFFd94848, Color.WHITE);
        killBtn.setContentDescription(CONTROL_WINDOW);
        killBtn.setTypeface(Typeface.DEFAULT_BOLD);
        killBtn.setOnClickListener(v -> {
            triggerImmediateStop(L.t("Agente parado."));
            switchToIdleMode();
        });
        runningBar.addView(killBtn);
        overlayRoot.addView(runningBar);

        confirmBox = new LinearLayout(this);
        confirmBox.setOrientation(LinearLayout.VERTICAL);
        confirmBox.setPadding(dp(12), dp(10), dp(12), dp(10));
        confirmBox.setBackground(roundedBg(bgCol, 0xFFf0a540, dp(14)));
        confirmBox.setVisibility(View.GONE);

        TextView cTitle = new TextView(this);
        cTitle.setText("⚠️ Confirmar ação sensível");
        cTitle.setTextColor(0xFFf0a540);
        cTitle.setTextSize(14);
        cTitle.setTypeface(Typeface.DEFAULT_BOLD);
        confirmBox.addView(cTitle);

        confirmText = new TextView(this);
        confirmText.setTextColor(fgCol);
        confirmText.setTextSize(13);
        confirmText.setMaxWidth(dp(260));
        confirmText.setPadding(0, dp(4), 0, dp(8));
        confirmBox.addView(confirmText);

        LinearLayout cRow = new LinearLayout(this);
        Button okBtn = smallBtn("✓ Autorizar", 0xFF2ea043, Color.WHITE);
        Button skipBtn = smallBtn("✕ Recusar", 0xFF3d4452, fgCol);
        Button abortBtn = smallBtn("⏹ Parar", 0xFFd94848, Color.WHITE);
        okBtn.setOnClickListener(v -> resolveConfirm(CONFIRM_APPROVE));
        skipBtn.setOnClickListener(v -> resolveConfirm(CONFIRM_SKIP));
        abortBtn.setOnClickListener(v -> resolveConfirm(CONFIRM_STOP));
        cRow.addView(okBtn);
        cRow.addView(skipBtn);
        cRow.addView(abortBtn);
        confirmBox.addView(cRow);
        overlayRoot.addView(confirmBox);

        int type = Build.VERSION.SDK_INT >= 26
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE;
        overlayLp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                type,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        overlayLp.setTitle(CONTROL_WINDOW);
        overlayLp.gravity = Gravity.TOP | Gravity.START;
        overlayLp.x = dp(12);
        overlayLp.y = dp(120);

        installDragAndTap(bubbleBtn);
        installDragAndTap(stepLabel);

        try { wm.addView(overlayRoot, overlayLp); } catch (Exception ignored) { overlayRoot = null; }
    }

    private void installDragAndTap(View handle) {
        handle.setOnTouchListener(new View.OnTouchListener() {
            int startX, startY;
            float downX, downY;
            long downAt;
            boolean moved;

            @Override
            public boolean onTouch(View v, MotionEvent ev) {
                if (overlayLp == null || wm == null || overlayRoot == null) return false;
                switch (ev.getActionMasked()) {
                    case MotionEvent.ACTION_DOWN:
                        startX = overlayLp.x;
                        startY = overlayLp.y;
                        downX = ev.getRawX();
                        downY = ev.getRawY();
                        downAt = System.currentTimeMillis();
                        moved = false;
                        return true;
                    case MotionEvent.ACTION_MOVE:
                        int dx = Math.round(ev.getRawX() - downX);
                        int dy = Math.round(ev.getRawY() - downY);
                        if (Math.abs(dx) > dp(6) || Math.abs(dy) > dp(6)) moved = true;
                        if (moved) {
                            overlayLp.x = startX + dx;
                            overlayLp.y = startY + dy;
                            try { wm.updateViewLayout(overlayRoot, overlayLp); } catch (Exception ignored) { }
                        }
                        return true;
                    case MotionEvent.ACTION_UP:
                        if (!moved && handle == bubbleBtn) {
                            if (System.currentTimeMillis() - downAt >= 500) {
                                startActivity(new Intent(AgentService.this, AgentPromptActivity.class)
                                        .putExtra("voice", true)
                                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                            } else {
                                bubbleBtn.setVisibility(View.GONE);
                                quickPanel.setVisibility(View.VISIBLE);
                            }
                        }
                        return true;
                }
                return false;
            }
        });
    }

    private void switchToIdleMode() {
        main.post(() -> {
            startFgNotification(L.t("Agente Odysseus pronto"));
            if (overlayRoot == null) return;
            runningBar.setVisibility(View.GONE);
            confirmBox.setVisibility(View.GONE);
            quickPanel.setVisibility(View.GONE);
            bubbleBtn.setVisibility(View.VISIBLE);
        });
    }

    private void updateRunningStatus(String msg) {
        String clean = msg == null ? "" : msg.replace('\n', ' ').trim();
        main.post(() -> {
            startFgNotification(clean);
            if (overlayRoot == null) return;
            bubbleBtn.setVisibility(View.GONE);
            quickPanel.setVisibility(View.GONE);
            runningBar.setVisibility(View.VISIBLE);
            stepLabel.setText("🤖 " + clean + "  ");
        });
    }

    private void updateRunningPreviewThrottled(int step, String text) {
        long now = System.currentTimeMillis();
        if (now - lastPreviewUpdateMs < 220) return;
        lastPreviewUpdateMs = now;
        String clean = stripThinkBlocks(text, null).replace('\n', ' ').trim();
        if (clean.isEmpty()) return;
        if (clean.length() > 48) clean = clean.substring(clean.length() - 48);
        updateRunningStatus("P" + step + " · " + clean);
    }

    private int askCriticalConfirmation(String reason) {
        CountDownLatch latch = new CountDownLatch(1);
        activeGate = latch;
        confirmChoice.set(CONFIRM_STOP);
        main.post(() -> {
            vibrateShort();
            ensureOverlay();
            if (overlayRoot != null) {
                overlayRoot.setVisibility(View.VISIBLE);
                bubbleBtn.setVisibility(View.GONE);
                quickPanel.setVisibility(View.GONE);
                runningBar.setVisibility(View.GONE);
                confirmText.setText(reason);
                confirmBox.setVisibility(View.VISIBLE);
            } else {
                resolveConfirm(CONFIRM_STOP);
            }
        });
        try { latch.await(); } catch (InterruptedException e) { return CONFIRM_STOP; }
        activeGate = null;
        main.post(() -> {
            if (confirmBox != null) confirmBox.setVisibility(View.GONE);
            if (runningBar != null && running.get()) runningBar.setVisibility(View.VISIBLE);
        });
        return confirmChoice.get();
    }

    private void resolveConfirm(int choice) {
        confirmChoice.set(choice);
        CountDownLatch gate = activeGate;
        if (gate != null) gate.countDown();
    }

    private void setOverlayTemporarilyHidden(boolean hidden) {
        CountDownLatch l = new CountDownLatch(1);
        main.post(() -> {
            if (overlayRoot != null) overlayRoot.setVisibility(hidden ? View.INVISIBLE : View.VISIBLE);
            l.countDown();
        });
        try { l.await(); } catch (InterruptedException ignored) { }
    }

    private void removeOverlay() {
        main.post(() -> {
            if (overlayRoot != null && wm != null) {
                try { wm.removeView(overlayRoot); } catch (Exception ignored) { }
            }
            overlayRoot = null;
        });
    }

    // ---- Ciclo Principal com Histórico `messages` Multi-Turno ----

    private void launchGoalLoop(final String goal) {
        if (worker != null && worker.isAlive()) return;

        if (!AgentAccessibilityService.isReady()) {
            main.post(() -> {
                Toast.makeText(this, L.t("Ativa primeiro a Acessibilidade do Agente Odysseus"), Toast.LENGTH_LONG).show();
                startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            });
            return;
        }

        if (!Settings.canDrawOverlays(this)) {
            main.post(() -> {
                Toast.makeText(this, "Ativa a permissão de Sobrepor a outras apps (necessária para confirmações e botão PARAR).", Toast.LENGTH_LONG).show();
                startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:" + getPackageName())).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            });
            return;
        }

        ensureOverlay();
        abort.set(false);
        running.set(true);
        final int maxSteps = AppSettings.sp(this).getInt("agent_max_steps", 25);

        worker = new Thread(() -> {
            String sessionId = "mob-" + UUID.randomUUID().toString().substring(0, 8);
            List<StepTurn> turns = new ArrayList<>();
            JSONArray appsCatalog = null;
            AgentSessionGuard sessionGuard = new AgentSessionGuard();
            String lastExecutedAction = "";

            // Flags adaptativos de compatibilidade com /agent/step caso o servidor imponha restrições no schema
            boolean[] compatFlags = new boolean[]{
                AppSettings.sp(AgentService.this).getBoolean("agent_send_tools", true), // [0] enviar tools
                false,                                                                  // O servidor atual aceita apenas texto
                false                                                                   // O servidor descarta role tool
            };

            try {
                for (int step = 1; step <= maxSteps && !abort.get(); step++) {
                    AgentAccessibilityService a11y = AgentAccessibilityService.instance;
                    if (a11y == null) throw new Exception("Serviço de acessibilidade desligado.");

                    updateRunningStatus("Passo " + step + "/" + maxSteps + " · A ler ecrã…");
                    if (appsCatalog == null) appsCatalog = a11y.listInstalledAppsJson(goal);

                    setOverlayTemporarilyHidden(true);
                    sleepQuiet(90);
                    AgentAccessibilityService.ScreenState state = a11y.inspectScreen();
                    for (int retryEmpty = 0; state.nodes.isEmpty() && retryEmpty < 2 && !abort.get(); retryEmpty++) {
                        sleepQuiet(450);
                        state = a11y.inspectScreen();
                    }
                    boolean sendVision = compatFlags[1] && AppSettings.sp(this).getBoolean("agent_vision", true);
                    String shotB64 = sendVision
                            ? a11y.captureAnnotatedScreenshotB64(state.nodes, state.width, state.height)
                            : "";
                    setOverlayTemporarilyHidden(false);

                    if (abort.get()) break;

                    long screenHash = sessionGuard.computeScreenHash(state);
                    AgentSessionGuard.GuardVerdict screenCheck =
                            sessionGuard.onScreenInspected(state, screenHash, lastExecutedAction);
                    if (screenCheck.abortLoop) {
                        finishWithNotice(screenCheck.title, screenCheck.reason);
                        return;
                    }

                    updateRunningStatus("Passo " + step + " · A aguardar /agent/step…");
                    if (!awaitControls(a11y)) return;

                    String compactUserPrompt = buildStepUserText(goal, step, maxSteps, state,
                            step == 1 ? appsCatalog : null, turns, compatFlags[2]);

                    StepResponse stepResp = requestServerStepWithCompat(
                            sessionId, step, state, compactUserPrompt, shotB64, turns, compatFlags);
                    if (abort.get()) break;

                    JSONObject decision = stepResp.decision;
                    String action = decision.optString("action", "").trim();
                    String thought = decision.optString("thought", "").trim();
                    int nodeId = decision.optInt("node_id", -1);
                    int x = decision.optInt("x", -1);
                    int y = decision.optInt("y", -1);
                    int x2 = decision.optInt("x2", -1);
                    int y2 = decision.optInt("y2", -1);
                    String text = decision.optString("text", "");
                    String urlTarget = decision.optString("url", text);
                    String pkg = decision.optString("package", text);
                    String dir = decision.optString("direction", "up");
                    int waitMs = decision.optInt("wait_ms", 2000);
                    boolean submit = decision.optBoolean("submit", false);
                    boolean modelCrit = decision.optBoolean("critical", false);
                    String critReason = decision.optString("critical_reason", "");
                    String message = decision.optString("message", thought);

                    if ("done".equals(action)) {
                        finishWithNotice("✅ Concluído", message.isEmpty() ? "Tarefa concluída." : message);
                        return;
                    }
                    if ("fail".equals(action)) {
                        finishWithNotice("⚠️ Não concluído", message.isEmpty() ? "O agente não conseguiu concluir." : message);
                        return;
                    }
                    if ("unknown_tool".equals(action)) {
                        JSONObject errRes = new JSONObject()
                                .put("ok", false)
                                .put("error", decision.optString("error", "Ferramenta desconhecida."));
                        recordTurn(turns, compactUserPrompt, stepResp, errRes);
                        lastExecutedAction = action;
                        continue;
                    }
                    if ("ask_user".equals(action)) {
                        int c = askCriticalConfirmation(message.isEmpty() ? "Confirmas continuar?" : message);
                        if (c == CONFIRM_STOP || abort.get()) {
                            finishWithNotice("⏹ Parado", "Execução cancelada pelo utilizador.");
                            return;
                        }
                        if (c == CONFIRM_SKIP && sessionGuard.recordAskUserRefusalAndShouldAbort()) {
                            finishWithNotice("🛑 Recusado", "O utilizador recusou continuar a ação.");
                            return;
                        }
                        JSONObject askRes = new JSONObject()
                                .put("ok", c == CONFIRM_APPROVE)
                                .put("user_confirmed", c == CONFIRM_APPROVE);
                        if (c == CONFIRM_SKIP) {
                            askRes.put("refused_by_user", true)
                                  .put("reason", "O utilizador recusou. NÃO executes a ação proposta; conclui com 'done' se não houver alternativa pedida.");
                        }
                        recordTurn(turns, compactUserPrompt, stepResp, askRes);
                        lastExecutedAction = action;
                        continue;
                    }

                    AgentAccessibilityService.NodeSnap snap = nodeId > 0 ? a11y.getNodeSnap(nodeId) : null;
                    // O alvo avaliado deve ser também o alvo efetivamente usado pelo gesto.
                    if (snap != null && ("tap".equals(action) || "click".equals(action)
                            || "long_press".equals(action) || "double_tap".equals(action)
                            || "type".equals(action) || "type_text".equals(action) || "input_text".equals(action))) {
                        x = -1;
                        y = -1;
                    }
                    String resolvedTargetPkg = ("open_app".equals(action) || "launch".equals(action))
                            ? a11y.resolveAppPackage(pkg) : "";
                    String policyTextOrUrl = "open_url".equals(action) ? urlTarget
                            : (("open_app".equals(action) || "launch".equals(action)) ? pkg : text);

                    AgentPolicy.Decision policy = AgentPolicy.evaluate(
                            this, goal, action, state.foregroundPkg, state.foregroundClass,
                            resolvedTargetPkg, snap, x, y, policyTextOrUrl, submit, modelCrit, critReason);

                    if (policy.verdict == AgentPolicy.Verdict.BLOCK) {
                        finishWithNotice("🛑 Bloqueado por Segurança", policy.reason);
                        return;
                    }

                    AgentSessionGuard.GuardVerdict preCheck = sessionGuard.checkBeforeExecution(
                            policy, action, resolvedTargetPkg, state.foregroundPkg, snap, x, y, screenHash);
                    if (preCheck.abortLoop) {
                        finishWithNotice(preCheck.title, preCheck.reason);
                        return;
                    }
                    if (!preCheck.proceed) {
                        JSONObject loopRes = new JSONObject()
                                .put("ok", false)
                                .put("blocked_repeat", true)
                                .put("reason", preCheck.reason);
                        recordTurn(turns, compactUserPrompt, stepResp, loopRes);
                        lastExecutedAction = action;
                        continue;
                    }

                    if (policy.verdict == AgentPolicy.Verdict.CONFIRM) {
                        int choice = askCriticalConfirmation(policy.reason
                                + (thought.isEmpty() ? "" : "\n\nPlano: " + thought));
                        if (choice == CONFIRM_STOP || abort.get()) {
                            finishWithNotice("⏹ Cancelado", "Ação cancelada pelo utilizador.");
                            return;
                        }
                        if (choice == CONFIRM_SKIP) {
                            sessionGuard.recordRefusal(policy, action, resolvedTargetPkg,
                                    state.foregroundPkg, snap, x, y);
                            if (step == 1 && ("open_app".equals(action) || "launch".equals(action) || "open_url".equals(action))) {
                                finishWithNotice("🛑 Ação recusada", "Abertura recusada pelo utilizador.");
                                return;
                            }
                            JSONObject skipRes = new JSONObject()
                                    .put("ok", false)
                                    .put("refused_by_user", true)
                                    .put("reason", "RECUSADO PELO UTILIZADOR: Esta ação está bloqueada nesta sessão. NÃO voltes a tentar este botão/app; conclui com 'done' se o resto da tarefa estiver pronto.");
                            recordTurn(turns, compactUserPrompt, stepResp, skipRes);
                            lastExecutedAction = action;
                            continue;
                        }
                    }

                    updateRunningStatus("Passo " + step + " · " + (thought.isEmpty() ? action : thought));
                    if (!awaitControls(a11y) || abort.get()) return;
                    boolean ok = executeAction(a11y, action, nodeId, x, y, x2, y2, text, pkg, urlTarget, dir, submit, waitMs);
                    lastExecutedAction = action;

                    AgentSessionGuard.GuardVerdict postCheck =
                            sessionGuard.afterExecution(action, policy.signature, ok, screenHash);

                    JSONObject execRes = new JSONObject()
                            .put("ok", ok)
                            .put("action", action)
                            .put("node_id", nodeId);
                    if (!ok) {
                        execRes.put("note", "Elemento não encontrado ou gesto falhou; NÃO repitas o mesmo node_id sem o ecrã mudar.");
                    }
                    recordTurn(turns, compactUserPrompt, stepResp, execRes);

                    if (postCheck.abortLoop) {
                        finishWithNotice(postCheck.title, postCheck.reason);
                        return;
                    }

                    sleepQuiet(("open_app".equals(action) || "launch".equals(action) || "open_url".equals(action)) ? 1600 : 950);
                }

                if (!abort.get()) {
                    finishWithNotice("⏱ Limite atingido", "Atingido o limite máximo de " + maxSteps + " passos.");
                }
            } catch (Exception e) {
                if (!abort.get()) {
                    finishWithNotice("⚠️ Erro no Agente",
                            e.getMessage() == null ? "Sem ligação ao servidor. Tens o Tailscale ligado?" : e.getMessage());
                }
            } finally {
                activeConn = null;
                running.set(false);
                if (AppSettings.sp(AgentService.this).getBoolean("agent_overlay", false)) {
                    switchToIdleMode();
                } else {
                    removeOverlay();
                    stopForeground(true);
                    stopSelf();
                }
            }
        }, "ody-agent-loop");
        worker.start();
    }

    private boolean awaitControls(AgentAccessibilityService a11y) {
        for (int i = 0; i < 12 && !abort.get(); i++) {
            if (Settings.canDrawOverlays(this) && a11y.hasAgentControls()) return true;
            sleepQuiet(100);
        }
        if (!abort.get()) finishWithNotice("Agente suspenso",
                "Os controlos estão ocultos. Volta a um ecrã que os permita e inicia outra tarefa.");
        return false;
    }

    private static void recordTurn(List<StepTurn> turns, String userPromptCompact,
                                   StepResponse resp, JSONObject primaryResult) {
        JSONArray toolResults = new JSONArray();
        if (resp.rawToolCalls != null && resp.rawToolCalls.length() > 0) {
            for (int i = 0; i < resp.rawToolCalls.length(); i++) {
                JSONObject tc = resp.rawToolCalls.optJSONObject(i);
                if (tc == null) continue;
                String tcId = tc.optString("id", "call_" + i);
                JSONObject fn = tc.optJSONObject("function");
                String tcName = fn != null ? fn.optString("name", "action") : tc.optString("name", "action");
                String contentStr;
                if (i == 0 || tcId.equals(resp.primaryToolCallId)) {
                    contentStr = primaryResult.toString();
                } else {
                    // Responder a eventuais tool_calls secundários no mesmo turno para nunca causar HTTP 400
                    contentStr = "{\"ok\":false,\"deferred\":true,\"reason\":\"Apenas 1 ação UI por leitura de ecrã; avalia o ecrã atualizado.\"}";
                }
                try {
                    toolResults.put(new JSONObject()
                            .put("tool_call_id", tcId)
                            .put("name", tcName)
                            .put("content", contentStr));
                } catch (Exception ignored) { }
            }
        }
        turns.add(new StepTurn(
                userPromptCompact,
                resp.assistantText,
                resp.assistantFallbackText,
                resp.rawToolCalls,
                toolResults,
                primaryResult.toString()));

        while (turns.size() > MAX_HISTORY_TURNS) {
            turns.remove(0);
        }
    }

    private boolean executeAction(AgentAccessibilityService a11y, String action, int nodeId,
                                  int x, int y, int x2, int y2, String text, String pkg,
                                  String url, String dir, boolean submit, int waitMs) {
        if (action == null) return false;
        switch (action) {
            case "open_app":
            case "launch":
                return a11y.openApp(pkg);
            case "open_url":
                return a11y.openUrl(url);
            case "tap":
            case "click":
                return a11y.tap(nodeId, x, y);
            case "long_press":
                return a11y.longPress(nodeId, x, y);
            case "double_tap":
                return a11y.doubleTap(nodeId, x, y);
            case "type":
            case "type_text":
            case "input_text":
                return a11y.typeText(nodeId, x, y, text, submit);
            case "swipe_coords":
                return a11y.gestureStroke(x, y, x2, y2, 350);
            case "scroll":
                return a11y.swipeDirection(dir);
            case "back":
                return a11y.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK);
            case "home":
                return a11y.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME);
            case "recents":
                return a11y.performGlobalAction(AccessibilityService.GLOBAL_ACTION_RECENTS);
            case "notifications":
                return a11y.performGlobalAction(AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS);
            case "wait":
                sleepQuiet(Math.max(400, Math.min(5000, waitMs)));
                return true;
            default:
                return false;
        }
    }

    // ---- Construção do Pedido `messages` + `tools` e Fallback Automático HTTP 400/422 ----

    private static String buildSystemPrompt(int width, int height) {
        return "És o Agente Android do Odysseus a controlar um smartphone Android (" + width + "x" + height + " px).\n"
                + "Em cada passo recebes o objetivo do utilizador, a aplicação em primeiro plano, a árvore de elementos interativos (os IDs numéricos coincidem com as etiquetas na captura de ecrã) e opcionalmente a imagem do ecrã.\n"
                + "Regras:\n"
                + "1. Executa APENAS UMA ação de cada vez invocando uma ferramenta (`tool_calls`). Caso não tenhas ferramentas ativas, responde com um único objeto JSON: "
                + "{\"thought\":\"...\",\"action\":\"open_app|open_url|tap|long_press|double_tap|type|scroll|back|home|recents|notifications|wait|ask_user|done|fail\","
                + "\"node_id\":-1,\"x\":-1,\"y\":-1,\"text\":\"\",\"package\":\"\",\"url\":\"\",\"direction\":\"up|down|left|right\",\"submit\":false,\"critical\":false,\"critical_reason\":\"\",\"message\":\"\"}.\n"
                + "2. Prefere sempre `node_id` da árvore UI em vez de coordenadas `(x, y)` soltas.\n"
                + "3. Para abrir endereços web (`http://` ou `https://`), usa diretamente `open_url` em vez de abrir o navegador manualmente.\n"
                + "4. Executa autonomamente (`critical: false`, SEM `ask_user`) ações rotineiras quando a intenção do utilizador é clara, como abrir aplicações normais (ex.: Spotify, YouTube, navegador), navegar para URLs ou pesquisar.\n"
                + "5. Define `critical: true` (ou usa `ask_user`) APENAS para: pagamentos/transferências/compras, acesso a gestores de palavras-passe/autenticadores, envio ou publicação efetiva de mensagens/emails/publicações, e eliminação de dados.\n"
                + "6. Se uma ação for recusada pelo utilizador (`refused_by_user: true`) ou falhar num elemento, NUNCA a repitas no mesmo alvo.\n"
                + "7. Quando o objetivo estiver concluído (ou se o utilizador fez apenas uma pergunta sobre o ecrã), chama `done` com a resposta em `message`.";
    }

    private static String buildStepUserText(String goal, int step, int maxSteps,
                                            AgentAccessibilityService.ScreenState st,
                                            JSONArray appsCatalog, List<StepTurn> turns,
                                            boolean toolRoleEnabled) {
        StringBuilder sb = new StringBuilder(2048);
        sb.append("Objetivo: ").append(goal)
          .append("\nPasso: ").append(step).append('/').append(maxSteps)
          .append("\nApp em primeiro plano: ").append(st.foregroundApp)
          .append(" (").append(st.foregroundPkg).append(')');

        if (!turns.isEmpty() && (!toolRoleEnabled || turns.get(turns.size() - 1).rawToolCalls == null)) {
            StepTurn prev = turns.get(turns.size() - 1);
            sb.append("\nResultado do passo anterior: ").append(prev.plainResultSummary);
        }

        if (appsCatalog != null && appsCatalog.length() > 0) {
            sb.append("\nApps instaladas: ");
            for (int i = 0; i < appsCatalog.length(); i++) {
                JSONObject a = appsCatalog.optJSONObject(i);
                if (a == null) continue;
                if (i > 0) sb.append(", ");
                sb.append(a.optString("name")).append(" [").append(a.optString("package")).append(']');
            }
        }

        sb.append("\nÁrvore UI interativa (").append(st.width).append('x').append(st.height)
          .append("): ").append(st.uiTree.toString());
        return sb.toString();
    }

    private static JSONArray buildAndroidToolsSchema() throws Exception {
        JSONArray tools = new JSONArray();

        tools.put(fnTool("open_app",
                "Abre uma aplicação instalada pelo package name ou pelo nome visível.",
                new JSONObject()
                        .put("package", prop("string", "Package name (ex.: com.spotify.music) ou nome da app (ex.: Spotify)."))
                        .put("thought", prop("string", "Breve motivo deste passo.")),
                new String[]{"package"}));

        tools.put(fnTool("open_url",
                "Abre diretamente um endereço web (http:// ou https://) no navegador predefinido.",
                new JSONObject()
                        .put("url", prop("string", "URL completo a abrir (ex.: https://www.publico.pt)."))
                        .put("thought", prop("string", "Breve motivo deste passo.")),
                new String[]{"url"}));

        tools.put(fnTool("tap",
                "Toca num elemento interativo pelo node_id da árvore UI (preferido) ou coordenadas (x, y).",
                new JSONObject()
                        .put("node_id", prop("integer", "ID numérico do elemento na árvore UI / etiqueta na captura."))
                        .put("x", prop("integer", "Coordenada X opcional."))
                        .put("y", prop("integer", "Coordenada Y opcional."))
                        .put("critical", prop("boolean", "True se confirmar pagamento, compra, envio ou eliminação."))
                        .put("critical_reason", prop("string", "Explicação caso critical=true."))
                        .put("thought", prop("string", "Breve motivo deste passo.")),
                new String[]{}));

        tools.put(fnTool("long_press",
                "Faz pressão longa num elemento pelo node_id ou coordenadas (x, y).",
                new JSONObject()
                        .put("node_id", prop("integer", "ID numérico do elemento."))
                        .put("x", prop("integer", "Coordenada X opcional."))
                        .put("y", prop("integer", "Coordenada Y opcional."))
                        .put("critical", prop("boolean", "True se for ação sensível."))
                        .put("critical_reason", prop("string", "Motivo se critical=true."))
                        .put("thought", prop("string", "Breve motivo deste passo.")),
                new String[]{}));

        tools.put(fnTool("double_tap",
                "Faz duplo toque num elemento pelo node_id ou coordenadas (x, y).",
                new JSONObject()
                        .put("node_id", prop("integer", "ID numérico do elemento."))
                        .put("x", prop("integer", "Coordenada X opcional."))
                        .put("y", prop("integer", "Coordenada Y opcional."))
                        .put("thought", prop("string", "Breve motivo deste passo.")),
                new String[]{}));

        tools.put(fnTool("type_text",
                "Escreve texto num campo editável (tocando opcionalmente em node_id antes de escrever).",
                new JSONObject()
                        .put("text", prop("string", "Texto a introduzir."))
                        .put("node_id", prop("integer", "ID do campo editável na árvore UI."))
                        .put("submit", prop("boolean", "True para premir Enter/Pesquisar após escrever."))
                        .put("critical", prop("boolean", "True se submeter mensagem/formulário sensível."))
                        .put("critical_reason", prop("string", "Motivo se critical=true."))
                        .put("thought", prop("string", "Breve motivo deste passo.")),
                new String[]{"text"}));

        tools.put(fnTool("swipe",
                "Desliza o dedo no ecrã. Usa direction='up' para avançar para baixo numa lista/página, 'down' para subir ao topo, 'left' ou 'right', ou coordenadas x1,y1 -> x2,y2.",
                new JSONObject()
                        .put("direction", new JSONObject().put("type", "string")
                                .put("enum", new JSONArray().put("up").put("down").put("left").put("right")))
                        .put("x1", prop("integer", "X inicial opcional."))
                        .put("y1", prop("integer", "Y inicial opcional."))
                        .put("x2", prop("integer", "X final opcional."))
                        .put("y2", prop("integer", "Y final opcional."))
                        .put("thought", prop("string", "Breve motivo deste passo.")),
                new String[]{}));

        tools.put(fnTool("navigate",
                "Executa um botão global do Android: back, home, recents, notifications ou wait.",
                new JSONObject()
                        .put("target", new JSONObject().put("type", "string")
                                .put("enum", new JSONArray().put("back").put("home").put("recents").put("notifications").put("wait")))
                        .put("thought", prop("string", "Breve motivo deste passo.")),
                new String[]{"target"}));

        tools.put(fnTool("ask_user",
                "Pede confirmação ou esclarecimento ao utilizador no ecrã antes de prosseguir.",
                new JSONObject()
                        .put("message", prop("string", "Pergunta ou confirmação clara para o utilizador.")),
                new String[]{"message"}));

        tools.put(fnTool("done",
                "Conclui a tarefa e apresenta o resultado final ao utilizador (ou failed=true se impossível).",
                new JSONObject()
                        .put("message", prop("string", "Resumo final ou resposta para o utilizador."))
                        .put("failed", prop("boolean", "True apenas se a tarefa falhou.")),
                new String[]{"message"}));

        return tools;
    }

    private static JSONObject prop(String type, String desc) throws Exception {
        return new JSONObject().put("type", type).put("description", desc);
    }

    private static JSONObject fnTool(String name, String desc, JSONObject props, String[] req) throws Exception {
        JSONArray reqArr = new JSONArray();
        for (String r : req) reqArr.put(r);
        JSONObject params = new JSONObject()
                .put("type", "object")
                .put("properties", props);
        if (reqArr.length() > 0) params.put("required", reqArr);
        return new JSONObject()
                .put("type", "function")
                .put("function", new JSONObject()
                        .put("name", name)
                        .put("description", desc)
                        .put("parameters", params));
    }

    private static JSONObject buildStepRequestPayload(String sessionId,
                                                      AgentAccessibilityService.ScreenState st,
                                                      String currentUserText,
                                                      String shotB64,
                                                      List<StepTurn> turns,
                                                      String model,
                                                      boolean includeTools,
                                                      boolean allowMultimodalArray,
                                                      boolean allowToolRole) throws Exception {
        JSONArray messages = new JSONArray();
        messages.put(new JSONObject()
                .put("role", "system")
                .put("content", buildSystemPrompt(st.width, st.height)));

        for (StepTurn t : turns) {
            messages.put(new JSONObject()
                    .put("role", "user")
                    .put("content", t.userPromptCompact));

            if (allowToolRole && t.rawToolCalls != null && t.rawToolCalls.length() > 0) {
                messages.put(new JSONObject()
                        .put("role", "assistant")
                        .put("content", t.assistantText)
                        .put("tool_calls", t.rawToolCalls));
                for (int i = 0; i < t.toolResults.length(); i++) {
                    JSONObject tr = t.toolResults.getJSONObject(i);
                    messages.put(new JSONObject()
                            .put("role", "tool")
                            .put("tool_call_id", tr.getString("tool_call_id"))
                            .put("name", tr.getString("name"))
                            .put("content", tr.getString("content")));
                }
            } else {
                messages.put(new JSONObject()
                        .put("role", "assistant")
                        .put("content", t.assistantFallbackText + "\nResultado da ação: " + t.plainResultSummary));
            }
        }

        if (allowMultimodalArray && shotB64 != null && !shotB64.isEmpty()) {
            JSONArray contentParts = new JSONArray()
                    .put(new JSONObject().put("type", "text").put("text", currentUserText))
                    .put(new JSONObject().put("type", "image_url")
                            .put("image_url", new JSONObject().put("url", "data:image/jpeg;base64," + shotB64)));
            messages.put(new JSONObject().put("role", "user").put("content", contentParts));
        } else {
            messages.put(new JSONObject().put("role", "user").put("content", currentUserText));
        }

        JSONObject root = new JSONObject()
                .put("messages", messages)
                .put("stream", true);
        if (!model.isEmpty()) {
            root.put("model", model);
        }
        if (includeTools) {
            root.put("tools", buildAndroidToolsSchema());
            root.put("tool_choice", "auto");
        }
        return root;
    }

    private StepResponse requestServerStepWithCompat(String sessionId, int step,
                                                     AgentAccessibilityService.ScreenState state,
                                                     String currentUserText, String shotB64,
                                                     List<StepTurn> turns, boolean[] compatFlags) throws Exception {
        String url = resolveEndpointUrl(this);
        String base = AppSettings.serverUrl(this);
        String cookie = serverCookieForUrl(base, url);
        String authHeader = AppSettings.agentAuthHeader(this);
        String authVal = "/api/android-agent/step".equals(AppSettings.agentEndpoint(this)) ? "" : AppSettings.formatAgentAuthValue(this);
        String model = AppSettings.sp(this).getString("agent_model", "").trim();

        boolean tryTools = compatFlags[0];
        boolean tryMultimodal = compatFlags[1];
        boolean tryToolRole = compatFlags[2];

        Exception last4xx = null;
        for (int attempt = 0; attempt < 3 && !abort.get(); attempt++) {
            JSONObject payloadObj = buildStepRequestPayload(
                    sessionId, state, currentUserText, shotB64, turns,
                    model, tryTools, tryMultimodal, tryToolRole);
            if (AppSettings.sp(this).getBoolean("agent_server_model", false) && "/api/android-agent/step".equals(AppSettings.agentEndpoint(this))) {
                payloadObj.put("endpoint_id", AppSettings.sp(this).getString("agent_endpoint_id", ""));
            }
            try {
                StepResponse ok = executeSingleStepHttp(url, cookie, authHeader, authVal, payloadObj.toString(), step);
                compatFlags[0] = tryTools;
                compatFlags[1] = tryMultimodal;
                compatFlags[2] = tryToolRole;
                return ok;
            } catch (Http4xxSchemaException e400) {
                last4xx = e400;
                if (attempt == 0 && tryTools) {
                    // Tentativa 2: servidor /agent/step pode injetar as suas próprias tools e recusar `tools` externo
                    tryTools = false;
                    continue;
                }
                if ((tryMultimodal && shotB64 != null && !shotB64.isEmpty()) || (tryToolRole && !turns.isEmpty())) {
                    // Tentativa 3: servidor /agent/step aceita apenas content String e roles básicos
                    tryTools = false;
                    tryMultimodal = false;
                    tryToolRole = false;
                    continue;
                }
                break;
            }
        }
        throw last4xx != null ? last4xx : new Exception("Falha ao comunicar com /agent/step.");
    }

    private static final class Http4xxSchemaException extends Exception {
        Http4xxSchemaException(String msg) { super(msg); }
    }

    private StepResponse executeSingleStepHttp(String url, String cookie, String authHeader,
                                               String authVal, String bodyStr, int step) throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        activeConn = conn;
        try {
            conn.setRequestMethod("POST");
            conn.setInstanceFollowRedirects(false);
            conn.setConnectTimeout(12000);
            conn.setReadTimeout(120000);
            conn.setUseCaches(false);
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Accept", "text/event-stream, application/json");
            conn.setRequestProperty("Cache-Control", "no-cache");
            conn.setRequestProperty("Accept-Encoding", "identity");
            if (!authVal.isEmpty()) conn.setRequestProperty(authHeader, authVal);
            if (cookie != null && !cookie.isEmpty()) conn.setRequestProperty("Cookie", cookie);
            conn.setDoOutput(true);

            byte[] payload = bodyStr.getBytes(StandardCharsets.UTF_8);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(payload);
            }

            int code = conn.getResponseCode();
            if (code == 401 || code == 403) {
                throw new Exception("Autenticação recusada (HTTP " + code + ") em " + url
                        + ". Verifica o Token nas Definições da app.");
            }
            if (code == 404) {
                throw new Exception("Rota não encontrada (HTTP 404): " + url
                        + ". Confirma /agent/step nas Definições.");
            }
            if (code == 400 || code == 422) {
                String errTxt = readAllSmall(conn.getErrorStream());
                throw new Http4xxSchemaException("Servidor respondeu HTTP " + code
                        + (errTxt.isEmpty() ? "" : ": " + errTxt));
            }
            if (code < 200 || code >= 400) {
                String errTxt = readAllSmall(conn.getErrorStream());
                throw new Exception("Servidor respondeu HTTP " + code
                        + (errTxt.isEmpty() ? "" : ": " + errTxt));
            }

            String ct = conn.getHeaderField("Content-Type");
            boolean isSse = ct != null && ct.toLowerCase(Locale.ROOT).contains("text/event-stream");
            if (isSse) {
                return consumeSseOrJsonStream(conn.getInputStream(), step);
            }

            String rawBody = readAllBounded(conn.getInputStream(), 2 * 1024 * 1024);
            String trimmed = rawBody.trim();
            if (trimmed.startsWith("event:") || trimmed.startsWith("data:") || trimmed.startsWith(":")) {
                return consumeSseOrJsonStream(
                        new ByteArrayInputStream(rawBody.getBytes(StandardCharsets.UTF_8)), step);
            }
            return parseSingleJsonBody(trimmed, step);
        } finally {
            if (activeConn == conn) activeConn = null;
            conn.disconnect();
        }
    }

    // ---- Leitor SSE Completo: `tool_calls` (deltas + objetos) e Fragmentos de Texto ----

    private StepResponse consumeSseOrJsonStream(InputStream in, int step) throws Exception {
        if (in == null) throw new Exception("Stream SSE vazio.");
        final List<ToolCallAccum> toolCalls = new ArrayList<>();
        final StringBuilder contentBuf = new StringBuilder();
        final StringBuilder thoughtBuf = new StringBuilder();
        JSONObject directAction = null;

        try (BufferedReader br = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            String eventType = "message";
            StringBuilder dataBuf = new StringBuilder();
            String line;

            while (!abort.get() && (line = br.readLine()) != null) {
                if (line.startsWith(":")) continue; // Heartbeat SSE

                if (line.isEmpty()) {
                    if (dataBuf.length() > 0) {
                        String data = dataBuf.toString().trim();
                        dataBuf.setLength(0);
                        if ("[DONE]".equals(data)) break;

                        JSONObject maybeDirect = processSseFrame(
                                eventType, data, step, toolCalls, contentBuf, thoughtBuf);
                        if (maybeDirect != null) {
                            if (maybeDirect.optBoolean("__stream_end", false)) {
                                maybeDirect.remove("__stream_end");
                                if (maybeDirect.has("action")) directAction = maybeDirect;
                                break;
                            }
                            directAction = maybeDirect;
                        }
                    }
                    eventType = "message";
                    continue;
                }

                if (line.startsWith("event:")) {
                    eventType = line.substring(6).trim();
                } else if (line.startsWith("data:")) {
                    String part = line.substring(5);
                    if (part.startsWith(" ")) part = part.substring(1);
                    if (dataBuf.length() > 0) dataBuf.append('\n');
                    dataBuf.append(part);
                }
            }

            if (dataBuf.length() > 0 && !abort.get()) {
                String rem = dataBuf.toString().trim();
                if (!"[DONE]".equals(rem)) {
                    JSONObject maybeDirect = processSseFrame(
                            eventType, rem, step, toolCalls, contentBuf, thoughtBuf);
                    if (maybeDirect != null && maybeDirect.has("action")) {
                        maybeDirect.remove("__stream_end");
                        directAction = maybeDirect;
                    }
                }
            }
        }

        return buildStepResponseFromAccumulated(step, toolCalls, contentBuf.toString(), thoughtBuf.toString(), directAction);
    }

    private JSONObject processSseFrame(String eventType, String data, int step,
                                       List<ToolCallAccum> toolCalls,
                                       StringBuilder contentBuf,
                                       StringBuilder thoughtBuf) throws Exception {
        if (data.isEmpty() || "[DONE]".equals(data)) {
            return new JSONObject().put("__stream_end", true);
        }
        String ev = eventType == null ? "message" : eventType.toLowerCase(Locale.ROOT);

        if ("error".equals(ev)) {
            if (data.startsWith("{")) {
                JSONObject errObj = new JSONObject(data);
                throw new Exception(errObj.optString("error", errObj.optString("message", data)));
            }
            throw new Exception(data);
        }

        // Fragmento de texto puro (não-JSON objeto) em `data:`
        if (!data.startsWith("{") && !data.startsWith("[")) {
            String piece = data;
            if (data.startsWith("\"") && data.endsWith("\"") && data.length() >= 2) {
                try { piece = new JSONArray("[" + data + "]").getString(0); }
                catch (Exception ignored) { }
            }
            if ("thought".equals(ev) || "thinking".equals(ev) || "reasoning".equals(ev)
                    || "status".equals(ev) || "progress".equals(ev)) {
                thoughtBuf.append(piece);
                updateRunningStatus("Passo " + step + " · " + piece);
            } else if (!"done".equals(ev) && !"end".equals(ev) && !"ping".equals(ev)) {
                contentBuf.append(piece);
                updateRunningPreviewThrottled(step, contentBuf.toString());
            }
            if ("done".equals(ev) || "end".equals(ev) || "complete".equals(ev)) {
                return new JSONObject().put("__stream_end", true);
            }
            return null;
        }

        // Array direto de tool_calls
        if (data.startsWith("[")) {
            JSONArray arr = new JSONArray(data);
            ingestToolCallsArray(toolCalls, arr);
            return null;
        }

        JSONObject obj = new JSONObject(data);
        String typeField = obj.optString("type", ev).toLowerCase(Locale.ROOT);

        // 1) Erros explícitos
        if ("error".equals(typeField) || (obj.has("error") && !obj.isNull("error") && !obj.has("action"))) {
            Object errVal = obj.opt("error");
            if (errVal instanceof JSONObject) {
                throw new Exception(((JSONObject) errVal).optString("message", errVal.toString()));
            }
            throw new Exception(obj.optString("message", obj.optString("detail", String.valueOf(errVal))));
        }

        // 2) Formato OpenAI / LiteLLM / vLLM (`choices` com `delta` ou `message`) — em qualquer URL (/agent/step incluído!)
        if (obj.has("choices")) {
            JSONArray choices = obj.optJSONArray("choices");
            if (choices != null && choices.length() > 0) {
                JSONObject c0 = choices.optJSONObject(0);
                if (c0 != null) {
                    JSONObject delta = c0.optJSONObject("delta");
                    if (delta != null) {
                        ingestMessageOrDeltaObject(delta, step, true, toolCalls, contentBuf, thoughtBuf);
                    }
                    JSONObject message = c0.optJSONObject("message");
                    if (message != null) {
                        ingestMessageOrDeltaObject(message, step, false, toolCalls, contentBuf, thoughtBuf);
                    }
                }
            }
            return null;
        }

        // 3) Formato Anthropic / Claude (`content_block_start` / `content_block_delta` / `message_stop`)
        if ("content_block_start".equals(typeField)) {
            int idx = obj.optInt("index", toolCalls.size());
            JSONObject cb = obj.optJSONObject("content_block");
            if (cb != null && ("tool_use".equals(cb.optString("type")) || "function".equals(cb.optString("type")))) {
                ToolCallAccum acc = getOrCreateToolAccum(toolCalls, idx, cb.optString("id", ""));
                acc.mergeId(cb.optString("id", ""));
                acc.mergeName(cb.optString("name", ""));
                JSONObject inp = cb.optJSONObject("input");
                if (inp != null && inp.length() > 0) acc.setArgsObject(inp);
            }
            return null;
        }
        if ("content_block_delta".equals(typeField)) {
            int idx = obj.optInt("index", 0);
            JSONObject delta = obj.optJSONObject("delta");
            if (delta != null) {
                String dt = delta.optString("type", "");
                if ("input_json_delta".equals(dt)) {
                    ToolCallAccum acc = getOrCreateToolAccum(toolCalls, Math.max(0, toolCalls.size() - 1), "");
                    acc.appendArgsChunk(delta.optString("partial_json", ""));
                } else if ("text_delta".equals(dt) || delta.has("text")) {
                    contentBuf.append(delta.optString("text", ""));
                    updateRunningPreviewThrottled(step, contentBuf.toString());
                } else if ("thinking_delta".equals(dt) || delta.has("thinking")) {
                    thoughtBuf.append(delta.optString("thinking", ""));
                }
            }
            return null;
        }

        // 4) Formato OpenAI Responses API (`response.output_item.*` / `response.function_call_arguments.*` / `response.output_text.delta`)
        if (typeField.startsWith("response.")) {
            if ("response.output_item.added".equals(typeField) || "response.output_item.done".equals(typeField)) {
                JSONObject item = obj.optJSONObject("item");
                if (item != null && "function_call".equals(item.optString("type"))) {
                    int idx = obj.optInt("output_index", toolCalls.size());
                    ToolCallAccum acc = getOrCreateToolAccum(toolCalls, idx, item.optString("call_id", item.optString("id", "")));
                    acc.mergeId(item.optString("call_id", item.optString("id", "")));
                    acc.mergeName(item.optString("name", ""));
                    String args = item.optString("arguments", "");
                    if (!args.isEmpty() && "response.output_item.done".equals(typeField)) {
                        acc.argsBuf.setLength(0);
                        acc.appendArgsChunk(args);
                    }
                }
            } else if ("response.function_call_arguments.delta".equals(typeField)) {
                int idx = obj.optInt("output_index", Math.max(0, toolCalls.size() - 1));
                getOrCreateToolAccum(toolCalls, idx, "").appendArgsChunk(obj.optString("delta", ""));
            } else if ("response.function_call_arguments.done".equals(typeField)) {
                int idx = obj.optInt("output_index", Math.max(0, toolCalls.size() - 1));
                ToolCallAccum acc = getOrCreateToolAccum(toolCalls, idx, "");
                acc.mergeName(obj.optString("name", ""));
                String fullArgs = obj.optString("arguments", "");
                if (!fullArgs.isEmpty()) {
                    acc.argsBuf.setLength(0);
                    acc.appendArgsChunk(fullArgs);
                }
            } else if ("response.output_text.delta".equals(typeField)) {
                contentBuf.append(obj.optString("delta", ""));
                updateRunningPreviewThrottled(step, contentBuf.toString());
            } else if ("response.completed".equals(typeField)) {
                return new JSONObject().put("__stream_end", true);
            }
            return null;
        }

        // 5) `tool_calls` ou `tool_call` de topo em /agent/step personalizado
        if (obj.has("tool_calls") && obj.opt("tool_calls") instanceof JSONArray) {
            ingestToolCallsArray(toolCalls, obj.getJSONArray("tool_calls"));
        }
        if (obj.has("tool_call") && obj.opt("tool_call") instanceof JSONObject) {
            ingestSingleToolCallObject(toolCalls, obj.getJSONObject("tool_call"), toolCalls.size());
        }
        if ("tool_call".equals(typeField) || "function_call".equals(typeField) || "tool_use".equals(typeField)) {
            if (obj.has("name") || obj.has("function")) {
                ingestSingleToolCallObject(toolCalls, obj, obj.optInt("index", toolCalls.size()));
            }
        }
        if ("tool_call_delta".equals(typeField) || "function_call_delta".equals(typeField)) {
            ingestSingleToolCallObject(toolCalls, obj, obj.optInt("index", Math.max(0, toolCalls.size() - 1)));
        }

        // 6) Sub-objetos `delta` ou `message` de topo (comum em wrappers FastAPI de /agent/step)
        if (obj.opt("delta") instanceof JSONObject) {
            ingestMessageOrDeltaObject(obj.getJSONObject("delta"), step, true, toolCalls, contentBuf, thoughtBuf);
        }
        if (obj.opt("message") instanceof JSONObject) {
            ingestMessageOrDeltaObject(obj.getJSONObject("message"), step, false, toolCalls, contentBuf, thoughtBuf);
        }

        // 7) Eventos explícitos de pensamento / estado
        if ("thought".equals(typeField) || "thinking".equals(typeField)
                || "reasoning".equals(typeField) || "status".equals(typeField) || "progress".equals(typeField)) {
            String t = obj.optString("thought", obj.optString("thinking",
                    obj.optString("reasoning", obj.optString("text", obj.optString("message", "")))));
            if (!t.isEmpty()) {
                if (thoughtBuf.length() > 0) thoughtBuf.append(' ');
                thoughtBuf.append(t);
                updateRunningStatus("Passo " + step + " · " + t);
            }
            return null;
        }

        // 8) Fragmentos de texto em eventos JSON (`text`, `delta` string, `token`, `chunk`, `content`)
        if ((!obj.has("type") && obj.opt("delta") instanceof String)
                || "text".equals(typeField) || "text_delta".equals(typeField) || "delta".equals(typeField)
                || "token".equals(typeField) || "chunk".equals(typeField) || "content".equals(typeField)) {
            String piece = "";
            if (obj.opt("delta") instanceof String) piece = obj.optString("delta", "");
            else if (obj.opt("text") instanceof String) piece = obj.optString("text", "");
            else if (obj.opt("token") instanceof String) piece = obj.optString("token", "");
            else if (obj.opt("chunk") instanceof String) piece = obj.optString("chunk", "");
            else if (obj.opt("content") instanceof String) piece = obj.optString("content", "");
            if (!piece.isEmpty()) {
                contentBuf.append(piece);
                updateRunningPreviewThrottled(step, contentBuf.toString());
            }
            return null;
        }

        // Se `content` de topo existir como String num evento genérico sem `action`
        if (!obj.has("action") && obj.opt("content") instanceof String && !obj.has("message")) {
            String cStr = obj.optString("content", "");
            if (!cStr.isEmpty()) {
                mergeWholeOrDeltaText(contentBuf, cStr, "done".equals(typeField) || "final".equals(typeField));
                updateRunningPreviewThrottled(step, contentBuf.toString());
            }
        }

        // 9) Objeto de ação direta (`{"action": "tap", ...}` ou `{"decision": {...}}` ou `{"step": {...}}`)
        JSONObject unwrapped = unwrapActionObject(obj);
        if ("done".equals(ev) || "end".equals(ev) || "complete".equals(ev)
                || "message_stop".equals(typeField) || "step_done".equals(typeField)) {
            if (unwrapped != null) {
                unwrapped.put("__stream_end", true);
                return unwrapped;
            }
            return new JSONObject().put("__stream_end", true);
        }
        return unwrapped;
    }

    private StepResponse parseSingleJsonBody(String rawJson, int step) throws Exception {
        List<ToolCallAccum> toolCalls = new ArrayList<>();
        StringBuilder contentBuf = new StringBuilder();
        StringBuilder thoughtBuf = new StringBuilder();
        JSONObject direct = processSseFrame("message", rawJson, step, toolCalls, contentBuf, thoughtBuf);
        if (direct != null) direct.remove("__stream_end");
        return buildStepResponseFromAccumulated(step, toolCalls, contentBuf.toString(), thoughtBuf.toString(), direct);
    }

    private void ingestMessageOrDeltaObject(JSONObject m, int step, boolean isDelta,
                                            List<ToolCallAccum> toolCalls,
                                            StringBuilder contentBuf,
                                            StringBuilder thoughtBuf) throws Exception {
        if (m == null) return;

        // Reasoning / thinking
        String r = m.optString("reasoning_content", m.optString("reasoning", m.optString("thinking", "")));
        if (!r.isEmpty()) {
            thoughtBuf.append(r);
        }

        // Content (String ou Array multimodal de texto)
        Object cObj = m.opt("content");
        if (cObj instanceof String) {
            String s = (String) cObj;
            if (!s.isEmpty()) {
                mergeWholeOrDeltaText(contentBuf, s, !isDelta);
                updateRunningPreviewThrottled(step, contentBuf.toString());
            }
        } else if (cObj instanceof JSONArray) {
            JSONArray parts = (JSONArray) cObj;
            for (int i = 0; i < parts.length(); i++) {
                JSONObject p = parts.optJSONObject(i);
                if (p == null) continue;
                String pt = p.optString("type", "");
                if ("tool_use".equals(pt) || "function".equals(pt)) {
                    ingestSingleToolCallObject(toolCalls, p, i);
                } else if (p.has("text")) {
                    mergeWholeOrDeltaText(contentBuf, p.optString("text", ""), !isDelta);
                }
            }
        }

        // `tool_calls` array
        if (m.opt("tool_calls") instanceof JSONArray) {
            ingestToolCallsArray(toolCalls, m.getJSONArray("tool_calls"));
        }

        // Legacy `function_call`
        if (m.opt("function_call") instanceof JSONObject) {
            JSONObject fc = m.getJSONObject("function_call");
            ToolCallAccum acc = getOrCreateToolAccum(toolCalls, 0, "");
            acc.mergeName(fc.optString("name", ""));
            Object args = fc.opt("arguments");
            if (args instanceof JSONObject) acc.setArgsObject((JSONObject) args);
            else if (args instanceof String) acc.appendArgsChunk((String) args);
        }
    }

    private static void mergeWholeOrDeltaText(StringBuilder buf, String incoming, boolean isWholeMessage) {
        if (incoming == null || incoming.isEmpty()) return;
        if (!isWholeMessage || buf.length() == 0) {
            buf.append(incoming);
            return;
        }
        String cur = buf.toString();
        if (incoming.equals(cur)) return;
        if (incoming.startsWith(cur)) {
            buf.setLength(0);
            buf.append(incoming);
        }
    }

    private static void ingestToolCallsArray(List<ToolCallAccum> toolCalls, JSONArray arr) {
        if (arr == null) return;
        for (int i = 0; i < arr.length(); i++) {
            JSONObject tc = arr.optJSONObject(i);
            if (tc == null) continue;
            int idx = tc.optInt("index", i);
            ingestSingleToolCallObject(toolCalls, tc, idx);
        }
    }

    private static void ingestSingleToolCallObject(List<ToolCallAccum> toolCalls, JSONObject tc, int defaultIndex) {
        if (tc == null) return;
        String tcId = tc.optString("id", tc.optString("call_id", tc.optString("tool_call_id", "")));
        int idx = tc.optInt("index", defaultIndex);
        ToolCallAccum acc = getOrCreateToolAccum(toolCalls, idx, tcId);
        acc.mergeId(tcId);

        JSONObject fn = tc.optJSONObject("function");
        if (fn != null) {
            acc.mergeName(fn.optString("name", ""));
            ingestArgsField(acc, fn.opt("arguments"));
        } else {
            acc.mergeName(tc.optString("name", tc.optString("tool", "")));
            if (tc.has("arguments")) ingestArgsField(acc, tc.opt("arguments"));
            else if (tc.has("args")) ingestArgsField(acc, tc.opt("args"));
            else if (tc.has("input")) ingestArgsField(acc, tc.opt("input"));
            else if (tc.has("parameters")) ingestArgsField(acc, tc.opt("parameters"));
        }
    }

    private static void ingestArgsField(ToolCallAccum acc, Object args) {
        if (args == null || args == JSONObject.NULL) return;
        if (args instanceof JSONObject) {
            JSONObject jo = (JSONObject) args;
            if (jo.length() > 0 || acc.argsObj == null) acc.setArgsObject(jo);
        } else if (args instanceof String) {
            String s = (String) args;
            if (!s.isEmpty()) {
                // Evita duplicar se um evento final repetir o JSON completo já acumulado por deltas
                String cur = acc.argsBuf.toString();
                if (!cur.isEmpty() && cur.equals(s)) return;
                acc.appendArgsChunk(s);
            }
        }
    }

    private static ToolCallAccum getOrCreateToolAccum(List<ToolCallAccum> list, int index, String id) {
        if (id != null && !id.isEmpty()) {
            for (ToolCallAccum a : list) {
                if (id.equals(a.id)) return a;
            }
        }
        for (ToolCallAccum a : list) {
            if (a.index == index) return a;
        }
        ToolCallAccum created = new ToolCallAccum(index);
        list.add(created);
        return created;
    }

    // ---- Conversão de `tool_calls` e Fragmentos de Texto para `StepResponse` ----

    private static StepResponse buildStepResponseFromAccumulated(int step,
                                                                 List<ToolCallAccum> toolCalls,
                                                                 String rawContent,
                                                                 String rawThoughts,
                                                                 JSONObject directAction) throws Exception {
        StringBuilder extractedThink = new StringBuilder();
        if (rawThoughts != null && !rawThoughts.trim().isEmpty()) {
            extractedThink.append(rawThoughts.trim());
        }
        String cleanText = stripThinkBlocks(rawContent == null ? "" : rawContent, extractedThink).trim();

        // Se o modelo local (ex.: Qwen/Hermes/Llama) emitiu `<tool_call>{...}</tool_call>` em texto puro:
        if (toolCalls.isEmpty()) {
            extractInlineXmlToolCalls(cleanText, toolCalls);
            if (!toolCalls.isEmpty()) {
                cleanText = stripXmlToolCallTags(cleanText).trim();
            }
        }

        // Prioridade 1: `tool_calls` estruturados
        if (!toolCalls.isEmpty()) {
            JSONArray canonicalToolCalls = new JSONArray();
            for (ToolCallAccum acc : toolCalls) {
                String id = acc.resolvedId(step);
                String name = acc.resolvedName();
                if (name.isEmpty()) continue;
                canonicalToolCalls.put(new JSONObject()
                        .put("id", id)
                        .put("type", "function")
                        .put("function", new JSONObject()
                                .put("name", name)
                                .put("arguments", acc.resolvedArgsString())));
            }

            if (canonicalToolCalls.length() > 0) {
                ToolCallAccum primary = toolCalls.get(0);
                String pId = primary.resolvedId(step);
                String pName = primary.resolvedName();
                JSONObject pArgs = primary.resolvedArgsObject();
                String fallbackThought = !cleanText.isEmpty() ? cleanText : extractedThink.toString();
                JSONObject decision = toolCallToDecision(pName, pArgs, fallbackThought);
                String fallbackHist = pName + "(" + pArgs.toString() + ")";
                return new StepResponse(decision, cleanText, fallbackHist, canonicalToolCalls, pId, pName);
            }
        }

        // Prioridade 2: Objeto de ação direta (`{"action": "tap", ...}`)
        if (directAction != null && directAction.has("action")) {
            JSONObject normalized = normalizeDecisionObject(directAction,
                    !cleanText.isEmpty() ? cleanText : extractedThink.toString());
            return new StepResponse(normalized, cleanText, normalized.toString(), null, null, null);
        }

        // Prioridade 3: Fragmentos de texto acumulados (JSON embebido ou resposta final em linguagem natural)
        if (!cleanText.isEmpty()) {
            JSONObject embedded = tryExtractJsonDecisionFromText(cleanText, extractedThink.toString());
            if (embedded != null) {
                return new StepResponse(embedded, cleanText, embedded.toString(), null, null, null);
            }

            // Resposta em texto natural sem tool_call: pergunta ao utilizador (`?`) ou conclusão da tarefa (`done`)
            boolean isQuestion = cleanText.endsWith("?");
            JSONObject textDecision = new JSONObject()
                    .put("action", isQuestion ? "ask_user" : "done")
                    .put("message", cleanText)
                    .put("thought", extractedThink.toString());
            return new StepResponse(textDecision, cleanText, cleanText, null, null, null);
        }

        JSONObject missing = new JSONObject().put("action", "fail").put("message",
                "Resposta vazia do servidor. Verifica o resultado da última ação antes de continuar.");
        return new StepResponse(missing, "", "", null, null, null);
    }

    private static JSONObject toolCallToDecision(String rawName, JSONObject args, String fallbackThought) throws Exception {
        String name = rawName == null ? "" : rawName.toLowerCase(Locale.ROOT).trim();
        if (args == null) args = new JSONObject();

        String thought = args.optString("thought", args.optString("reasoning", fallbackThought)).trim();
        int nodeId = args.optInt("node_id", args.optInt("element_id",
                args.optInt("id", args.optInt("index", args.optInt("mark", -1)))));
        int x = args.optInt("x", args.optInt("start_x", args.optInt("x1", -1)));
        int y = args.optInt("y", args.optInt("start_y", args.optInt("y1", -1)));
        int x2 = args.optInt("x2", args.optInt("end_x", -1));
        int y2 = args.optInt("y2", args.optInt("end_y", -1));

        JSONArray coords = args.optJSONArray("coordinate");
        if (coords == null) coords = args.optJSONArray("point");
        if (coords == null) coords = args.optJSONArray("position");
        if (coords != null && coords.length() >= 2) {
            x = coords.optInt(0, x);
            y = coords.optInt(1, y);
        }

        String text = args.optString("text", args.optString("value",
                args.optString("content", args.optString("input", args.optString("query", "")))));
        String url = args.optString("url", args.optString("href", args.optString("link", text))).trim();
        String pkg = args.optString("package", args.optString("package_name",
                args.optString("app", args.optString("app_name", args.optString("name", text)))));
        String dir = args.optString("direction", args.optString("dir", "up")).toLowerCase(Locale.ROOT).trim();
        boolean submit = args.optBoolean("submit", args.optBoolean("enter", args.optBoolean("press_enter", false)));
        boolean crit = args.optBoolean("critical", args.optBoolean("requires_confirmation", false));
        String critReason = args.optString("critical_reason", args.optString("reason", ""));
        String msg = args.optString("message", args.optString("summary",
                args.optString("result", args.optString("answer", args.optString("question", text)))));
        int waitMs = args.has("seconds") ? Math.round((float) args.optDouble("seconds", 2.0) * 1000f)
                : args.optInt("duration_ms", args.optInt("ms", 2000));

        String action;
        switch (name) {
            case "open_app":
            case "launch_app":
            case "launch":
            case "start_app":
            case "open_application":
                action = "open_app";
                break;
            case "open_url":
            case "browse":
            case "navigate_url":
            case "goto_url":
            case "load_url":
                action = "open_url";
                break;
            case "tap":
            case "click":
            case "click_element":
            case "tap_element":
            case "touch":
            case "press_element":
            case "select":
                action = "tap";
                break;
            case "long_press":
            case "long_click":
            case "hold":
            case "touch_and_hold":
                action = "long_press";
                break;
            case "double_tap":
            case "double_click":
                action = "double_tap";
                break;
            case "type":
            case "type_text":
            case "input_text":
            case "set_text":
            case "enter_text":
            case "write":
            case "fill":
                action = "type";
                break;
            case "swipe":
            case "drag":
            case "fling":
                action = (x > 0 && y > 0 && x2 > 0 && y2 > 0) ? "swipe_coords" : "scroll";
                break;
            case "scroll":
                if (x > 0 && y > 0 && x2 > 0 && y2 > 0) {
                    action = "swipe_coords";
                } else {
                    // Em `scroll(direction='down')`, o utilizador quer ver conteúdo mais abaixo -> gesto dedo para cima
                    if ("down".equals(dir)) dir = "up";
                    else if ("up".equals(dir)) dir = "down";
                    action = "scroll";
                }
                break;
            case "scroll_down":
                action = "scroll";
                dir = "up";
                break;
            case "scroll_up":
                action = "scroll";
                dir = "down";
                break;
            case "navigate":
            case "system_button":
            case "global_action":
            case "press_key":
            case "key_event": {
                String tgt = args.optString("target", args.optString("button",
                        args.optString("key", args.optString("action", "back")))).toLowerCase(Locale.ROOT).trim();
                if (tgt.contains("home")) action = "home";
                else if (tgt.contains("recent") || tgt.contains("overview") || tgt.contains("app_switch")) action = "recents";
                else if (tgt.contains("notif")) action = "notifications";
                else if (tgt.contains("wait") || tgt.contains("sleep")) action = "wait";
                else action = "back";
                break;
            }
            case "back":
            case "press_back":
            case "navigate_back":
            case "go_back":
                action = "back";
                break;
            case "home":
            case "press_home":
            case "navigate_home":
            case "go_home":
                action = "home";
                break;
            case "recents":
            case "press_recents":
            case "recent_apps":
            case "overview":
                action = "recents";
                break;
            case "notifications":
            case "open_notifications":
            case "expand_notifications":
                action = "notifications";
                break;
            case "wait":
            case "sleep":
            case "pause":
                action = "wait";
                break;
            case "ask_user":
            case "confirm":
            case "request_confirmation":
            case "ask_confirmation":
            case "human_confirm":
                action = "ask_user";
                break;
            case "done":
            case "finish":
            case "complete":
            case "task_complete":
            case "finish_task":
            case "final_answer":
                action = args.optBoolean("failed", false) ? "fail" : "done";
                break;
            case "fail":
            case "abort":
            case "give_up":
            case "cannot_complete":
                action = "fail";
                break;
            default:
                // Caso a tool seja um wrapper genérico (ex.: `android_action` com campo `action` lá dentro)
                if (args.has("action")) {
                    return normalizeDecisionObject(args, thought);
                }
                return new JSONObject()
                        .put("action", "unknown_tool")
                        .put("thought", thought)
                        .put("error", "Ferramenta não suportada no Android: '" + rawName
                                + "'. Usa open_app, open_url, tap, long_press, double_tap, type_text, swipe, navigate, ask_user ou done.");
        }

        return new JSONObject()
                .put("action", action)
                .put("thought", thought)
                .put("node_id", nodeId)
                .put("x", x)
                .put("y", y)
                .put("x2", x2)
                .put("y2", y2)
                .put("text", text)
                .put("package", pkg)
                .put("url", url)
                .put("direction", dir)
                .put("submit", submit)
                .put("wait_ms", waitMs)
                .put("critical", crit)
                .put("critical_reason", critReason)
                .put("message", msg.isEmpty() ? thought : msg);
    }

    private static JSONObject normalizeDecisionObject(JSONObject raw, String fallbackThought) throws Exception {
        String rawAct = raw.optString("action", "");
        return toolCallToDecision(rawAct, raw, fallbackThought);
    }

    private static JSONObject tryExtractJsonDecisionFromText(String text, String fallbackThought) {
        if (text == null || text.isEmpty()) return null;

        // 1) Procura bloco ```json ... ``` ou ``` ... ```
        int fence = text.indexOf("```");
        while (fence >= 0) {
            int nl = text.indexOf('\n', fence);
            int endFence = nl >= 0 ? text.indexOf("```", nl + 1) : -1;
            if (nl >= 0 && endFence > nl) {
                String candidate = text.substring(nl + 1, endFence).trim();
                JSONObject parsed = tryParseActionCandidate(candidate, fallbackThought);
                if (parsed != null) return parsed;
                fence = text.indexOf("```", endFence + 3);
            } else {
                break;
            }
        }

        // 2) Procura objetos JSON balanceados `{ ... }` no texto
        int pos = text.indexOf('{');
        while (pos >= 0) {
            int end = findMatchingBrace(text, pos);
            if (end > pos) {
                String sub = text.substring(pos, end + 1);
                JSONObject parsed = tryParseActionCandidate(sub, fallbackThought);
                if (parsed != null) return parsed;
                pos = text.indexOf('{', end + 1);
            } else {
                break;
            }
        }
        return null;
    }

    private static JSONObject tryParseActionCandidate(String jsonCandidate, String fallbackThought) {
        try {
            if (!jsonCandidate.startsWith("{")) return null;
            JSONObject obj = new JSONObject(jsonCandidate);
            if (obj.opt("tool_calls") instanceof JSONArray) {
                JSONArray arr = obj.getJSONArray("tool_calls");
                if (arr.length() > 0) {
                    List<ToolCallAccum> tmp = new ArrayList<>();
                    ingestToolCallsArray(tmp, arr);
                    if (!tmp.isEmpty() && !tmp.get(0).resolvedName().isEmpty()) {
                        return toolCallToDecision(tmp.get(0).resolvedName(), tmp.get(0).resolvedArgsObject(), fallbackThought);
                    }
                }
            }
            if (obj.has("name") && (obj.has("arguments") || obj.has("args") || obj.has("parameters"))) {
                ToolCallAccum acc = new ToolCallAccum(0);
                ingestSingleToolCallObject(tmpList(acc), obj, 0);
                if (!acc.resolvedName().isEmpty()) {
                    return toolCallToDecision(acc.resolvedName(), acc.resolvedArgsObject(), fallbackThought);
                }
            }
            JSONObject unwrapped = unwrapActionObject(obj);
            if (unwrapped != null && !unwrapped.optString("action", "").isEmpty()) {
                return normalizeDecisionObject(unwrapped, fallbackThought);
            }
        } catch (Exception ignored) { }
        return null;
    }

    private static List<ToolCallAccum> tmpList(ToolCallAccum a) {
        List<ToolCallAccum> l = new ArrayList<>(1);
        l.add(a);
        return l;
    }

    private static int findMatchingBrace(String s, int openIdx) {
        int depth = 0;
        boolean inStr = false;
        boolean esc = false;
        for (int i = openIdx; i < s.length(); i++) {
            char c = s.charAt(i);
            if (inStr) {
                if (esc) esc = false;
                else if (c == '\\') esc = true;
                else if (c == '"') inStr = false;
            } else {
                if (c == '"') inStr = true;
                else if (c == '{') depth++;
                else if (c == '}') {
                    depth--;
                    if (depth == 0) return i;
                }
            }
        }
        return -1;
    }

    private static String stripThinkBlocks(String text, StringBuilder sink) {
        if (text == null || text.isEmpty()) return "";
        String out = text;
        while (true) {
            int s = out.indexOf("<think>");
            if (s < 0) break;
            int e = out.indexOf("</think>", s + 7);
            if (e < 0) {
                // Tag <think> ainda aberta a meio do stream
                if (sink != null) sink.append(out.substring(s + 7));
                out = out.substring(0, s);
                break;
            }
            if (sink != null) {
                if (sink.length() > 0) sink.append(' ');
                sink.append(out.substring(s + 7, e).trim());
            }
            out = out.substring(0, s) + out.substring(e + 8);
        }
        return out;
    }

    private static void extractInlineXmlToolCalls(String text, List<ToolCallAccum> out) {
        if (text == null) return;
        int idx = 0;
        int pos = text.indexOf("<tool_call>");
        while (pos >= 0) {
            int end = text.indexOf("</tool_call>", pos + 11);
            if (end < 0) break;
            String body = text.substring(pos + 11, end).trim();
            try {
                JSONObject tc = new JSONObject(body);
                ingestSingleToolCallObject(out, tc, idx++);
            } catch (Exception ignored) { }
            pos = text.indexOf("<tool_call>", end + 12);
        }
    }

    private static String stripXmlToolCallTags(String text) {
        String out = text;
        while (true) {
            int s = out.indexOf("<tool_call>");
            if (s < 0) break;
            int e = out.indexOf("</tool_call>", s + 11);
            if (e < 0) {
                out = out.substring(0, s);
                break;
            }
            out = out.substring(0, s) + out.substring(e + 12);
        }
        return out;
    }

    private static JSONObject unwrapActionObject(JSONObject obj) throws Exception {
        if (obj == null) return null;

        Object actField = obj.opt("action");
        if (actField instanceof JSONObject) {
            JSONObject inner = new JSONObject(((JSONObject) actField).toString());
            if (!inner.has("action")) {
                inner.put("action", inner.optString("type", inner.optString("name", "")));
            }
            copyIfMissing(obj, inner, "thought");
            copyIfMissing(obj, inner, "critical");
            copyIfMissing(obj, inner, "critical_reason");
            copyIfMissing(obj, inner, "message");
            return inner;
        }
        if (actField instanceof String && !((String) actField).isEmpty()) {
            return obj;
        }

        for (String wrapper : new String[]{"decision", "step", "result", "data"}) {
            Object sub = obj.opt(wrapper);
            if (sub instanceof JSONObject) {
                JSONObject unwrapped = unwrapActionObject((JSONObject) sub);
                if (unwrapped != null) {
                    copyIfMissing(obj, unwrapped, "thought");
                    copyIfMissing(obj, unwrapped, "critical");
                    copyIfMissing(obj, unwrapped, "critical_reason");
                    return unwrapped;
                }
            }
        }

        if (obj.has("tool") && obj.opt("tool") instanceof String) {
            JSONObject out = obj.optJSONObject("args") != null
                    ? new JSONObject(obj.getJSONObject("args").toString())
                    : (obj.optJSONObject("arguments") != null
                        ? new JSONObject(obj.getJSONObject("arguments").toString())
                        : new JSONObject());
            out.put("action", obj.optString("tool"));
            copyIfMissing(obj, out, "thought");
            copyIfMissing(obj, out, "critical");
            return out;
        }
        return null;
    }

    private static void copyIfMissing(JSONObject src, JSONObject dst, String key) {
        try {
            if (src.has(key) && !dst.has(key)) dst.put(key, src.get(key));
        } catch (Exception ignored) { }
    }

    private static String readAllBounded(InputStream in, int maxBytes) throws Exception {
        if (in == null) return "";
        try (InputStream is = in) {
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n, total = 0;
            while ((n = is.read(buf)) > 0) {
                total += n;
                if (total > maxBytes) throw new Exception("Resposta excedeu limite de memória.");
                bo.write(buf, 0, n);
            }
            return new String(bo.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    private static String readAllSmall(InputStream in) {
        try {
            String s = readAllBounded(in, 4096).trim();
            return s.length() > 240 ? s.substring(0, 240) + "…" : s;
        } catch (Exception e) {
            return "";
        }
    }

    private void finishWithNotice(String title, String body) {
        SyncService.notifyDone(getApplicationContext(), "agent-" + System.currentTimeMillis(), title, body);
        main.post(() -> Toast.makeText(this, title + ": " + body, Toast.LENGTH_LONG).show());
    }

    private void vibrateShort() {
        try {
            Vibrator v = (Vibrator) getSystemService(VIBRATOR_SERVICE);
            if (v == null) return;
            if (Build.VERSION.SDK_INT >= 26) v.vibrate(VibrationEffect.createOneShot(180, VibrationEffect.DEFAULT_AMPLITUDE));
            else v.vibrate(180);
        } catch (Exception ignored) { }
    }

    private Button smallBtn(String text, int bg, int fg) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setTextSize(12);
        b.setTextColor(fg);
        b.setMinimumWidth(0);
        b.setMinWidth(0);
        b.setMinimumHeight(0);
        b.setMinHeight(0);
        b.setPadding(dp(10), dp(6), dp(10), dp(6));
        b.setBackground(roundedBg(bg, bg, dp(8)));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.leftMargin = dp(4);
        b.setLayoutParams(lp);
        return b;
    }

    private static GradientDrawable roundedBg(int fill, int stroke, int radiusPx) {
        GradientDrawable gd = new GradientDrawable();
        gd.setColor(fill);
        gd.setCornerRadius(radiusPx);
        gd.setStroke(2, stroke);
        return gd;
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    private static void sleepQuiet(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignored) { }
    }
}
