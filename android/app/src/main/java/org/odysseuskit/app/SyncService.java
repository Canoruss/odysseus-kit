package org.odysseuskit.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.webkit.CookieManager;

import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Foreground service that keeps the app alive in the background and notifies when a chat
 * (or agent/research run) finishes streaming, or when a scheduled task reports a result.
 */
public class SyncService extends Service {
    static volatile boolean appVisible = false;
    static final String CH_FG = "odysseus_sync", CH_CHAT = "odysseus_chat";
    private volatile boolean running = false;
    private Thread thread;
    private final Set<String> streaming = new HashSet<>();
    private final java.util.Map<String, String> lastSeen = new java.util.HashMap<>();
    private boolean primed = false;

    static void start(Context ctx) {
        try { ContextCompat.startForegroundService(ctx, new Intent(ctx, SyncService.class)); } catch (Exception ignored) { }
    }

    @Override public IBinder onBind(Intent i) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(new NotificationChannel(CH_FG, Tr.t("Ligação em segundo plano"), NotificationManager.IMPORTANCE_MIN));
            nm.createNotificationChannel(new NotificationChannel(CH_CHAT, Tr.t("Respostas e tarefas concluídas"), NotificationManager.IMPORTANCE_HIGH));
        }
        PendingIntent pi = PendingIntent.getActivity(this, 1, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification n = new NotificationCompat.Builder(this, CH_FG)
                .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
                .setContentTitle("Odysseus").setContentText("A receber avisos em segundo plano")
                .setPriority(NotificationCompat.PRIORITY_MIN).setOngoing(true).setContentIntent(pi)
                .addAction(0, Tr.t("Definições"), PendingIntent.getActivity(this, 30, new Intent(this, SettingsActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE))
                .addAction(0, "Tradutor", PendingIntent.getActivity(this, 31, new Intent(this, TranslateActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE))
                .build();
        try {
            if (Build.VERSION.SDK_INT >= 34) startForeground(2, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            else startForeground(2, n);
        } catch (Exception e) { stopSelf(); return START_NOT_STICKY; }
        if (intent != null && ACTION_REPLY.equals(intent.getAction())) {
            doReply(intent.getStringExtra("session"), intent.getStringExtra("text"));
        }
        if (!running) {
            running = true;
            thread = new Thread(this::loop, "ody-sync");
            thread.start();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        running = false;
        if (thread != null) thread.interrupt();
        super.onDestroy();
    }

    private void loop() {
        int n = 0;
        while (running) {
            try { poll(); } catch (Exception ignored) { }
            // Reminders/events created elsewhere (PC, Claude, Telegram) are picked up within
            // ~1 min instead of waiting for the 15-min WorkManager job.
            if (n++ % 3 == 0) NoteSync.runSync(getApplicationContext());
            try { Thread.sleep(20000); } catch (InterruptedException e) { return; }
        }
    }

    private static long parseUtc(String s) {
        try {
            if (s == null || s.isEmpty()) return -1;
            if (s.endsWith("Z") || s.contains("+")) return Instant.parse(s.endsWith("Z") ? s : java.time.OffsetDateTime.parse(s).toInstant().toString()).toEpochMilli();
            return LocalDateTime.parse(s).toInstant(ZoneOffset.UTC).toEpochMilli();
        } catch (Exception e) { return -1; }
    }

    private void poll() throws Exception {
        Daily.tick(this);
        FileShare.poll(this, appVisible);
        String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
        if (cookie == null || cookie.isEmpty()) return;
        String ss = NoteSync.httpGet(NoteSync.SITE + "/api/sessions", cookie);
        if (ss != null) {
            // A chat "finished" = its last_message_at moved since the last poll and it is no
            // longer streaming. Catches replies shorter than the poll interval too.
            JSONArray arr = new JSONArray(ss);
            boolean first = !primed;
            for (int i = 0; i < arr.length(); i++) {
                JSONObject s = arr.getJSONObject(i);
                String id = s.optString("id");
                String lm = s.isNull("last_message_at") ? "" : s.optString("last_message_at", "");
                if (id.isEmpty() || lm.isEmpty()) continue;
                String prev = lastSeen.get(id);
                if (first) { lastSeen.put(id, lm); continue; }
                if (lm.equals(prev) && !streaming.contains(id)) continue;
                int code = NoteSync.httpCode(NoteSync.SITE + "/api/chat/stream_status/" + id, cookie);
                if (code == 200) {
                    streaming.add(id);
                    lastSeen.put(id, lm);
                } else if (code == 404) {
                    streaming.remove(id);
                    lastSeen.put(id, lm);
                    if (!appVisible && AppSettings.chatNotifications(this)) {
                        String name = s.isNull("name") ? "" : s.optString("name", "");
                        notifyChat(id, name.isEmpty() ? "Chat" : name, cookie);
                    }
                }
            }
            primed = true;
        }
        if (!appVisible && AppSettings.taskNotifications(this)) {
            String nb = NoteSync.httpGet(NoteSync.SITE + "/api/tasks/notifications", cookie);
            if (nb != null) {
                JSONArray a = new JSONObject(nb).optJSONArray("notifications");
                for (int i = 0; a != null && i < a.length(); i++) {
                    JSONObject o = a.getJSONObject(i);
                    // Reminders are already shown natively at the due time (NoteSync): the
                    // server's copy would be a duplicate.
                    if (o.optString("task_id", "").startsWith("reminder-")) continue;
                    String st = o.optString("status", "");
                    String body = NoteSync.s(o, "body", "");
                    if (body.startsWith("[") && body.contains("unavailable")) body = "";
                    String title = o.optString("task_name", "Tarefa");
                    if (st.equals("error") || st.equals("failed")) title += " — falhou";
                    notifyDone("task" + o.optString("task_id", String.valueOf(i)) + o.optString("timestamp"),
                            title, body.isEmpty() ? Tr.t("Tarefa concluída") : body);
                }
            }
        }
    }

    /** "Resposta pronta": opens that chat, shows the start of the reply, inline "Responder". */
    private void notifyChat(String sessionId, String name, String cookie) {
        String preview = lastReply(sessionId, cookie);
        int nid = Math.abs(sessionId.hashCode());
        PendingIntent pi = PendingIntent.getActivity(this, nid, new Intent(this, MainActivity.class)
                .setAction("open." + sessionId).putExtra(MainActivity.EXTRA_SESSION, sessionId)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP), PendingIntent.FLAG_IMMUTABLE);
        String text = preview.isEmpty() ? name : preview;
        Notification n = new NotificationCompat.Builder(this, CH_CHAT)
                .setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle("Resposta pronta — " + name).setContentText(text)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
                .setPriority(NotificationCompat.PRIORITY_HIGH).setSilent(AppSettings.quiet(this)).setAutoCancel(true).setContentIntent(pi)
                .addAction(Actions.replyAction(this, sessionId, nid)).build();
        try { getSystemService(NotificationManager.class).notify(nid, n); } catch (SecurityException ignored) { }
    }

    /** First ~300 chars of the latest assistant message (best effort). */
    private static String lastReply(String sessionId, String cookie) {
        try {
            String b = NoteSync.httpGet(NoteSync.SITE + "/api/history/" + sessionId, cookie);
            if (b == null) return "";
            JSONObject o = new JSONObject(b);
            JSONArray h = o.optJSONArray("history");
            if (h == null) h = o.optJSONArray("messages");
            for (int i = h == null ? -1 : h.length() - 1; i >= 0; i--) {
                JSONObject m = h.optJSONObject(i);
                if (m != null && "assistant".equals(m.optString("role"))) {
                    Object c = m.opt("content");
                    String t = c instanceof String ? (String) c : String.valueOf(c);
                    // Drop tool-call lines ("> 🔧 **Bash** ...") so the preview shows the answer.
                    StringBuilder keep = new StringBuilder();
                    for (String line : t.split("\n")) {
                        if (line.trim().startsWith(">") && line.contains("🔧")) continue;
                        keep.append(line).append('\n');
                    }
                    t = keep.toString();
                    t = t.replaceAll("[#*`>_]", "").replaceAll("\\s+", " ").trim();
                    return t.length() > 300 ? t.substring(0, 300) + "…" : t;
                }
            }
        } catch (Exception ignored) { }
        return "";
    }

    static final String ACTION_REPLY = "org.odysseuskit.app.SEND_REPLY";

    /** Send a chat message from a notification; the reply is announced again when it finishes. */
    static void sendReply(Context ctx, String sessionId, String text) {
        try {
            ContextCompat.startForegroundService(ctx, new Intent(ctx, SyncService.class)
                    .setAction(ACTION_REPLY).putExtra("session", sessionId).putExtra("text", text));
        } catch (Exception ignored) { }
    }

    private void doReply(String sessionId, String text) {
        new Thread(() -> {
            try {
                String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
                java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL(NoteSync.SITE + "/api/chat_stream").openConnection();
                c.setRequestMethod("POST");
                c.setConnectTimeout(15000);
                c.setReadTimeout(10 * 60_000);
                c.setRequestProperty("Cookie", cookie);
                c.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
                c.setDoOutput(true);
                String form = "session=" + java.net.URLEncoder.encode(sessionId, "UTF-8") + "&message=" + java.net.URLEncoder.encode(text, "UTF-8");
                try (java.io.OutputStream os = c.getOutputStream()) { os.write(form.getBytes("UTF-8")); }
                // Read the whole stream so the server finishes the reply normally.
                try (java.io.InputStream in = c.getInputStream()) {
                    byte[] buf = new byte[8192];
                    while (in.read(buf) > 0) { }
                }
            } catch (Exception e) {
                notifyDone("replyfail" + sessionId, Tr.t("Não foi possível enviar a resposta"), String.valueOf(e.getMessage()));
            }
        }, "ody-reply").start();
    }

    private void notifyDone(String key, String title, String text) {
        PendingIntent pi = PendingIntent.getActivity(this, 2, new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP), PendingIntent.FLAG_IMMUTABLE);
        Notification n = new NotificationCompat.Builder(this, CH_CHAT)
                .setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentTitle(title).setContentText(text)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
                .setPriority(NotificationCompat.PRIORITY_HIGH).setSilent(AppSettings.quiet(this)).setAutoCancel(true).setContentIntent(pi).build();
        try { getSystemService(NotificationManager.class).notify(Math.abs(key.hashCode()), n); } catch (SecurityException ignored) { }
    }

    public static class Boot extends BroadcastReceiver {
        @Override public void onReceive(Context c, Intent i) { start(c); NoteSync.schedule(c); }
    }
}
