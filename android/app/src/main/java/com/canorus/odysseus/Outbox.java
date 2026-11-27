package com.canorus.odysseus;

import android.content.Context;
import android.content.SharedPreferences;
import android.webkit.CookieManager;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Local offline outbox queue: if the phone is temporarily offline or Tailscale hasn't
 * reconnected when creating a Quick Note, Quick Task, or Quick Expense from a widget,
 * the item is saved locally on the device and flushed automatically by WorkManager
 * as soon as connectivity returns. Zero data lost!
 */
final class Outbox {
    private Outbox() { }

    private static final String PREFS = "offline_outbox";
    private static final String KEY = "queue";
    private static final int MAX_ITEMS = 100;

    static synchronized void enqueue(Context ctx, String path, JSONObject payload) {
        try {
            SharedPreferences sp = ctx.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            JSONArray q = new JSONArray(sp.getString(KEY, "[]"));
            if (q.length() >= MAX_ITEMS) return;
            q.put(new JSONObject()
                    .put("path", path)
                    .put("body", payload.toString())
                    .put("ts", System.currentTimeMillis()));
            sp.edit().putString(KEY, q.toString()).apply();
            // Schedule WorkManager to flush automatically as soon as NetworkType.CONNECTED is satisfied
            NoteSync.enqueueImmediateWork(ctx.getApplicationContext());
        } catch (Exception ignored) { }
    }

    /** Flushes any queued offline items. Returns true if at least one note/task was synced. */
    static synchronized boolean flush(Context ctx) {
        if (!Bg.isOnline(ctx) || NoteSync.SITE == null || NoteSync.SITE.isEmpty()) return false;
        SharedPreferences sp = ctx.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String raw = sp.getString(KEY, "[]");
        if ("[]".equals(raw) || raw.isEmpty()) return false;
        String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
        if (cookie == null || cookie.isEmpty()) return false;

        boolean flushedNotes = false;
        try {
            JSONArray q = new JSONArray(raw);
            JSONArray remaining = new JSONArray();
            long cutoff = System.currentTimeMillis() - 14L * 86400_000L; // drop items older than 14 days
            for (int i = 0; i < q.length(); i++) {
                JSONObject item = q.optJSONObject(i);
                if (item == null || item.optLong("ts", 0) < cutoff) continue;
                String path = item.optString("path", "");
                String body = item.optString("body", "");
                if (path.isEmpty() || body.isEmpty()) continue;
                int code = Actions.send("POST", NoteSync.SITE + path, cookie, "application/json", body);
                if (code >= 200 && code < 300) {
                    if (path.startsWith("/api/notes")) flushedNotes = true;
                } else if (code == -1 || code >= 500) {
                    // Network or transient server error: keep in queue for next WorkManager run
                    remaining.put(item);
                }
                // 4xx client errors (e.g. 403) are not retried endlessly
            }
            sp.edit().putString(KEY, remaining.toString()).apply();
        } catch (Exception ignored) { }
        return flushedNotes;
    }
}
