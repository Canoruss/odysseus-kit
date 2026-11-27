package com.canorus.odysseus;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.webkit.CookieManager;

import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * Adaptive notification sync:
 * 1. In Battery Saver mode (default), SyncService does NOT run 24/7. Instead, NoteSync's WorkManager
 *    job runs SyncService.pollOnce(ctx) during batched Doze-friendly windows, and SyncService only
 *    starts as a short-lived ForegroundService when actively watching an in-flight chat reply or
 *    sending an inline notification reply, stopping itself automatically once idle!
 * 2. If the user explicitly disables Battery Saver in Settings, it uses adaptive exponential backoff
 *    (30s active -> up to 5 min idle/offline) instead of hammering the radio every 20s.
 */
public class SyncService extends Service {
    static { System.loadLibrary("odysseus_voice"); }
    private static native String nativeChatPreview(String body);
    static volatile boolean appVisible = false;
    static final String CH_FG = Channels.SYNC_FG;
    static final String CH_CHAT = Channels.CHAT;
    static final String ACTION_REPLY = "com.canorus.odysseus.SEND_REPLY";
    static final String ACTION_WATCH = "com.canorus.odysseus.WATCH_STREAM";
    private static final String PREFS_STATE = "sync_state";

    private volatile boolean running = false;
    private Thread thread;
    private volatile long watchUntilMs = 0;

    /** Called on boot / app resume: respects Battery Saver so we don't hold a permanent service! */
    static void startIfNeeded(Context ctx) {
        if (!AppSettings.setupDone(ctx)) return;
        if (AppSettings.batterySaver(ctx)) return;
        start(ctx, null);
    }

    /** Temporarily watch for an in-flight chat response for up to 10 minutes, then auto-stop. */
    static void watchActiveStream(Context ctx) {
        if (!AppSettings.setupDone(ctx) || !AppSettings.chatNotifications(ctx)) return;
        start(ctx, ACTION_WATCH);
    }

    static void start(Context ctx) {
        startIfNeeded(ctx);
    }

    private static void start(Context ctx, String action) {
        try {
            Intent i = new Intent(ctx, SyncService.class);
            if (action != null) i.setAction(action);
            ContextCompat.startForegroundService(ctx, i);
        } catch (Exception ignored) { }
    }

    static void stopIfRunning(Context ctx) {
        try { ctx.stopService(new Intent(ctx, SyncService.class)); } catch (Exception ignored) { }
    }

