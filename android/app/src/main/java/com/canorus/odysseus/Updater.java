package com.canorus.odysseus;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;
import androidx.core.content.pm.PackageInfoCompat;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import org.json.JSONObject;

/**
 * Self-updater. Reads BASE/version.json:
 *   {"versionCode": 3, "versionName": "1.2", "apk": "Odysseus-1.2.apk", "sha256": "...", "notes": "..."}
 * If versionCode is newer than the installed one, asks the user, downloads the APK,
 * checks the SHA-256 and installs it with PackageInstaller (Android also checks that
 * the signature matches the installed app).
 */
public class Updater {

    static String BASE = "";
    static final String ACTION_STATUS = "com.canorus.odysseus.INSTALL_STATUS";
    private static final long CHECK_INTERVAL_MS = 30 * 60 * 1000L;

    private final Activity act;
    private long lastCheck = 0;
    private boolean busy = false;
    private int dismissedCode = -1; // L.t("Mais tarde") -> don't ask again for this version until the app restarts
    private File pendingApk = null; // waiting for "install unknown apps" permission

    Updater(Activity act) {
        this.act = act;
    }

    long installedCode() {
        try {
            return PackageInfoCompat.getLongVersionCode(act.getPackageManager().getPackageInfo(act.getPackageName(), 0));
        } catch (PackageManager.NameNotFoundException e) {
            return 0;
        }
    }

    /** Called from onResume. */
    void onResume() {
        if (pendingApk != null && canInstall()) {
            File f = pendingApk;
            pendingApk = null;
            install(f);
            return;
        }
        long now = System.currentTimeMillis();
        if (busy || now - lastCheck < CHECK_INTERVAL_MS) return;
        lastCheck = now;
        check(false);
    }

    /** manual = true shows "already up to date" feedback. */
    void check(boolean manual) {
        if (busy) return;
        Bg.run(() -> {
            try {
                JSONObject j = new JSONObject(new String(get(BASE + "version.json?t=" + System.currentTimeMillis()), "UTF-8"));
                int code = j.optInt("versionCode", 0);
                String remoteSha = j.optString("sha256", "").toLowerCase(java.util.Locale.ROOT);
                String lastSha = AppSettings.sp(act).getString("installed_sha256", "");
                boolean newer = code > installedCode() || (manual && code == installedCode() && !remoteSha.isEmpty() && !remoteSha.equals(lastSha));
                if (newer && (manual || code != dismissedCode)) {
                    act.runOnUiThread(() -> ask(j));
                } else if (manual) {
                    toast(L.t("A app já está na versão mais recente."));
                }
            } catch (Exception e) {
                if (manual) toast(L.t("Não foi possível procurar atualizações: ") + e.getMessage());
            }
        });
    }

    private void ask(JSONObject j) {
        if (act.isFinishing()) return;
        String name = j.optString("versionName", String.valueOf(j.optInt("versionCode")));
        String notes = j.optString("notes", "").trim();
        String msg = (notes.isEmpty() ? "" : notes + "\n\n") + L.t("Queres descarregar e instalar agora?");
        new AlertDialog.Builder(act)
            .setTitle(L.t("Nova versão do Odysseus: ") + name)
            .setMessage(msg)
            .setCancelable(true)
            .setPositiveButton(L.t("Atualizar"), (d, w) -> { askNotificationPermission(); download(j); })
            .setNegativeButton(L.t("Mais tarde"), (d, w) -> dismissedCode = j.optInt("versionCode"))
            .show();
    }

    private void download(JSONObject j) {
        busy = true;
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
        AlertDialog dlg = new AlertDialog.Builder(act).setTitle(L.t("A descarregar atualização…")).setView(box).setCancelable(false).show();

        Bg.run(() -> {
            File out = new File(act.getCacheDir(), "update.apk");
            HttpURLConnection c = null;
            try {
                c = (HttpURLConnection) new URL(BASE + j.getString("apk")).openConnection();
                c.setConnectTimeout(15000);
                c.setReadTimeout(30000);
                if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
                long total = c.getContentLengthLong();
                MessageDigest sha = MessageDigest.getInstance("SHA-256");
                try (InputStream in = c.getInputStream(); OutputStream os = new FileOutputStream(out)) {
                    byte[] buf = new byte[64 * 1024];
                    long done = 0;
                    int n, last = -1;
                    while ((n = in.read(buf)) > 0) {
                        os.write(buf, 0, n);
                        sha.update(buf, 0, n);
                        done += n;
                        if (total > 0) {
                            int p = (int) (done * 100 / total);
                            if (p != last) {
                                last = p;
                                act.runOnUiThread(() -> { bar.setProgress(p); label.setText(p + "%"); });
                            }
                        }
                    }
                }
                String want = j.optString("sha256", "").toLowerCase();
                String got = hex(sha.digest());
                if (!want.isEmpty() && !want.equals(got)) throw new Exception(L.t("ficheiro corrompido (SHA-256 não confere)"));
                if (!got.isEmpty()) AppSettings.sp(act).edit().putString("installed_sha256", got).apply();
                act.runOnUiThread(() -> { dlg.dismiss(); install(out); });
            } catch (Exception e) {
                busy = false;
                out.delete();
                act.runOnUiThread(() -> { dlg.dismiss(); toast(L.t("Falha ao descarregar a atualização: ") + e.getMessage()); });
            } finally {
                if (c != null) c.disconnect();
            }
        });
    }

