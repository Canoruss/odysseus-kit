package org.odysseuskit.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.media.MediaRecorder;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** Ditado sem depender da Google: grava no telemóvel e transcreve no servidor (/translate/stt). */
final class Voice {
    private Voice() { }

    interface Result { void done(String text); }   // texto vazio = nada reconhecido / cancelado

    static void listen(Activity a, String lang, Result cb) {
        if (a.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            a.requestPermissions(new String[] { android.Manifest.permission.RECORD_AUDIO }, 78);
            Toast.makeText(a, Tr.t("Dá permissão ao microfone e carrega outra vez em Ditar"), Toast.LENGTH_LONG).show();
            cb.done("");
            return;
        }
        final MediaRecorder rec = new MediaRecorder();
        final File f;
        try {
            f = File.createTempFile("ditado", ".m4a", a.getCacheDir());
            rec.setAudioSource(MediaRecorder.AudioSource.MIC);
            rec.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            rec.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            rec.setAudioSamplingRate(16000);
            rec.setAudioEncodingBitRate(48000);
            rec.setMaxDuration(60000);
            rec.setOutputFile(f.getAbsolutePath());
            rec.prepare();
            rec.start();
        } catch (Exception e) {
            try { rec.release(); } catch (Exception ignored) { }
            Toast.makeText(a, Tr.t("Não consegui usar o microfone"), Toast.LENGTH_LONG).show();
            cb.done("");
            return;
        }
        final boolean ry = "ryoku".equals(AppSettings.sp(a).getString("ui_theme", ""));
        final int bg = ry ? 0xFF0a0a0a : 0xFF282c34, fg = ry ? 0xFFcdc4ba : 0xFFE5E9F0, ac = ry ? 0xFFce5e32 : 0xFF5b8abf;
        android.widget.LinearLayout box = new android.widget.LinearLayout(a);
        box.setOrientation(android.widget.LinearLayout.VERTICAL);
        int pd = (int) (20 * a.getResources().getDisplayMetrics().density);
        box.setPadding(pd, pd, pd, pd / 2);
        android.widget.TextView tt = new android.widget.TextView(a);
        tt.setText(Tr.t("🎤 A ouvir…")); tt.setTextSize(20); tt.setTextColor(ry ? ac : fg); tt.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        android.widget.TextView mm = new android.widget.TextView(a);
        mm.setText(Tr.t("Fala agora e carrega em Parar.")); mm.setTextSize(16); mm.setTextColor(fg); mm.setPadding(0, pd / 2, 0, 0);
        box.addView(tt); box.addView(mm);
        AlertDialog dlg = new AlertDialog.Builder(a)
                .setView(box)
                .setCancelable(false)
                .setPositiveButton(Tr.t("Parar"), (d, w) -> finish(a, rec, f, lang, true, cb))
                .setNegativeButton(Tr.t("Cancelar"), (d, w) -> finish(a, rec, f, lang, false, cb))
                .create();
        dlg.show();
        if (dlg.getWindow() != null) dlg.getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(bg));
        dlg.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(ac);
        dlg.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(fg);
    }

    private static void finish(Activity a, MediaRecorder rec, File f, String lang, boolean send, Result cb) {
        try { rec.stop(); } catch (Exception e) { send = false; }
        try { rec.release(); } catch (Exception ignored) { }
        if (!send) { f.delete(); cb.done(""); return; }
        Toast.makeText(a, Tr.t("A transcrever…"), Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            String txt = null;
            try {
                ByteArrayOutputStream bo = new ByteArrayOutputStream();
                try (InputStream in = new FileInputStream(f)) {
                    byte[] buf = new byte[8192]; int n;
                    while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
                }
                JSONObject body = new JSONObject()
                        .put("audio", android.util.Base64.encodeToString(bo.toByteArray(), android.util.Base64.NO_WRAP))
                        .put("mime", "audio/mp4").put("lang", lang == null ? "" : lang);
                HttpURLConnection c = (HttpURLConnection) new URL(AppSettings.sp(a).getString("tr_base", NoteSync.SITE) + "/translate/stt").openConnection();
                c.setConnectTimeout(8000);
                c.setReadTimeout(60000);
                c.setRequestMethod("POST");
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                try (OutputStream os = c.getOutputStream()) { os.write(body.toString().getBytes("UTF-8")); }
                int code = c.getResponseCode();
                InputStream is = code < 400 ? c.getInputStream() : c.getErrorStream();
                ByteArrayOutputStream ro = new ByteArrayOutputStream();
                byte[] buf = new byte[4096]; int n;
                while (is != null && (n = is.read(buf)) > 0) ro.write(buf, 0, n);
                if (code < 400) txt = new JSONObject(ro.toString("UTF-8")).optString("text", "").trim();
            } catch (Exception ignored) { }
            f.delete();
            final String ft = txt;
            a.runOnUiThread(() -> {
                if (a.isFinishing()) return;
                if (ft == null) Toast.makeText(a, Tr.t("Sem ligação ao servidor. Tens o Tailscale ligado?"), Toast.LENGTH_LONG).show();
                else if (ft.isEmpty()) Toast.makeText(a, Tr.t("Não percebi nada"), Toast.LENGTH_SHORT).show();
                cb.done(ft == null ? "" : ft);
            });
        }).start();
    }
}
