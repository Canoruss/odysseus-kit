package com.canorus.odysseus;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** Assistente flutuante privado que substitui o Google Gemini em todo o telemóvel. */
public class GeminiLauncher extends Activity {
    private static final int REQ_PERMS = 91;
    private final JSONArray history = new JSONArray();
    private TextView statusView;
    private AlertDialog panel;

    static void open(Context c) {
        Intent i = new Intent(c, GeminiLauncher.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        c.startActivity(i);
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (!hasCorePermissions()) {
            requestPermissions(new String[] {
                    Manifest.permission.RECORD_AUDIO,
                    Manifest.permission.READ_CONTACTS,
                    Manifest.permission.CALL_PHONE,
                    Manifest.permission.SEND_SMS
            }, REQ_PERMS);
            return;
        }
        startTurn();
    }

    private boolean hasCorePermissions() {
        return checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                && checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED
                && checkSelfPermission(Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
        super.onRequestPermissionsResult(code, perms, res);
        startTurn();
    }

    private void startTurn() {
        Voice.listen(this, "pt", true, text -> {
            if (text == null || text.trim().isEmpty()) {
                finish();
                return;
            }
            showProgressPanel("Tu: \"" + text + "\"\n\nA pensar…");
            try {
                history.put(new JSONObject().put("role", "user").put("content", text));
            } catch (Exception ignored) { }
            runAgentLoop(0);
        });
    }

    private void runAgentLoop(int depth) {
        if (depth > 4) { finish(); return; }
        new Thread(() -> {
            try {
                JSONObject payload = new JSONObject()
                        .put("messages", history)
                        .put("now_ms", System.currentTimeMillis());

                HttpURLConnection c = (HttpURLConnection) new URL(NoteSync.SITE + "/api/agent").openConnection();
                c.setRequestMethod("POST");
                c.setConnectTimeout(10000);
                c.setReadTimeout(120000);
                c.setInstanceFollowRedirects(false);
                String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
                if (cookie != null) c.setRequestProperty("Cookie", cookie);
                c.setRequestProperty("Content-Type", "application/json");
                c.setDoOutput(true);
                try (OutputStream os = c.getOutputStream()) { os.write(payload.toString().getBytes("UTF-8")); }

                int code = c.getResponseCode();
                if (code == 401 || code == 403 || (code >= 300 && code < 400)) {
                    throw new SecurityException();
                }
                if (code != 200) throw new IllegalStateException();
                InputStream is = c.getInputStream();
                ByteArrayOutputStream bo = new ByteArrayOutputStream();
                byte[] buf = new byte[4096]; int n;
                while (is != null && (n = is.read(buf)) > 0) bo.write(buf, 0, n);

                JSONObject resp = new JSONObject(bo.toString("UTF-8"));
                JSONArray toolCalls = resp.optJSONArray("tool_calls");

                // Se o modelo pediu para executar uma ação no telemóvel (ex: ligar, alarme, SMS)
                if (toolCalls != null && toolCalls.length() > 0) {
                    history.put(new JSONObject().put("role", "assistant").put("tool_calls", toolCalls));
                    for (int i = 0; i < toolCalls.length(); i++) {
                        JSONObject tc = toolCalls.getJSONObject(i);
                        String name = tc.getString("name");
                        JSONObject args = tc.optJSONObject("arguments");
                        if (args == null) args = new JSONObject();
                        JSONObject toolResult = PhoneAgent.execute(GeminiLauncher.this, name, args);
                        history.put(new JSONObject()
                                .put("role", "tool")
                                .put("name", name)
                                .put("content", toolResult.toString()));
                    }
                    // Devolve o resultado da ação ao servidor para o modelo confirmar ou desambiguar
                    runAgentLoop(depth + 1);
                    return;
                }

                final String reply = resp.optString("reply", "");
                final String audioB64 = resp.optString("audio_base64", "");
                final boolean followUp = resp.optBoolean("expect_follow_up", false);
                history.put(new JSONObject().put("role", "assistant").put("content", reply));

                runOnUiThread(() -> {
                    if (isFinishing()) return;
                    showProgressPanel(reply);
                    Voice.speak(GeminiLauncher.this, reply, audioB64, () -> {
                        if (followUp && !isFinishing()) {
                            if (panel != null) panel.dismiss();
                            startTurn(); // Ex: "Qual dos dois Joões queres ligar?" -> volta a ouvir!
                        } else {
                            finish();
                        }
                    });
                });
            } catch (Exception e) {
                String message = e instanceof SecurityException
                        ? "Sessão expirada. Inicia sessão no Odysseus e tenta novamente."
                        : e instanceof java.io.IOException
                        ? "Não consigo aceder ao servidor. Verifica a ligação e o Tailscale."
                        : "O servidor não conseguiu responder. Tenta novamente.";
                runOnUiThread(() -> {
                    android.widget.Toast.makeText(this, L.t(message), android.widget.Toast.LENGTH_LONG).show();
                    finish();
                });
            }
        }).start();
    }

    private void showProgressPanel(String msg) {
        if (panel != null && panel.isShowing() && statusView != null) {
            statusView.setText(msg);
            return;
        }
        boolean ry = "ryoku".equals(AppSettings.sp(this).getString("ui_theme", ""));
        int bg = ry ? 0xFF0a0a0a : 0xFF282c34, fg = ry ? 0xFFcdc4ba : 0xFFE5E9F0;
        int pd = (int) (22 * getResources().getDisplayMetrics().density);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(pd, pd, pd, pd);
        statusView = new TextView(this);
        statusView.setText(msg);
        statusView.setTextSize(17);
        statusView.setTextColor(fg);
        box.addView(statusView);
        panel = new AlertDialog.Builder(this)
                .setView(box)
                .setOnCancelListener(d -> finish())
                .create();
        panel.show();
        if (panel.getWindow() != null) {
            panel.getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(bg));
        }
    }

    @Override
    protected void onDestroy() {
        if (panel != null && panel.isShowing()) panel.dismiss();
        super.onDestroy();
    }
}