    private boolean canInstall() {
        return Build.VERSION.SDK_INT < 26 || act.getPackageManager().canRequestPackageInstalls();
    }

    private void install(File apk) {
        if (!canInstall()) {
            pendingApk = apk;
            new AlertDialog.Builder(act)
                .setTitle(L.t("Permitir atualizações"))
                .setMessage(L.t("Para o Odysseus se atualizar sozinho, ativa \"Permitir desta fonte\" no ecrã seguinte e volta à app. Só é preciso fazer isto uma vez."))
                .setPositiveButton(L.t("Abrir definições"), (d, w) -> act.startActivity(
                    new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + act.getPackageName()))))
                .setNegativeButton(L.t("Cancelar"), (d, w) -> { pendingApk = null; busy = false; })
                .show();
            return;
        }
        try {
            PackageInstaller pi = act.getPackageManager().getPackageInstaller();
            PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
            params.setAppPackageName(act.getPackageName());
            if (Build.VERSION.SDK_INT >= 31) {
                // After the first in-app update this app is the installer of record, so
                // Android 12+ installs later updates without asking again.
                params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED);
            }
            int id = pi.createSession(params);
            try (PackageInstaller.Session s = pi.openSession(id)) {
                try (InputStream in = new FileInputStream(apk); OutputStream os = s.openWrite("base.apk", 0, apk.length())) {
                    byte[] buf = new byte[64 * 1024];
                    int n;
                    while ((n = in.read(buf)) > 0) os.write(buf, 0, n);
                    s.fsync(os);
                }
                Intent status = new Intent(ACTION_STATUS).setPackage(act.getPackageName());
                int flags = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
                PendingIntent pi2 = PendingIntent.getBroadcast(act, id, status, flags);
                s.commit(pi2.getIntentSender());
            }
            busy = false; // the system owns the install from here on
            toast(L.t("A instalar a atualização… a app fecha por um instante e avisa quando estiver pronta."));
        } catch (Exception e) {
            busy = false;
            toast(L.t("Falha ao instalar: ") + e.getMessage());
        }
    }

    private void toast(String m) {
        act.runOnUiThread(() -> Toast.makeText(act, m, Toast.LENGTH_LONG).show());
    }

    private static byte[] get(String url) throws Exception {
        return Http.getBytesNoCache(url, 10000, 10000);
    }

    private static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder();
        for (byte x : b) sb.append(String.format("%02x", x));
        return sb.toString();
    }

    /** Android 13+: needed so the "updated, tap to open" notification can be shown. */
    private void askNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33
            && act.checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            act.requestPermissions(new String[] { android.Manifest.permission.POST_NOTIFICATIONS }, 4711);
        }
    }

    /**
     * Android blocks apps from reopening themselves in the background after an update,
     * so post a notification that opens the app when tapped.
     */
    static void notifyUpdated(Context ctx) {
        try {
            android.app.NotificationManager nm = (android.app.NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
            Channels.ensureAll(ctx);
            String ver = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).versionName;
            Intent open = ctx.getPackageManager().getLaunchIntentForPackage(ctx.getPackageName());
            PendingIntent pi = PendingIntent.getActivity(ctx, 1, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            android.app.Notification.Builder b = Build.VERSION.SDK_INT >= 26
                ? new android.app.Notification.Builder(ctx, "updates")
                : new android.app.Notification.Builder(ctx);
            b.setSmallIcon(R.drawable.ic_stat_update)
                .setContentTitle(L.t("Odysseus atualizado para a versão ") + ver)
                .setContentText(L.t("Toca para abrir."))
                .setContentIntent(pi)
                .setAutoCancel(true);
            nm.notify(4711, b.build());
            android.util.Log.i("OdysseusUpdater", "posted updated notification for " + ver);
        } catch (Exception e) {
            android.util.Log.w("OdysseusUpdater", "notifyUpdated failed", e);
        }
    }
}
