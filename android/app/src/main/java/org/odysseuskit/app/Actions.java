package org.odysseuskit.app;

import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.widget.Toast;

import androidx.core.app.NotificationCompat;
import androidx.core.app.RemoteInput;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** Buttons on notifications: "Feito", "Adiar", and the inline reply of "Resposta pronta". */
public class Actions extends BroadcastReceiver {
    static final String DONE = "org.odysseuskit.app.DONE";
    static final String SNOOZE = "org.odysseuskit.app.SNOOZE";
    static final String REPLY = "org.odysseuskit.app.REPLY";
    static final String KEY_REPLY = "reply_text";

    static PendingIntent pending(Context c, String action, String id, String title, String body, int nid) {
        Intent i = new Intent(c, Actions.class).setAction(action)
                .putExtra("id", id).putExtra("title", title).putExtra("body", body).putExtra("nid", nid);
        return PendingIntent.getBroadcast(c, (action + id).hashCode(), i,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    /** Reply action for a chat notification (needs a MUTABLE intent so Android can add the typed text). */
    static NotificationCompat.Action replyAction(Context c, String sessionId, int nid) {
        Intent i = new Intent(c, Actions.class).setAction(REPLY).putExtra("id", sessionId).putExtra("nid", nid);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
        PendingIntent pi = PendingIntent.getBroadcast(c, ("r" + sessionId).hashCode(), i, flags);
        RemoteInput ri = new RemoteInput.Builder(KEY_REPLY).setLabel("Escreve a resposta…").build();
        return new NotificationCompat.Action.Builder(0, "Responder", pi).addRemoteInput(ri).setAllowGeneratedReplies(false).build();
    }

    @Override
    public void onReceive(Context ctx, Intent intent) {
        String action = intent.getAction();
        String id = intent.getStringExtra("id");
        int nid = intent.getIntExtra("nid", 0);
        if (action == null || id == null) return;
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        switch (action) {
            case DONE: {
                nm.cancel(nid);
                PendingResult pr = goAsync();
                new Thread(() -> {
                    try {
                        String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
                        int code = send("PUT", NoteSync.SITE + "/api/notes/" + id, cookie, "application/json", "{\"archived\":true}");
                        if (code != 200) toast(ctx, Tr.t("Não foi possível marcar como feito (") + code + ")");
                        NoteSync.runSync(ctx.getApplicationContext());
                    } finally { pr.finish(); }
                }).start();
                break;
            }
            case SNOOZE: {
                nm.cancel(nid);
                int m = AppSettings.snoozeMinutes(ctx);
                NoteSync.snooze(ctx, id, intent.getStringExtra("title"), intent.getStringExtra("body"), m);
                Toast.makeText(ctx, "Adiado " + m + " minutos", Toast.LENGTH_SHORT).show();
                break;
            }
            case REPLY: {
                Bundle r = RemoteInput.getResultsFromIntent(intent);
                CharSequence text = r == null ? null : r.getCharSequence(KEY_REPLY);
                if (text == null || text.toString().trim().isEmpty()) return;
                SyncService.sendReply(ctx, id, text.toString().trim());
                // Replace the notification so the reply spinner stops.
                nm.notify(nid, new NotificationCompat.Builder(ctx, SyncService.CH_CHAT)
                        .setSmallIcon(android.R.drawable.stat_notify_chat)
                        .setContentTitle("Mensagem enviada")
                        .setContentText("Aviso quando a resposta estiver pronta.")
                        .setTimeoutAfter(5000).build());
                break;
            }
        }
    }

    static int send(String method, String url, String cookie, String type, String body) {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
            c.setRequestMethod(method);
            c.setConnectTimeout(10000);
            c.setReadTimeout(20000);
            if (cookie != null) c.setRequestProperty("Cookie", cookie);
            c.setRequestProperty("Content-Type", type);
            c.setDoOutput(true);
            try (OutputStream os = c.getOutputStream()) { os.write(body.getBytes("UTF-8")); }
            return c.getResponseCode();
        } catch (Exception e) {
            return -1;
        }
    }

    private static void toast(Context c, String m) {
        new android.os.Handler(android.os.Looper.getMainLooper()).post(() -> Toast.makeText(c, m, Toast.LENGTH_LONG).show());
    }
}
