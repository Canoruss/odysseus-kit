package com.canorus.odysseus;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.media.MediaPlayer;
import android.media.MediaRecorder;
import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;

/** Grava com deteção automática de silêncio, transcreve no servidor (/translate/stt) e reproduz TTS privado. */
final class Voice {
    private Voice() { }

    static { System.loadLibrary("odysseus_voice"); }
    private static native int nativeVoiceState(int amplitude, boolean spoke, long silenceSince,
                                                long now, long started);

    private static native String nativeTranscriptionBody(byte[] audio, String language);

    interface Result { void done(String text); }

    static void listen(Activity a, String lang, Result cb) {
        listen(a, lang, true, cb);
    }

    static void listen(Activity a, String lang, boolean autoStopOnSilence, Result cb) {
        if (a.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            a.requestPermissions(new String[] { android.Manifest.permission.RECORD_AUDIO }, 78);
            Toast.makeText(a, L.t("Dá permissão ao microfone e tenta outra vez"), Toast.LENGTH_LONG).show();
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
            Toast.makeText(a, L.t("Não consegui usar o microfone"), Toast.LENGTH_LONG).show();
            cb.done("");
            return;
        }

        final boolean[] finished = { false };
        final Handler vadHandler = new Handler(Looper.getMainLooper());

        final boolean ry = "ryoku".equals(AppSettings.sp(a).getString("ui_theme", ""));
        final int bg = ry ? 0xFF0a0a0a : 0xFF282c34, fg = ry ? 0xFFcdc4ba : 0xFFE5E9F0, ac = ry ? 0xFFce5e32 : 0xFF5b8abf;
        android.widget.LinearLayout box = new android.widget.LinearLayout(a);
        box.setOrientation(android.widget.LinearLayout.VERTICAL);
        int pd = (int) (20 * a.getResources().getDisplayMetrics().density);
        box.setPadding(pd, pd, pd, pd / 2);
        android.widget.TextView tt = new android.widget.TextView(a);
        tt.setText(L.t("🎤 A ouvir…")); tt.setTextSize(20); tt.setTextColor(ry ? ac : fg); tt.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        android.widget.TextView mm = new android.widget.TextView(a);
        mm.setText(L.t(autoStopOnSilence ? "Fala naturalmente (envia ao fazer pausa)." : "Fala agora e carrega em Parar."));
        mm.setTextSize(16); mm.setTextColor(fg); mm.setPadding(0, pd / 2, 0, 0);
        box.addView(tt); box.addView(mm);
        android.widget.ProgressBar level = new android.widget.ProgressBar(a, null, android.R.attr.progressBarStyleHorizontal);
        level.setMax(100);
        level.setContentDescription(L.t("Nível do microfone"));
        box.addView(level);

        final AlertDialog dlg = new AlertDialog.Builder(a)
                .setView(box)
                .setCancelable(false)
                .setPositiveButton(L.t("Enviar"), (d, w) -> {
                    if (!finished[0]) { finished[0] = true; vadHandler.removeCallbacksAndMessages(null); finish(a, rec, f, lang, true, cb); }
                })
                .setNegativeButton(L.t("Cancelar"), (d, w) -> {
                    if (!finished[0]) { finished[0] = true; vadHandler.removeCallbacksAndMessages(null); finish(a, rec, f, lang, false, cb); }
                })
                .create();
        dlg.show();
        if (dlg.getWindow() != null) dlg.getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(bg));
        dlg.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(ac);
        dlg.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(fg);

