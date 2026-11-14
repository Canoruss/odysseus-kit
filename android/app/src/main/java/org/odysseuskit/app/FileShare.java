package org.odysseuskit.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.Gravity;
import android.webkit.CookieManager;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import androidx.core.app.NotificationCompat;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Files the server shares with the logged-in Odysseus user (tools/share.py on the server).
 * Index: BASE/files/<user>/index.json. The app notifies about new files, asks
 * "Descarregar?" and saves the file into Transferências.
 */
public class FileShare {
    static final String CH = "odysseus_files";
    private static final String P_DONE = "fs_done";      // downloaded or ignored for good
    private static final String P_NOTIFIED = "fs_notified";
    private static final String P_USER = "fs_user";
    private static final Set<String> snoozed = new HashSet<>(); // Tr.t("Agora não"): ask again next app start
    private static boolean asking = false;
    private static final Set<String> downloading = new HashSet<>();
    static volatile Activity current; // set while the app is on screen

    static SharedPreferences prefs(Context c) {
        return c.getSharedPreferences(NoteSync.PREFS, Context.MODE_PRIVATE);
    }

    private static long userAt = 0;

    static String user(Context c) {
        String cached = prefs(c).getString(P_USER, null);
        if (cached != null && System.currentTimeMillis() - userAt < 10 * 60_000L) return cached;
        String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
        if (cookie == null) return cached;
        userAt = System.currentTimeMillis();
        try {
            String u = new JSONObject(NoteSync.httpGet(NoteSync.SITE + "/api/auth/status", cookie)).optString("username", "");
            u = u.toLowerCase().replaceAll("[^a-z0-9_-]", "");
            if (!u.isEmpty()) { prefs(c).edit().putString(P_USER, u).apply(); return u; }
        } catch (Exception ignored) { }
        return prefs(c).getString(P_USER, null);
    }

    /** Items for this user that were not downloaded/ignored yet. */
    static List<JSONObject> pending(Context c, String user) throws Exception {
        String s = NoteSync.httpGet(Updater.BASE + "files/" + user + "/index.json?t=" + System.currentTimeMillis(), "");
        JSONArray a = new JSONArray(s);
        Set<String> done = prefs(c).getStringSet(P_DONE, new HashSet<>());
        Set<String> live = new HashSet<>();
        List<JSONObject> out = new ArrayList<>();
        for (int i = 0; i < a.length(); i++) {
            JSONObject o = a.getJSONObject(i);
            live.add(o.optString("id"));
            if (!done.contains(o.optString("id"))) out.add(o);
        }
        prune(c, P_DONE, live);
        prune(c, P_NOTIFIED, live);
        return out;
    }

    /** Forget ids the server already deleted (files expire after 7 days). */
    private static void prune(Context c, String key, Set<String> live) {
        Set<String> s = new HashSet<>(prefs(c).getStringSet(key, new HashSet<>()));
        if (s.retainAll(live)) prefs(c).edit().putStringSet(key, s).apply();
    }

    private static void mark(Context c, String key, String id) {
        Set<String> s = new HashSet<>(prefs(c).getStringSet(key, new HashSet<>()));
        s.add(id);
        prefs(c).edit().putStringSet(key, s).apply();
    }

    static String human(long b) {
        if (b < 1024) return b + " B";
        if (b < 1024 * 1024) return (b / 1024) + " KB";
        return String.format("%.1f MB", b / 1048576.0);
    }

    /** From the background service: notify once per new file. */
    /** Every file currently shared with this user (for the settings screen). */
    static JSONArray all(Context c, String user) throws Exception {
        return new JSONArray(NoteSync.httpGet(Updater.BASE + "files/" + user + "/index.json?t=" + System.currentTimeMillis(), ""));
    }

    static boolean isDone(Context c, String id) {
        return prefs(c).getStringSet(P_DONE, new HashSet<>()).contains(id);
    }

