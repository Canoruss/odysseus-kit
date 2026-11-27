package com.canorus.odysseus;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import org.json.JSONObject;

/**
 * Optional UnifiedPush receiver (https://unifiedpush.org) — 100% open-source & self-hosted,
 * zero Google/Firebase dependencies.
 *
 * When a user optionally pairs a self-hosted push distributor (e.g., ntfy / NextPush) on their phone,
 * incoming push messages immediately wake Odysseus to display the notification or trigger a targeted
 * single poll without any background polling battery cost. If unused, WorkManager handles everything.
 */
public class PushReceiver extends BroadcastReceiver {
    static final String ACTION_MESSAGE = "org.unifiedpush.android.connector.MESSAGE";
    static final String ACTION_NEW_ENDPOINT = "org.unifiedpush.android.connector.NEW_ENDPOINT";
    static final String ACTION_UNREGISTERED = "org.unifiedpush.android.connector.UNREGISTERED";

    @Override
    public void onReceive(Context ctx, Intent intent) {
        if (intent == null || intent.getAction() == null) return;
        final Context app = ctx.getApplicationContext();
        AppSettings.applyServer(app);
        String action = intent.getAction();

        if (ACTION_NEW_ENDPOINT.equals(action)) {
            String endpoint = intent.getStringExtra("url");
            if (endpoint != null && !endpoint.isEmpty()) {
                AppSettings.sp(app).edit().putString("unifiedpush_endpoint", endpoint).apply();
            }
            return;
        }
        if (ACTION_UNREGISTERED.equals(action)) {
            AppSettings.sp(app).edit().remove("unifiedpush_endpoint").apply();
            return;
        }
        if (ACTION_MESSAGE.equals(action)) {
            byte[] bytes = intent.getByteArrayExtra("bytesMessage");
            String raw = bytes != null
                    ? new String(bytes, java.nio.charset.StandardCharsets.UTF_8)
                    : intent.getStringExtra("message");
            final PendingResult pr = goAsync();
            Bg.run(() -> {
                try {
                    boolean handledDirect = false;
                    if (raw != null && raw.trim().startsWith("{")) {
                        JSONObject j = new JSONObject(raw);
                        String title = j.optString("title", "");
                        String body = j.optString("body", "");
                        String kind = j.optString("kind", "");
                        if ("notes".equals(kind)) {
                            NoteSync.runSync(app, true);
                            handledDirect = true;
                        } else if (!title.isEmpty() || !body.isEmpty()) {
                            if (!SyncService.appVisible) {
                                SyncService.notifyDone(app,
                                        "up|" + j.optString("id", String.valueOf(System.currentTimeMillis())),
                                        title.isEmpty() ? "Odysseus" : title,
                                        body);
                            }
                            handledDirect = true;
                        }
                    }
                    if (!handledDirect) {
                        SyncService.pollOnce(app);
                        NoteSync.runSync(app, false);
                    }
                } catch (Exception ignored) {
                } finally {
                    pr.finish();
                }
            });
        }
    }
}
