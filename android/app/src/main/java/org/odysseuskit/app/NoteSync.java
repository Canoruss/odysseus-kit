package org.odysseuskit.app;

import android.app.AlarmManager;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.webkit.CookieManager;

import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.ExistingWorkPolicy;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.time.OffsetDateTime;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.HashSet;
import java.util.Set;
import java.util.Locale;
import java.util.concurrent.TimeUnit;

/**
 * Native reminders: polls /api/notes with the WebView session cookie, schedules an
 * alarm for every note that has a due date and shows an Android notification when it is due.
 */
public class NoteSync {
    static String SITE = "https://YOUR-SERVER.YOUR-TAILNET.ts.net";
    static final String CHANNEL = "odysseus_reminders";
    static final String PREFS = "note_sync";

    static void schedule(Context ctx) {
        WorkManager wm = WorkManager.getInstance(ctx);
        wm.enqueueUniquePeriodicWork("note-sync", ExistingPeriodicWorkPolicy.KEEP,
                new PeriodicWorkRequest.Builder(Worker1.class, 15, TimeUnit.MINUTES).build());
        wm.enqueueUniqueWork("note-sync-now", ExistingWorkPolicy.REPLACE,
                new OneTimeWorkRequest.Builder(Worker1.class).build());
    }

    static String s(JSONObject o, String k, String d) { return (o == null || o.isNull(k)) ? d : o.optString(k, d); }

