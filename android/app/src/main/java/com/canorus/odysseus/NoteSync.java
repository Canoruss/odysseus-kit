package com.canorus.odysseus;

import android.app.AlarmManager;
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
import androidx.core.content.ContextCompat;
import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.ExistingWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.text.SimpleDateFormat;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Collections;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * Native reminders & Doze-friendly background orchestrator:
 * - Uses WorkManager with NetworkType.CONNECTED + exponential backoff.
 * - Hashes `/api/notes` payloads so unchanged notes skip AlarmManager rescheduling & widget broadcasts!
 * - Decouples heavy HealthConnect queries (handled exclusively by HealthWorker) and throttles CalendarSync.
 */
public class NoteSync {
    static { System.loadLibrary("odysseus_voice"); }
    private static native int nativeClassifyNote(long due, long now, long dayStart, long dayEnd);
    private static final int NOTE_TODAY = 1, NOTE_UPCOMING = 2, NOTE_SHOW = 4, NOTE_SCHEDULE = 8;
    static String SITE = "";
    static final String CHANNEL = Channels.REMINDERS;
    static final String PREFS = "note_sync";
    private static final long MIN_CALENDAR_SYNC_INTERVAL_MS = 15 * 60_000L;
    private static volatile long lastCalendarSyncMs = 0;

    static void schedule(Context ctx) {
        if (!AppSettings.setupDone(ctx)) return;
        Constraints netConstraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        WorkManager wm = WorkManager.getInstance(ctx);
        PeriodicWorkRequest periodic = new PeriodicWorkRequest.Builder(Worker1.class, 15, TimeUnit.MINUTES, 5, TimeUnit.MINUTES)
                .setConstraints(netConstraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 1, TimeUnit.MINUTES)
                .build();
        wm.enqueueUniquePeriodicWork("note-sync", ExistingPeriodicWorkPolicy.KEEP, periodic);
    }

    static void enqueueImmediateWork(Context ctx) {
        if (!AppSettings.setupDone(ctx)) return;
        Constraints netConstraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build();
        OneTimeWorkRequest once = new OneTimeWorkRequest.Builder(Worker1.class)
                .setConstraints(netConstraints)
                .build();
        WorkManager.getInstance(ctx).enqueueUniqueWork("note-sync-now", ExistingWorkPolicy.KEEP, once);
    }

    static String s(JSONObject o, String k, String d) {
        return (o == null || o.isNull(k)) ? d : o.optString(k, d);
    }

    static String httpGet(String url, String cookie) throws Exception {
        return Http.getString(url, cookie);
    }

    static int httpCode(String url, String cookie) {
        return Http.headOrGetCode(url, cookie, 8000);
    }

    /** Triggered on explicit user note/calendar mutations or widget taps. */
    static void syncNow(Context ctx) {
        final Context app = ctx.getApplicationContext();
        Bg.run(() -> runSync(app, true));
    }

    static void ensureChannel(Context ctx) {
        Channels.ensureAll(ctx);
    }

    static long parseDue(String s) {
        if (s == null || s.isEmpty()) return -1;
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
            Iterator<String> it = done.iterator();
            while (it.hasNext()) {
                String k = it.next();
                int idx = k.indexOf('|');
                long t = idx >= 0 ? parseDue(k.substring(idx + 1)) : -1;
                if (t > 0 && t < cutoff) it.remove();
            }
        }
        sp.edit().putStringSet("notified", done).apply();