    static void poll(Context c, boolean appVisible) {
        try {
            String u = user(c);
            if (u == null) return;
            Set<String> notified = prefs(c).getStringSet(P_NOTIFIED, new HashSet<>());
            for (JSONObject o : pending(c, u)) {
                String id = o.optString("id");
                if (notified.contains(id)) continue;
                mark(c, P_NOTIFIED, id);
                if (!appVisible && AppSettings.fileNotifications(c)) notifyNew(c, o);
            }
            Activity a = current;
            if (appVisible && a != null) prompt(a);
        } catch (Exception ignored) { }
    }

    private static void notifyNew(Context c, JSONObject o) {
        NotificationManager nm = c.getSystemService(NotificationManager.class);
        if (Build.VERSION.SDK_INT >= 26) nm.createNotificationChannel(new NotificationChannel(CH, "Ficheiros partilhados", NotificationManager.IMPORTANCE_HIGH));
        PendingIntent pi = PendingIntent.getActivity(c, 3, new Intent(c, MainActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP), PendingIntent.FLAG_IMMUTABLE);
        String txt = o.optString("name") + " (" + human(o.optLong("size")) + Tr.t(") — toca para descarregar");
        android.app.Notification n = new NotificationCompat.Builder(c, CH)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle(Tr.t("Novo ficheiro para ti")).setContentText(txt)
            .setStyle(new NotificationCompat.BigTextStyle().bigText(txt))
            .setPriority(NotificationCompat.PRIORITY_HIGH).setSilent(AppSettings.quiet(c)).setAutoCancel(true).setContentIntent(pi).build();
        try { nm.notify(Math.abs(o.optString("id").hashCode()), n); } catch (SecurityException ignored) { }
    }

    /** From the activity (onResume): ask about the first pending file. */
    static void prompt(Activity act) {
        if (asking) return;
        new Thread(() -> {
            try {
                String u = user(act);
                if (u == null) return;
                for (JSONObject o : pending(act, u)) {
                    if (snoozed.contains(o.optString("id")) || downloading.contains(o.optString("id"))) continue;
                    act.runOnUiThread(() -> ask(act, u, o));
                    return;
                }
            } catch (Exception ignored) { }
        }).start();
    }

    private static void ask(Activity act, String user, JSONObject o) {
        if (act.isFinishing() || asking) return;
        asking = true;
        String note = o.optString("note", "").trim();
        String msg = o.optString("name") + "\n" + human(o.optLong("size")) + (note.isEmpty() ? "" : "\n\n" + note)
            + Tr.t("\n\nQueres descarregar para a pasta Transferências?");
        new AlertDialog.Builder(act).setTitle("Novo ficheiro")
            .setMessage(msg)
            .setPositiveButton("Descarregar", (d, w) -> { asking = false; download(act, user, o); })
            .setNegativeButton(Tr.t("Agora não"), (d, w) -> { asking = false; snoozed.add(o.optString("id")); })
            .setNeutralButton("Ignorar", (d, w) -> { asking = false; mark(act, P_DONE, o.optString("id")); })
            .setOnCancelListener(d -> { asking = false; snoozed.add(o.optString("id")); })
            .show();
    }