    static String httpGet(String url, String cookie) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(10000); c.setReadTimeout(20000);
        c.setRequestProperty("Cookie", cookie); c.setRequestProperty("Accept", "application/json");
        if (c.getResponseCode() != 200) return null;
        try (InputStream in = c.getInputStream()) {
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[8192]; int r;
            while ((r = in.read(buf)) > 0) bo.write(buf, 0, r);
            return bo.toString("UTF-8");
        }
    }

    static int httpCode(String url, String cookie) {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(8000); c.setReadTimeout(8000);
            c.setRequestProperty("Cookie", cookie);
            return c.getResponseCode();
        } catch (Exception e) { return -1; }
    }


    static void syncNow(Context ctx) {
        Context app = ctx.getApplicationContext();
        new Thread(() -> runSync(app), "ody-notesync").start();
    }

    static void ensureChannel(Context ctx) {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "Lembretes e tarefas",
                    NotificationManager.IMPORTANCE_HIGH);
            ch.setDescription("Avisos das tarefas e lembretes do Odysseus");
            NotificationManager nm = ctx.getSystemService(NotificationManager.class);
            nm.createNotificationChannel(ch);
            NotificationChannel al = new NotificationChannel("odysseus_alarms", "Alarmes", NotificationManager.IMPORTANCE_HIGH);
            al.setDescription(Tr.t("Tarefas com 'alarme' no título tocam como alarme"));
            al.setSound(android.media.RingtoneManager.getDefaultUri(android.media.RingtoneManager.TYPE_ALARM),
                    new android.media.AudioAttributes.Builder().setUsage(android.media.AudioAttributes.USAGE_ALARM)
                            .setContentType(android.media.AudioAttributes.CONTENT_TYPE_SONIFICATION).build());
            al.enableVibration(true);
            al.setVibrationPattern(new long[]{0, 600, 400, 600, 400, 600});
            nm.createNotificationChannel(al);
        }
    }

    static long parseDue(String s) {
        try {
            return OffsetDateTime.parse(s).toInstant().toEpochMilli();
        } catch (Exception e) {
            try {
                String t = s.endsWith("Z") ? s.substring(0, s.length() - 1) : s;
                return LocalDateTime.parse(t).atZone(ZoneId.systemDefault()).toInstant().toEpochMilli();
            } catch (Exception e2) {
                return -1;
            }
        }
    }

    static void show(Context ctx, String id, String title, String body, String dueKey) {
        SharedPreferences sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        Set<String> done = new HashSet<>(sp.getStringSet("notified", new HashSet<>()));
        String key = id + "|" + dueKey;
        if (done.contains(key)) return;
        done.add(key);
        if (done.size() > 200) {
            long cutoff = System.currentTimeMillis() - 2 * 86400_000L;
            java.util.Iterator<String> it = done.iterator();
            while (it.hasNext()) {
                String k = it.next();
                long t = parseDue(k.substring(k.indexOf('|') + 1));
                if (t > 0 && t < cutoff) it.remove();
            }
        }
        sp.edit().putStringSet("notified", done).apply();
        boolean alarm = AppSettings.isAlarmTitle(ctx, title);
        if (alarm) {
            try {
                androidx.core.content.ContextCompat.startForegroundService(ctx, new Intent(ctx, AlarmService.class)
                        .putExtra("id", id).putExtra("title", title).putExtra("body", body));
                return;
            } catch (Exception ignored) { /* fall back to a normal notification below */ }
        }
        if (!alarm && !AppSettings.reminders(ctx)) return;
        ensureChannel(ctx);
        Intent open = new Intent(ctx, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(ctx, 0, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        int nid = Math.abs(id.hashCode());
        NotificationCompat.Builder b = new NotificationCompat.Builder(ctx, alarm ? "odysseus_alarms" : CHANNEL)
                .setSmallIcon(android.R.drawable.ic_popup_reminder)
                .setContentTitle(title == null || title.isEmpty() ? "Lembrete" : title)
                .setContentText(body == null || body.isEmpty() ? Tr.t("Tens uma tarefa agora") : body)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(body == null ? "" : body))
                .setPriority(NotificationCompat.PRIORITY_HIGH).setSilent(!alarm && AppSettings.quiet(ctx) && !AppSettings.healthTitle(title))
                .setCategory(NotificationCompat.CATEGORY_REMINDER)
                .setAutoCancel(true)
                .setContentIntent(pi)
                .addAction(0, "Feito", Actions.pending(ctx, Actions.DONE, id, title, body, nid))
                .addAction(0, "Adiar " + AppSettings.snoozeMinutes(ctx) + " min", Actions.pending(ctx, Actions.SNOOZE, id, title, body, nid));
        if (alarm) {
            b.setCategory(NotificationCompat.CATEGORY_ALARM).setFullScreenIntent(pi, true).setTimeoutAfter(120000);
        }
        try {
            android.app.Notification nf = b.build();
            if (alarm) nf.flags |= android.app.Notification.FLAG_INSISTENT;
            ctx.getSystemService(NotificationManager.class).notify(nid, nf);
        } catch (SecurityException ignored) { }
    }

    /** Re-show this reminder in N minutes (local only; the server's due date is unchanged). */
    static void snooze(Context ctx, String id, String title, String body, int minutes) {
        long t = System.currentTimeMillis() + minutes * 60_000L;
        Intent in = new Intent(ctx, Alarm.class).setAction("snooze." + id)
                .putExtra("id", id).putExtra("title", title).putExtra("body", body).putExtra("due", "snooze-" + t);
        PendingIntent pi = PendingIntent.getBroadcast(ctx, Math.abs(("s" + id).hashCode()), in,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        AlarmManager am = ctx.getSystemService(AlarmManager.class);
        if (AppSettings.isAlarmTitle(ctx, title))
            am.setAlarmClock(new AlarmManager.AlarmClockInfo(t, PendingIntent.getActivity(ctx, 3,
                    new Intent(ctx, MainActivity.class), PendingIntent.FLAG_IMMUTABLE)), pi);
        else if (Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms())
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, t, pi);
        else
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, t, pi);
    }

    public static class Worker1 extends Worker {
        public Worker1(@NonNull Context c, @NonNull WorkerParameters p) { super(c, p); }

        @NonNull @Override
        public Result doWork() {
            return runSync(getApplicationContext()) ? Result.success() : Result.retry();
        }
    }

    private static final Object LOCK = new Object();

    /** Fetch notes (+ calendar) and (re)schedule reminders. Safe to call from any background thread. */
    static boolean runSync(Context ctx) {
        synchronized (LOCK) {
            try {
                String cookie = CookieManager.getInstance().getCookie(SITE);
                if (cookie == null || cookie.isEmpty()) return true;
                HttpURLConnection c = (HttpURLConnection) new URL(SITE + "/api/notes").openConnection();
                c.setConnectTimeout(10000);
                c.setReadTimeout(15000);
                c.setRequestProperty("Cookie", cookie);
                c.setRequestProperty("Accept", "application/json");
                if (c.getResponseCode() != 200) return false;
                byte[] data;
                try (InputStream in = c.getInputStream()) {
                    java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
                    byte[] buf = new byte[8192]; int r;
                    while ((r = in.read(buf)) > 0) bo.write(buf, 0, r);
                    data = bo.toByteArray();
                }
                try { if (AppSettings.calendarSync(ctx)) CalendarSync.sync(ctx, cookie); } catch (Exception ignored) { }
                JSONArray notes = new JSONObject(new String(data, "UTF-8")).getJSONArray("notes");
                long now = System.currentTimeMillis();
                AlarmManager am = ctx.getSystemService(AlarmManager.class);
                SharedPreferences sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
                Set<String> prev = new HashSet<>(sp.getStringSet("alarms", new HashSet<>()));
                Set<String> cur = new HashSet<>();
                java.util.List<JSONObject> upcoming = new java.util.ArrayList<>();
                java.util.Calendar d0 = java.util.Calendar.getInstance(); d0.set(java.util.Calendar.HOUR_OF_DAY, 0); d0.set(java.util.Calendar.MINUTE, 0); d0.set(java.util.Calendar.SECOND, 0);
                long dayStart = d0.getTimeInMillis(), dayEnd = dayStart + 86400000L;
                java.util.List<JSONObject> todayList = new java.util.ArrayList<>();
                for (int i = 0; i < notes.length(); i++) {
                    JSONObject n = notes.getJSONObject(i);
                    String due = NoteSync.s(n, "due_date", "");
                    if (due.isEmpty() || n.optBoolean("archived", false)) continue;
                    long t = parseDue(due);
                    if (t >= dayStart && t < dayEnd) todayList.add(new JSONObject().put("t", t).put("title", NoteSync.s(n, "title", "")));
                    if (t >= now - 3600_000L) {
                        upcoming.add(new JSONObject().put("id", n.optString("id")).put("title", NoteSync.s(n, "title", "")).put("t", t));
                    }
                    if (t < 0 || t < now - 6 * 3600_000L) continue;
                    String id = n.optString("id");
                    String title = NoteSync.s(n, "title", "");
                    String body = NoteSync.s(n, "content", "");
                    if (body.length() > 200) body = body.substring(0, 200) + "…";
                    if (t <= now + 30_000L) {
                        show(ctx, id, title, body, due);
                    } else {
                        Intent in = new Intent(ctx, Alarm.class).setAction("note." + id)
                                .putExtra("id", id).putExtra("title", title).putExtra("body", body).putExtra("due", due);
                        PendingIntent pi = PendingIntent.getBroadcast(ctx, Math.abs(id.hashCode()), in,
                                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
                        if (AppSettings.isAlarmTitle(ctx, title))
                            am.setAlarmClock(new AlarmManager.AlarmClockInfo(t, PendingIntent.getActivity(ctx, 3,
                                    new Intent(ctx, MainActivity.class), PendingIntent.FLAG_IMMUTABLE)), pi);
                        else if (Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms())
                            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, t, pi);
                        else
                            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, t, pi);
                        cur.add(id);
                    }
                }
                for (String old : prev) {
                    if (cur.contains(old)) continue;
                    Intent in = new Intent(ctx, Alarm.class).setAction("note." + old);
                    PendingIntent pi = PendingIntent.getBroadcast(ctx, Math.abs(old.hashCode()), in,
                            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_NO_CREATE);
                    if (pi != null) { am.cancel(pi); pi.cancel(); }
                }
                sp.edit().putStringSet("alarms", cur).apply();
                java.util.Collections.sort(todayList, (x, y) -> Long.compare(x.optLong("t"), y.optLong("t")));
                sp.edit().putString("today_items", new JSONArray(todayList).toString()).apply();
                java.util.Collections.sort(upcoming, (x, y) -> Long.compare(x.optLong("t"), y.optLong("t")));
                JSONArray w = new JSONArray();
                for (int i = 0; i < Math.min(upcoming.size(), 6); i++) w.put(upcoming.get(i));
                sp.edit().putString("widget_items", w.toString()).putLong("widget_at", now).apply();
                try {
                    java.util.List<JSONObject> nl = new java.util.ArrayList<>();
                    for (int i = 0; i < notes.length(); i++) { JSONObject n = notes.getJSONObject(i); if (!n.optBoolean("archived", false)) nl.add(n); }
                    java.util.Collections.sort(nl, (x, y) -> {
                        int pc = Boolean.compare(y.optBoolean("pinned", false), x.optBoolean("pinned", false));
                        return pc != 0 ? pc : NoteSync.s(y, "updated_at", "").compareTo(NoteSync.s(x, "updated_at", ""));
                    });
                    JSONArray ni = new JSONArray();
                    java.text.SimpleDateFormat iso = new java.text.SimpleDateFormat("yyyy-MM-dd", Locale.ROOT);
                    String today = iso.format(new java.util.Date()), yest = iso.format(new java.util.Date(now - 86400000L));
                    for (int i = 0; i < Math.min(nl.size(), 3); i++) {
                        JSONObject n = nl.get(i);
                        String u = n.optString("updated_at", NoteSync.s(n, "created_at", ""));
                        String day = u.length() >= 10 ? u.substring(0, 10) : "";
                        String when = day.equals(today) ? "Hoje" : day.equals(yest) ? "Ontem" : (day.length() == 10 ? day.substring(8) + "/" + day.substring(5, 7) : "");
                        String cc = NoteSync.s(n, "content", "").replace('\n', ' ').trim();
                        if (cc.length() > 70) cc = cc.substring(0, 70) + "…";
                        String t = NoteSync.s(n, "title", "").trim();
                        ni.put(new JSONObject().put("title", t.isEmpty() ? Tr.t("(sem título)") : t).put("when", when).put("preview", cc));
                    }
                    sp.edit().putString("notes_items", ni.toString()).apply();
                    Widgets.Notes.updateAll(ctx);
                } catch (Exception ignored) { }
                OdysseusWidget.updateAll(ctx);
                return true;
            } catch (Exception e) {
                return false;
            }
        }
    }

    public static class Alarm extends BroadcastReceiver {
        @Override
        public void onReceive(Context ctx, Intent i) {
            show(ctx, i.getStringExtra("id") == null ? "x" : i.getStringExtra("id"),
                    i.getStringExtra("title"), i.getStringExtra("body"),
                    i.getStringExtra("due") == null ? "" : i.getStringExtra("due"));
        }
    }
}