        {
            final boolean[] spoke = { false };
            final long[] silenceSince = { 0L };
            final long startedAt = System.currentTimeMillis();
            vadHandler.postDelayed(new Runnable() {
                @Override public void run() {
                    if (finished[0] || a.isFinishing()) return;
                    int amp = 0;
                    try { amp = rec.getMaxAmplitude(); } catch (Exception ignored) { }
                    level.setProgress(Math.min(100, amp * 100 / 12000));
                    long now = System.currentTimeMillis();
                    int state = autoStopOnSilence
                            ? nativeVoiceState(amp, spoke[0], silenceSince[0], now, startedAt) : 0;
                    if (state == 1) {
                        spoke[0] = true;
                        silenceSince[0] = 0L;
                    } else if (state == 2) {
                        silenceSince[0] = now;
                    } else if (state == 3) {
                        finished[0] = true;
                        dlg.dismiss();
                        finish(a, rec, f, lang, true, cb);
                        return;
                    } else if (state == 4) {
                        finished[0] = true;
                        dlg.dismiss();
                        Toast.makeText(a, L.t("Não detetei voz. Verifica o microfone e tenta novamente."), Toast.LENGTH_LONG).show();
                        finish(a, rec, f, lang, false, cb);
                        return;
                    }
                    vadHandler.postDelayed(this, 150);
                }
            }, 250);
        }
    }

    private static void finish(Activity a, MediaRecorder rec, File f, String lang, boolean send, Result cb) {
        try { rec.stop(); } catch (Exception e) { send = false; }
        try { rec.release(); } catch (Exception ignored) { }
        if (!send) { f.delete(); cb.done(""); return; }
        new Thread(() -> {
            String txt = null;
            String error = null;
            try {
                ByteArrayOutputStream bo = new ByteArrayOutputStream();
                try (InputStream in = new FileInputStream(f)) {
                    byte[] buf = new byte[8192]; int n;
                    while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
                }
                String body = nativeTranscriptionBody(bo.toByteArray(), lang == null ? "" : lang);
                boolean assistant = a instanceof GeminiLauncher;
                String base = assistant ? NoteSync.SITE : AppSettings.sp(a).getString("tr_base", NoteSync.SITE);
                HttpURLConnection c = (HttpURLConnection) new URL(base + (assistant ? "/api/agent/stt" : "/translate/stt")).openConnection();
                c.setConnectTimeout(8000);
                c.setInstanceFollowRedirects(false);
                c.setReadTimeout(100000);
                c.setRequestMethod("POST");
                c.setDoOutput(true);
                String cookie = android.webkit.CookieManager.getInstance().getCookie(base);
                if (cookie != null) c.setRequestProperty("Cookie", cookie);
                c.setRequestProperty("Content-Type", "application/json");
                try (OutputStream os = c.getOutputStream()) { os.write(body.getBytes("UTF-8")); }
                int code = c.getResponseCode();
                InputStream is = code < 400 ? c.getInputStream() : c.getErrorStream();
                ByteArrayOutputStream ro = new ByteArrayOutputStream();
                byte[] buf = new byte[4096]; int n;
                while (is != null && (n = is.read(buf)) > 0) ro.write(buf, 0, n);
                if (code == 401 || code == 403 || (code >= 300 && code < 400)) {
                    error = "Sessão expirada. Inicia sessão no Odysseus e tenta novamente.";
                } else if (code >= 200 && code < 300) {
                    txt = new JSONObject(ro.toString("UTF-8")).optString("text", "").trim();
                    if (txt.isEmpty()) error = "Não detetei voz. Verifica o microfone e tenta novamente.";
                } else {
                    error = "O servidor não conseguiu transcrever o áudio. Tenta novamente.";
                }
            } catch (java.io.IOException e) {
                error = "Não consigo aceder ao servidor. Verifica a ligação e o Tailscale.";
            } catch (Exception e) {
                error = "Não consegui processar a transcrição. Tenta novamente.";
            }
            f.delete();
            final String ft = txt;
            final String message = error;
            a.runOnUiThread(() -> {
                if (a.isFinishing()) return;
                if (message != null) Toast.makeText(a, L.t(message), Toast.LENGTH_LONG).show();
                cb.done(ft == null ? "" : ft);
            });
        }).start();
    }

    /** Reproduz áudio Base64 vindo do TTS privado do servidor (ou usa TTS offline do dispositivo se vazio). */
    static void speak(Context ctx, String replyText, String audioBase64, Runnable onDone) {
        if (audioBase64 != null && !audioBase64.isEmpty()) {
            try {
                File tmp = File.createTempFile("tts", ".wav", ctx.getCacheDir());
                byte[] bytes = android.util.Base64.decode(audioBase64, android.util.Base64.DEFAULT);
                try (FileOutputStream fos = new FileOutputStream(tmp)) { fos.write(bytes); }
                MediaPlayer mp = new MediaPlayer();
                mp.setDataSource(tmp.getAbsolutePath());
                mp.setOnCompletionListener(p -> { p.release(); tmp.delete(); if (onDone != null) onDone.run(); });
                mp.setOnErrorListener((p, w, ex) -> { p.release(); tmp.delete(); if (onDone != null) onDone.run(); return true; });
                mp.prepare();
                mp.start();
                return;
            } catch (Exception ignored) { }
        }
        if (replyText == null || replyText.isEmpty()) {
            if (onDone != null) onDone.run();
            return;
        }
        final TextToSpeech[] holder = new TextToSpeech[1];
        holder[0] = new TextToSpeech(ctx.getApplicationContext(), status -> {
            if (status == TextToSpeech.SUCCESS) {
                holder[0].setLanguage(new Locale("pt", "PT"));
                holder[0].setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override public void onStart(String id) { }
                    @Override public void onDone(String id) { holder[0].shutdown(); if (onDone != null) new Handler(Looper.getMainLooper()).post(onDone); }
                    @Override public void onError(String id) { holder[0].shutdown(); if (onDone != null) new Handler(Looper.getMainLooper()).post(onDone); }
                });
                holder[0].speak(replyText, TextToSpeech.QUEUE_FLUSH, null, "odysseus_reply");
            } else if (onDone != null) {
                onDone.run();
            }
        });
    }
}