    static void download(Activity act, String user, JSONObject o) {
        downloading.add(o.optString("id"));
        LinearLayout box = new LinearLayout(act);
        box.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (20 * act.getResources().getDisplayMetrics().density);
        box.setPadding(pad, pad, pad, pad / 2);
        ProgressBar bar = new ProgressBar(act, null, android.R.attr.progressBarStyleHorizontal);
        bar.setMax(100);
        TextView label = new TextView(act);
        label.setGravity(Gravity.END);
        label.setText("0%");
        box.addView(bar);
        box.addView(label);
        AlertDialog dlg = new AlertDialog.Builder(act).setTitle("A descarregar…").setView(box).setCancelable(false).show();
        new Thread(() -> {
            File tmp = new File(act.getCacheDir(), "share.tmp");
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(Updater.BASE + "files/" + user + "/" + o.getString("file")).openConnection();
                c.setConnectTimeout(15000);
                c.setReadTimeout(30000);
                if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
                long total = c.getContentLengthLong();
                MessageDigest sha = MessageDigest.getInstance("SHA-256");
                try (InputStream in = c.getInputStream(); OutputStream os = new FileOutputStream(tmp)) {
                    byte[] buf = new byte[64 * 1024];
                    long done = 0;
                    int n, last = -1;
                    while ((n = in.read(buf)) > 0) {
                        os.write(buf, 0, n);
                        sha.update(buf, 0, n);
                        done += n;
                        int p = total > 0 ? (int) (done * 100 / total) : 0;
                        if (p != last) { last = p; act.runOnUiThread(() -> { bar.setProgress(p); label.setText(p + "%"); }); }
                    }
                }
                StringBuilder sb = new StringBuilder();
                for (byte x : sha.digest()) sb.append(String.format("%02x", x));
                String want = o.optString("sha256", "").toLowerCase();
                if (!want.isEmpty() && !want.equals(sb.toString())) throw new Exception("ficheiro corrompido");
                Uri saved = save(act, tmp, o.optString("name", "ficheiro"), o.optString("mime", "application/octet-stream"));
                mark(act, P_DONE, o.optString("id"));
                act.runOnUiThread(() -> {
                    dlg.dismiss();
                    Toast.makeText(act, Tr.t("Guardado em Transferências: ") + o.optString("name"), Toast.LENGTH_LONG).show();
                });
                notifySaved(act, o, saved);
            } catch (Exception e) {
                act.runOnUiThread(() -> { dlg.dismiss(); Toast.makeText(act, "Falha ao descarregar: " + e.getMessage(), Toast.LENGTH_LONG).show(); });
            } finally {
                downloading.remove(o.optString("id"));
                tmp.delete();
            }
        }).start();
    }

    private static Uri save(Context c, File src, String name, String mime) throws Exception {
        name = name.replaceAll("[\\\\/:*?\"<>|]", "_");
        byte[] buf = new byte[64 * 1024];
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues v = new ContentValues();
            v.put(MediaStore.Downloads.DISPLAY_NAME, name);
            v.put(MediaStore.Downloads.MIME_TYPE, mime);
            v.put(MediaStore.Downloads.IS_PENDING, 1);
            Uri uri = c.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
            if (uri == null) throw new Exception("MediaStore insert failed");
            try (InputStream in = new java.io.FileInputStream(src); OutputStream os = c.getContentResolver().openOutputStream(uri)) {
                int n;
                while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
            }
            v.clear();
            v.put(MediaStore.Downloads.IS_PENDING, 0);
            c.getContentResolver().update(uri, v, null, null);
            return uri;
        }
        File dir = c.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        File dst = new File(dir, name);
        try (InputStream in = new java.io.FileInputStream(src); OutputStream os = new FileOutputStream(dst)) {
            int n;
            while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
        }
        return Uri.fromFile(dst);
    }

    private static void notifySaved(Context c, JSONObject o, Uri uri) {
        try {
            NotificationManager nm = c.getSystemService(NotificationManager.class);
            if (Build.VERSION.SDK_INT >= 26) nm.createNotificationChannel(new NotificationChannel(CH, "Ficheiros partilhados", NotificationManager.IMPORTANCE_HIGH));
            Intent view = new Intent(Intent.ACTION_VIEW).setDataAndType(uri, o.optString("mime", "*/*"))
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            PendingIntent pi = PendingIntent.getActivity(c, 4, view, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            android.app.Notification n = new NotificationCompat.Builder(c, CH)
                .setSmallIcon(android.R.drawable.stat_sys_download_done)
                .setContentTitle("Ficheiro guardado").setContentText(o.optString("name") + Tr.t(" — toca para abrir"))
                .setAutoCancel(true).setContentIntent(pi).build();
            nm.notify(Math.abs(("saved" + o.optString("id")).hashCode()), n);
        } catch (Exception ignored) { }
    }
}