        boolean alarm = AppSettings.isAlarmTitle(ctx, title);
        if (alarm) {
            try {
                ContextCompat.startForegroundService(ctx, new Intent(ctx, AlarmService.class)
                        .putExtra("id", id).putExtra("title", title).putExtra("body", body));
                return;
            } catch (Exception ignored) { /* fall back to a normal notification below */ }
        }
        if (!alarm && !AppSettings.reminders(ctx)) return;
        Channels.ensureAll(ctx);
        Intent open = new Intent(ctx, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(ctx, 0, open,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        int nid = Math.abs(id.hashCode());
        NotificationCompat.Builder b = new NotificationCompat.Builder(ctx, alarm ? Channels.ALARMS : CHANNEL)
                .setSmallIcon(android.R.drawable.ic_popup_reminder)
                .setContentTitle(title == null || title.isEmpty() ? L.t("Lembrete") : title)
                .setContentText(body == null || body.isEmpty() ? L.t("Tens uma tarefa agora") : body)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(body == null ? "" : body))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setOnlyAlertOnce(true)
                .setSilent(!alarm && AppSettings.quiet(ctx) && !AppSettings.healthTitle(title))
                .setCategory(NotificationCompat.CATEGORY_REMINDER)
                .setAutoCancel(true)
                .setContentIntent(pi)
                .addAction(0, L.t("Feito"), Actions.pending(ctx, Actions.DONE, id, title, body, nid))
                .addAction(0, L.t("Adiar ") + AppSettings.snoozeMinutes(ctx) + " min",
                        Actions.pending(ctx, Actions.SNOOZE, id, title, body, nid));
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
            Context app = getApplicationContext();
            AppSettings.applyServer(app);
            if (!Bg.isOnline(app)) return Result.retry();
            // Run chat/task/file notifications inside the same batched WorkManager wakeup!
            boolean flushed = Outbox.flush(app);
            try { SyncService.pollOnce(app); } catch (Exception ignored) { }
            GlucoseWidget.refreshIfAdded(app);
            return runSync(app, flushed) ? Result.success() : Result.retry();
        }
    }

    private static final Object LOCK = new Object();

    static boolean runSync(Context ctx) {
        return runSync(ctx, false);
    }

    private static String sha256Hex(byte[] data, String extra) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            md.update(data);
            if (extra != null) md.update(extra.getBytes(StandardCharsets.UTF_8));
            byte[] d = md.digest();
            StringBuilder sb = new StringBuilder(d.length * 2);
            for (byte b : d) sb.append(String.format(Locale.ROOT, "%02x", b));
            return sb.toString();
        } catch (Exception e) {
            return String.valueOf(java.util.Arrays.hashCode(data));
        }
    }

    /**
     * Fetch notes (+ throttled calendar) and diff reminders/widgets so unchanged payloads do zero
     * AlarmManager or AppWidgetManager work.
     */
    static boolean runSync(Context ctx, boolean forceCalendar) {
        synchronized (LOCK) {
            try {
                if (!Bg.isOnline(ctx) || SITE == null || SITE.isEmpty()) return true;
                String cookie = CookieManager.getInstance().getCookie(SITE);
                if (cookie == null || cookie.isEmpty()) return true;

                long now = System.currentTimeMillis();
                if (AppSettings.calendarSync(ctx)
                        && (forceCalendar || now - lastCalendarSyncMs >= MIN_CALENDAR_SYNC_INTERVAL_MS)) {
                    lastCalendarSyncMs = now;
                    try { CalendarSync.sync(ctx, cookie); } catch (Exception ignored) { }
                }

                Http.Resp resp = Http.getConditional(SITE + "/api/notes", cookie, 10000, 15000);
                if (resp.code != 200 || resp.bytes == null) return false;

                SharedPreferences sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
                SimpleDateFormat iso = new SimpleDateFormat("yyyy-MM-dd", Locale.ROOT);
                String todayIso = iso.format(new Date(now));
                String payloadHash = sha256Hex(resp.bytes, todayIso + "|" + AppSettings.alarmWords(ctx) + "|" + L.lang());

                // Fast-path: if neither notes payload, date, alarm keywords, nor language changed,
                // only check if any due note crossed `now` without touching AlarmManager or Widgets!
                if (!forceCalendar && (resp.notModified || payloadHash.equals(sp.getString("notes_hash", "")))) {
                    return true;
                }

                JSONArray notes = new JSONObject(resp.text()).getJSONArray("notes");
                AlarmManager am = ctx.getSystemService(AlarmManager.class);

                JSONObject prevSpecs;
                try { prevSpecs = new JSONObject(sp.getString("alarm_specs", "{}")); }
                catch (Exception e) { prevSpecs = new JSONObject(); }
                JSONObject nextSpecs = new JSONObject();

                Set<String> prevAlarms = new HashSet<>(sp.getStringSet("alarms", new HashSet<>()));
                Set<String> curAlarms = new HashSet<>();
                List<JSONObject> upcoming = new ArrayList<>();

                Calendar d0 = Calendar.getInstance();
                d0.set(Calendar.HOUR_OF_DAY, 0);
                d0.set(Calendar.MINUTE, 0);
                d0.set(Calendar.SECOND, 0);
                d0.set(Calendar.MILLISECOND, 0);
                long dayStart = d0.getTimeInMillis(), dayEnd = dayStart + 86400000L;
                List<JSONObject> todayList = new ArrayList<>();

                for (int i = 0; i < notes.length(); i++) {
                    JSONObject n = notes.getJSONObject(i);
                    String due = NoteSync.s(n, "due_date", "");
                    if (due.isEmpty() || n.optBoolean("archived", false)) continue;
                    long t = parseDue(due);
                    int classification = nativeClassifyNote(t, now, dayStart, dayEnd);
                    if ((classification & NOTE_TODAY) != 0) {
                        todayList.add(new JSONObject().put("t", t).put("title", NoteSync.s(n, "title", "")));
                    }
                    if ((classification & NOTE_UPCOMING) != 0) {
                        upcoming.add(new JSONObject().put("id", n.optString("id")).put("title", NoteSync.s(n, "title", "")).put("t", t));
                    }
                    if ((classification & (NOTE_SHOW | NOTE_SCHEDULE)) == 0) continue;
                    String id = n.optString("id");
                    String title = NoteSync.s(n, "title", "");
                    String body = NoteSync.s(n, "content", "");
                    if (body.length() > 200) body = body.substring(0, 200) + "…";
                    if ((classification & NOTE_SHOW) != 0) {
                        show(ctx, id, title, body, due);
                    } else {
                        boolean isAl = AppSettings.isAlarmTitle(ctx, title);
                        String spec = t + "|" + isAl + "|" + title + "|" + body;
                        nextSpecs.put(id, spec);
                        curAlarms.add(id);

                        // Only call AlarmManager if this reminder's schedule/spec actually changed!
                        if (!spec.equals(prevSpecs.optString(id, ""))) {
                            Intent in = new Intent(ctx, Alarm.class).setAction("note." + id)
                                    .putExtra("id", id).putExtra("title", title).putExtra("body", body).putExtra("due", due);
                            PendingIntent pi = PendingIntent.getBroadcast(ctx, Math.abs(id.hashCode()), in,
                                    PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
                            if (isAl)
                                am.setAlarmClock(new AlarmManager.AlarmClockInfo(t, PendingIntent.getActivity(ctx, 3,
                                        new Intent(ctx, MainActivity.class), PendingIntent.FLAG_IMMUTABLE)), pi);
                            else if (Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms())
                                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, t, pi);
                            else
                                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, t, pi);
                        }
                    }
                }

                for (String old : prevAlarms) {
                    if (curAlarms.contains(old)) continue;
                    Intent in = new Intent(ctx, Alarm.class).setAction("note." + old);
                    PendingIntent pi = PendingIntent.getBroadcast(ctx, Math.abs(old.hashCode()), in,
                            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_NO_CREATE);
                    if (pi != null) { am.cancel(pi); pi.cancel(); }
                }

                Collections.sort(todayList, (x, y) -> Long.compare(x.optLong("t"), y.optLong("t")));
                Collections.sort(upcoming, (x, y) -> Long.compare(x.optLong("t"), y.optLong("t")));
                JSONArray w = new JSONArray();
                for (int i = 0; i < Math.min(upcoming.size(), 6); i++) w.put(upcoming.get(i));
                String newWidgetItems = w.toString();
                boolean tasksWidgetChanged = !newWidgetItems.equals(sp.getString("widget_items", ""));

                String newNotesItems = null;
                boolean notesWidgetChanged = false;
                try {
                    List<JSONObject> nl = new ArrayList<>();
                    for (int i = 0; i < notes.length(); i++) {
                        JSONObject n = notes.getJSONObject(i);
                        if (!n.optBoolean("archived", false)) nl.add(n);
                    }
                    Collections.sort(nl, (x, y) -> {
                        int pc = Boolean.compare(y.optBoolean("pinned", false), x.optBoolean("pinned", false));
                        return pc != 0 ? pc : NoteSync.s(y, "updated_at", "").compareTo(NoteSync.s(x, "updated_at", ""));
                    });
                    JSONArray ni = new JSONArray();
                    String yestIso = iso.format(new Date(now - 86400000L));
                    for (int i = 0; i < Math.min(nl.size(), 3); i++) {
                        JSONObject n = nl.get(i);
                        String u = n.optString("updated_at", NoteSync.s(n, "created_at", ""));
                        String day = u.length() >= 10 ? u.substring(0, 10) : "";
                        String when = day.equals(todayIso) ? L.t("Hoje") : day.equals(yestIso) ? L.t("Ontem") : (day.length() == 10 ? day.substring(8) + "/" + day.substring(5, 7) : "");
                        String cc = NoteSync.s(n, "content", "").replace('\n', ' ').trim();
                        if (cc.length() > 70) cc = cc.substring(0, 70) + "…";
                        String t = NoteSync.s(n, "title", "").trim();
                        ni.put(new JSONObject().put("title", t.isEmpty() ? L.t("(sem título)") : t).put("when", when).put("preview", cc));
                    }
                    newNotesItems = ni.toString();
                    notesWidgetChanged = !newNotesItems.equals(sp.getString("notes_items", ""));
                } catch (Exception ignored) { }

                // Batch all SharedPreferences writes into a single atomic .apply()
                SharedPreferences.Editor ed = sp.edit()
                        .putString("notes_hash", payloadHash)
                        .putString("alarm_specs", nextSpecs.toString())
                        .putStringSet("alarms", curAlarms)
                        .putString("today_items", new JSONArray(todayList).toString())
                        .putString("widget_items", newWidgetItems)
                        .putLong("widget_at", now);
                if (newNotesItems != null) ed.putString("notes_items", newNotesItems);
                ed.apply();

                // Only wake Launcher / RemoteViews when widget content actually changed!
                if (notesWidgetChanged) Widgets.Notes.updateAll(ctx);
                if (tasksWidgetChanged) OdysseusWidget.updateAll(ctx);
                return true;
            } catch (Exception e) {
                return false;
            }
        }
    }

    public static class Alarm extends BroadcastReceiver {
        @Override
        public void onReceive(Context ctx, Intent i) {
            AppSettings.applyServer(ctx);
            show(ctx, i.getStringExtra("id") == null ? "x" : i.getStringExtra("id"),
                    i.getStringExtra("title"), i.getStringExtra("body"),
                    i.getStringExtra("due") == null ? "" : i.getStringExtra("due"));
        }
    }
}