    @Override public IBinder onBind(Intent i) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Channels.ensureAll(this);
        PendingIntent pi = PendingIntent.getActivity(this, 1, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification n = new NotificationCompat.Builder(this, CH_FG)
                .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setContentTitle("Odysseus")
                .setContentText(L.t("A receber avisos em segundo plano"))
                .setPriority(NotificationCompat.PRIORITY_MIN)
                .setSilent(true)
                .setOnlyAlertOnce(true)
                .setOngoing(true)
                .setContentIntent(pi)
                .addAction(0, L.t("Definições"), PendingIntent.getActivity(this, 30, new Intent(this, SettingsActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE))
                .addAction(0, L.t("Tradutor"), PendingIntent.getActivity(this, 31, new Intent(this, TranslateActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE))
                .build();
        try {
            if (Build.VERSION.SDK_INT >= 34) startForeground(2, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            else startForeground(2, n);
        } catch (Exception e) {
            stopSelf();
            return START_NOT_STICKY;
        }

        String action = intent == null ? null : intent.getAction();
        if (ACTION_REPLY.equals(action)) {
            watchUntilMs = System.currentTimeMillis() + 12 * 60_000L;
            doReply(intent.getStringExtra("session"), intent.getStringExtra("text"));
        } else if (ACTION_WATCH.equals(action)) {
            watchUntilMs = System.currentTimeMillis() + 10 * 60_000L;
        }

        if (!running) {
            running = true;
            thread = new Thread(this::loop, "ody-sync");
            thread.start();
        }
        return AppSettings.batterySaver(this) ? START_NOT_STICKY : START_STICKY;
    }

    @Override
    public void onDestroy() {
        running = false;
        if (thread != null) thread.interrupt();
        super.onDestroy();
    }

    private void loop() {
        int consecutiveErrors = 0;
        int idleCycles = 0;
        while (running) {
            boolean saver = AppSettings.batterySaver(this);
            boolean hasActiveStreams = false;
            if (!appVisible && Bg.isOnline(this)) {
                try {
                    hasActiveStreams = pollOnce(getApplicationContext());
                    consecutiveErrors = 0;
                } catch (Exception e) {
                    consecutiveErrors = Math.min(consecutiveErrors + 1, 5);
                }
            }

            if (saver) {
                if (!hasActiveStreams && System.currentTimeMillis() > watchUntilMs && idleCycles >= 1) {
                    running = false;
                    stopForeground(true);
                    stopSelf();
                    return;
                }
                idleCycles = hasActiveStreams ? 0 : (idleCycles + 1);
            } else {
                idleCycles = hasActiveStreams ? 0 : Math.min(idleCycles + 1, 6);
            }

            long sleepMs;
            if (consecutiveErrors > 0) {
                sleepMs = Math.min(300_000L, 30_000L * (1L << consecutiveErrors));
            } else if (hasActiveStreams) {
                sleepMs = 12_000L;
            } else if (saver) {
                sleepMs = 20_000L;
            } else if (appVisible) {
                sleepMs = 120_000L;
            } else {
                // Adaptive backoff when idle in continuous mode: 30s -> 60s -> 90s -> ... -> 180s
                sleepMs = Math.min(180_000L, 30_000L + idleCycles * 30_000L);
            }

            try { Thread.sleep(sleepMs); } catch (InterruptedException e) { return; }
        }
    }

    private static final Object POLL_LOCK = new Object();

    /**
     * Performs a single lightweight check for finished chats, completed scheduled tasks,
     * morning summary, and shared files. Persists `lastSeen` in SharedPreferences so WorkManager
     * runs and short-lived service runs seamlessly share state without duplicate alerts.
     *
     * @return true if any chat session is currently streaming.
     */
    static boolean pollOnce(Context ctx) throws Exception {
        synchronized (POLL_LOCK) {
            if (!Bg.isOnline(ctx) || NoteSync.SITE == null || NoteSync.SITE.isEmpty()) return false;
            Daily.tick(ctx);
            if (!appVisible && AppSettings.fileNotifications(ctx)) {
                FileShare.poll(ctx, false);
            }
            String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
            if (cookie == null || cookie.isEmpty()) return false;

            SharedPreferences sp = ctx.getSharedPreferences(PREFS_STATE, Context.MODE_PRIVATE);
            boolean primed = sp.getBoolean("primed", false);
            JSONObject seenJson;
            try { seenJson = new JSONObject(sp.getString("last_seen", "{}")); }
            catch (Exception e) { seenJson = new JSONObject(); }
            Set<String> streaming = new HashSet<>(sp.getStringSet("streaming", new HashSet<>()));
            boolean stateDirty = false;

            if (AppSettings.chatNotifications(ctx)) {
                Http.Resp sr = Http.getConditional(NoteSync.SITE + "/api/sessions", cookie, 8000, 15000);
                if (sr.code == 200 && (!sr.notModified || !streaming.isEmpty()) && sr.bytes != null) {
                    JSONArray arr = new JSONArray(sr.text());
                    boolean first = !primed;
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject s = arr.getJSONObject(i);
                        String id = s.optString("id");
                        String lm = s.isNull("last_message_at") ? "" : s.optString("last_message_at", "");
                        if (id.isEmpty() || lm.isEmpty()) continue;
                        String prev = seenJson.optString(id, "");
                        if (first) {
                            seenJson.put(id, lm);
                            stateDirty = true;
                            continue;
                        }
                        if (lm.equals(prev) && !streaming.contains(id)) continue;

                        String stBody = null;
                        int code;
                        try {
                            stBody = Http.getString(NoteSync.SITE + "/api/chat/stream_status/" + id, cookie);
                            code = stBody != null ? 200 : 404;
                        } catch (Exception e) { code = -1; }
                        if (code == 200 && stBody != null && !stBody.contains("\"streaming\"")) code = 404;

                        if (code == 200) {
                            if (streaming.add(id)) stateDirty = true;
                            if (!lm.equals(prev)) { seenJson.put(id, lm); stateDirty = true; }
                        } else if (code == 404) {
                            if (streaming.remove(id)) stateDirty = true;
                            if (!lm.equals(prev)) { seenJson.put(id, lm); stateDirty = true; }
                            if (!appVisible) {
                                String name = s.isNull("name") ? "" : s.optString("name", "");
                                notifyChat(ctx, id, name.isEmpty() ? "Chat" : name, lm, cookie, sp);
                            }
                        }
                    }
                    if (!primed) { primed = true; stateDirty = true; }
                }
            }

            if (!appVisible && AppSettings.taskNotifications(ctx)) {
                Http.Resp tr = Http.getConditional(NoteSync.SITE + "/api/tasks/notifications", cookie, 8000, 15000);
                if (tr.code == 200 && !tr.notModified && tr.bytes != null) {
                    JSONArray a = new JSONObject(tr.text()).optJSONArray("notifications");
                    Set<String> notifiedTasks = new HashSet<>(sp.getStringSet("notified_tasks", new HashSet<>()));
                    boolean tasksChanged = false;
                    for (int i = 0; a != null && i < a.length(); i++) {
                        JSONObject o = a.getJSONObject(i);
                        if (o.optString("task_id", "").startsWith("reminder-")) continue;
                        String key = "task|" + o.optString("task_id", String.valueOf(i)) + "|" + o.optString("timestamp");
                        if (!notifiedTasks.add(key)) continue;
                        tasksChanged = true;
                        String st = o.optString("status", "");
                        String body = NoteSync.s(o, "body", "");
                        if (body.startsWith("[") && body.contains("unavailable")) body = "";
                        String title = o.optString("task_name", L.t("Tarefa"));
                        if (st.equals("error") || st.equals("failed")) title += " — falhou";
                        notifyDone(ctx, key, title, body.isEmpty() ? L.t("Tarefa concluída") : body);
                    }
                    if (tasksChanged) {
                        if (notifiedTasks.size() > 200) {
                            java.util.Iterator<String> it = notifiedTasks.iterator();
                            while (notifiedTasks.size() > 150 && it.hasNext()) { it.next(); it.remove(); }
                        }
                        sp.edit().putStringSet("notified_tasks", notifiedTasks).apply();
                    }
                }
            }

            if (stateDirty) {
                // Bound seenJson to max 150 sessions so preferences stay tiny
                if (seenJson.length() > 150) {
                    JSONArray names = seenJson.names();
                    for (int i = 0; names != null && i < names.length() - 120; i++) {
                        seenJson.remove(names.optString(i));
                    }
                }
                sp.edit()
                        .putBoolean("primed", primed)
                        .putString("last_seen", seenJson.toString())
                        .putStringSet("streaming", streaming)
                        .apply();
            }
            return !streaming.isEmpty();
        }
    }

    /** "Resposta pronta": deduplicated by sessionId + last_message_at so it never alerts twice. */
    private static void notifyChat(Context ctx, String sessionId, String name, String lm, String cookie, SharedPreferences sp) {
        String dedupKey = sessionId + "|" + lm;
        if (dedupKey.equals(sp.getString("last_chat_notif_" + sessionId, ""))) return;
        sp.edit().putString("last_chat_notif_" + sessionId, dedupKey).apply();

        Channels.ensureAll(ctx);
        String preview = lastReply(sessionId, cookie);
        int nid = Math.abs(sessionId.hashCode());
        PendingIntent pi = PendingIntent.getActivity(ctx, nid, new Intent(ctx, MainActivity.class)
                .setAction("open." + sessionId).putExtra(MainActivity.EXTRA_SESSION, sessionId)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP), PendingIntent.FLAG_IMMUTABLE);
        String text = preview.isEmpty() ? name : preview;
        Notification n = new NotificationCompat.Builder(ctx, CH_CHAT)
                .setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle(L.t("Resposta pronta — ") + name)
                .setContentText(text)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setOnlyAlertOnce(true)
                .setSilent(AppSettings.quiet(ctx))
                .setAutoCancel(true)
                .setContentIntent(pi)
                .addAction(Actions.replyAction(ctx, sessionId, nid))
                .build();
        try { ctx.getSystemService(NotificationManager.class).notify(nid, n); } catch (SecurityException ignored) { }
    }

    /** First ~300 chars of the latest assistant message (best effort). */
    private static String lastReply(String sessionId, String cookie) {
        try {
            String b = Http.getString(NoteSync.SITE + "/api/history/" + sessionId, cookie);
            if (b == null) return "";
            return nativeChatPreview(b);
        } catch (Exception ignored) { }
        return "";
    }

    /** Send a chat message from a notification; watches the stream and stops when done. */
    static void sendReply(Context ctx, String sessionId, String text) {
        try {
            ContextCompat.startForegroundService(ctx, new Intent(ctx, SyncService.class)
                    .setAction(ACTION_REPLY).putExtra("session", sessionId).putExtra("text", text));
        } catch (Exception ignored) { }
    }

    private void doReply(String sessionId, String text) {
        if (sessionId == null || text == null) return;
        Bg.run(() -> {
            HttpURLConnection c = null;
            try {
                String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
                c = (HttpURLConnection) new URL(NoteSync.SITE + "/api/chat_stream").openConnection();
                c.setRequestMethod("POST");
                c.setConnectTimeout(15000);
                c.setReadTimeout(10 * 60_000);
                if (cookie != null) c.setRequestProperty("Cookie", cookie);
                c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
                c.setDoOutput(true);
                String form = "session=" + URLEncoder.encode(sessionId, "UTF-8")
                        + "&message=" + URLEncoder.encode(text, "UTF-8");
                try (OutputStream os = c.getOutputStream()) {
                    os.write(form.getBytes(StandardCharsets.UTF_8));
                }
                try (InputStream in = c.getInputStream()) {
                    byte[] buf = new byte[8192];
                    while (in.read(buf) > 0) { }
                }
                // Immediately check & deliver the completed reply notification
                try { pollOnce(getApplicationContext()); } catch (Exception ignored) { }
            } catch (Exception e) {
                notifyDone(getApplicationContext(), "replyfail" + sessionId,
                        L.t("Não foi possível enviar a resposta"), String.valueOf(e.getMessage()));
            } finally {
                if (c != null) c.disconnect();
                watchUntilMs = 0;
            }
        });
    }

    static void notifyDone(Context ctx, String key, String title, String text) {
        Channels.ensureAll(ctx);
        PendingIntent pi = PendingIntent.getActivity(ctx, 2, new Intent(ctx, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP), PendingIntent.FLAG_IMMUTABLE);
        Notification n = new NotificationCompat.Builder(ctx, CH_CHAT)
                .setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle(title)
                .setContentText(text)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setOnlyAlertOnce(true)
                .setSilent(AppSettings.quiet(ctx))
                .setAutoCancel(true)
                .setContentIntent(pi)
                .build();
        try { ctx.getSystemService(NotificationManager.class).notify(Math.abs(key.hashCode()), n); } catch (SecurityException ignored) { }
    }

    public static class Boot extends BroadcastReceiver {
        @Override public void onReceive(Context c, Intent i) {
            AppSettings.applyServer(c);
            startIfNeeded(c);
            NoteSync.schedule(c);
            SnsListener.scheduleAll(c);
        }
    }
}
