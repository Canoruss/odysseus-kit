package com.canorus.odysseus;

import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.SwitchCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;

/** Native settings of the Android app (not the Odysseus server settings). */
public class SettingsActivity extends AppCompatActivity {
    private static final int BG = Color.parseColor("#282c34"), FG = Color.parseColor("#E5E9F0"),
            MUTED = Color.parseColor("#9AA3B2"), ACCENT = Color.parseColor("#7C9CFF");
    private LinearLayout root, filesBox;
    private SharedPreferences sp;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        sp = AppSettings.sp(this);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(BG);
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int p = dp(18);
        root.setPadding(p, p, p, p);
        sv.addView(root);
        setContentView(sv);

        TextView title = text(L.t("Definições da app"), 22, FG);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        section("Avisos");
        toggle(L.t("Resposta pronta nos chats"), "notify_chat", true, null);
        toggle(L.t("Tarefas agendadas concluídas"), "notify_tasks", true, null);
        toggle(L.t("Lembretes das tarefas com data"), "notify_reminders", true, null);
        toggle(L.t("Ficheiros partilhados novos"), "notify_files", true, null);
        toggle(L.t("Resumo da manhã às 08:00 (tarefas, eventos e consultas do dia)"), "morning_summary", true, null);
        toggle(L.t("Silêncio noturno (18:30–09:30, avisos sem som; alarmes e consultas não são afetados)"), "quiet_hours", true, null);
        toggle(L.t("Modo poupança de bateria (recomendado: usa WorkManager em vez de ligação permanente)"), "battery_saver", true, on -> {
            if (on) SyncService.stopIfRunning(getApplicationContext());
            else SyncService.startIfNeeded(getApplicationContext());
            NoteSync.schedule(getApplicationContext());
        });

        section("Alarmes");
        toggle(L.t("Tarefas com palavra-chave tocam como alarme"), "alarms", true, null);
        root.addView(text(L.t("Palavras que ativam o alarme (separadas por vírgulas):"), 13, MUTED));
        EditText words = new EditText(this);
        words.setTextColor(FG);
        words.setText(AppSettings.alarmWords(this));
        words.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int c, int d) { }
            public void onTextChanged(CharSequence s, int a, int c, int d) { }
            public void afterTextChanged(Editable e) { sp.edit().putString("alarm_words", e.toString()).apply(); }
        });
        root.addView(words);
        choice(L.t("Adiar lembretes e alarmes"), "snooze_minutes", new int[]{5, 10, 15, 30, 60}, 10, "min");

        section(L.t("Calendário"));
        toggle(L.t("Enviar os eventos do telemóvel para o Odysseus (calendários graváveis; só os criados aqui)"), "calendar_push", true, null);
        toggle(L.t("Copiar os eventos do Odysseus para o calendário do telemóvel"), "calendar_sync", true, on -> {
            Bg.run(() -> {
                try {
                    if (on) NoteSync.runSync(getApplicationContext(), true);
                    else CalendarSync.removeCalendar(getApplicationContext());
                } catch (Exception ignored) { }
            });
        });

        section(L.t("Relógio (Health Connect)"));
        toggle(L.t("Enviar batimentos, passos, oxigénio e treinos do relógio para o Gym (precisa do Android 14+ e de uma app de saúde ligada ao Health Connect: Nothing X, Samsung Health, Garmin, Fitbit, Zepp…)"), "health_sync", false, on -> {
            if (!on) { HealthWorker.cancel(getApplicationContext()); return; }
            HealthWorker.schedule(getApplicationContext());
            if (!HealthSync.supported()) {
                android.widget.Toast.makeText(this, L.t("Precisa do Android 14 ou superior."), android.widget.Toast.LENGTH_LONG).show();
                return;
            }
            if (!HealthSync.hasPerm(this) || checkSelfPermission(HealthSync.PERM_SPO2) != android.content.pm.PackageManager.PERMISSION_GRANTED || checkSelfPermission(HealthSync.PERM_BG) != android.content.pm.PackageManager.PERMISSION_GRANTED) requestPermissions(HealthSync.PERMS_ASK, 4713);
            else Bg.run(() -> { boolean ok = HealthSync.sync(getApplicationContext()); String r = HealthSync.result; runOnUiThread(() -> android.widget.Toast.makeText(this, L.t(r.startsWith("Enviado ao Gym: ") ? "Enviado ao Gym: " : r) + (r.startsWith("Enviado ao Gym: ") ? r.substring(16) : ""), android.widget.Toast.LENGTH_LONG).show()); });
        });

        Button hb = new Button(this);
        hb.setText(L.t("Sincronizar relógio agora"));
        hb.setOnClickListener(v -> {
            if (!HealthSync.supported()) { showHealth(L.t("Precisa do Android 14 ou superior.")); return; }
            if (!HealthSync.hasPerm(this)) { requestPermissions(HealthSync.PERMS_ASK, 4713); return; }
            showHealth(L.t("A sincronizar…"));
            Bg.run(() -> {
                String r;
                try { HealthSync.sync(getApplicationContext()); r = HealthSync.result; }
                catch (Throwable t) { r = "Erro: " + t; }
                final String m = r.startsWith("Enviado ao Gym: ") ? L.t("Enviado ao Gym: ") + r.substring(16) : L.t(r);
                runOnUiThread(() -> showHealth(m));
            });
        });
        root.addView(hb);
        healthMsg = text("", 13, FG);
        root.addView(healthMsg);

        section(L.t("Segurança"));
        toggle(L.t("Pedir impressão digital (ou PIN) ao abrir"), "lock", true, null);
        choice(L.t("Voltar a pedir depois de"), "lock_minutes", new int[]{0, 1, 5, 15, 30, 60}, 5, L.t("min em segundo plano"));

        section("Agente Android (SSE /agent/step + Proteções)");
        toggle("Mostrar botão flutuante 🤖 sobre outras apps", "agent_overlay", false, on -> {
            if (on) {
                if (!android.provider.Settings.canDrawOverlays(this)) {
                    startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                            android.net.Uri.parse("package:" + getPackageName())));
                } else {
                    AgentService.showIdleOverlay(this);
                }
            } else {
                AgentService.hideOverlay(this);
            }
        });
        AppSettings.agentConfirmAllSteps(this);
        toggle("Modo Depuração: pedir confirmação em TODOS os passos (mesmo ações rotineiras)", "agent_confirm_all_steps", false, null);
        toggle("Confirmação reforçada em passos assinalados pelo modelo (pagamentos, gestores de passwords, envios e eliminações exigem sempre confirmação)", "agent_confirm_critical", true, null);
        root.addView(text("Visão do agente indisponível: o servidor atual só aceita texto.", 13, MUTED));
        toggle("Enviar definições de ferramentas Android (tools) em /agent/step", "agent_send_tools", true, null);
        choice("Limite máximo de passos por tarefa", "agent_max_steps", new int[]{10, 15, 25, 40, 60}, 25, "passos");

        root.addView(text("Rota SSE do agente no servidor (predefinido: /agent/step):", 13, MUTED));
        EditText epField = new EditText(this);
        epField.setTextColor(FG);
        epField.setSingleLine(true);
        epField.setText(AppSettings.agentEndpoint(this));
        epField.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int c, int d) { }
            public void onTextChanged(CharSequence s, int a, int c, int d) { }
            public void afterTextChanged(Editable e) { sp.edit().putString("agent_endpoint", e.toString().trim()).apply(); }
        });
        root.addView(epField);

        root.addView(text("Cabeçalho HTTP do Token (Authorization envia 'Bearer <token>'; ou ex.: X-Agent-Token):", 13, MUTED));
        EditText hdrField = new EditText(this);
        hdrField.setTextColor(FG);
        hdrField.setSingleLine(true);
        hdrField.setText(AppSettings.agentAuthHeader(this));
        hdrField.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int c, int d) { }
            public void onTextChanged(CharSequence s, int a, int c, int d) { }
            public void afterTextChanged(Editable e) { sp.edit().putString("agent_auth_header", e.toString().trim()).apply(); }
        });
        root.addView(hdrField);

        root.addView(text("Token de autenticação do Agente (oculto no ecrã e nas capturas):", 13, MUTED));
        EditText tokField = new EditText(this);
        tokField.setTextColor(FG);
        tokField.setSingleLine(true);
        tokField.setHint("Cola aqui o token de /agent/step…");
        tokField.setHintTextColor(MUTED);
        tokField.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        tokField.setText(AppSettings.agentToken(this));
        tokField.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int c, int d) { }
            public void onTextChanged(CharSequence s, int a, int c, int d) { }
            public void afterTextChanged(Editable e) { sp.edit().putString("agent_token", e.toString().trim()).apply(); }
        });
        root.addView(tokField);

        root.addView(text("Modelo no servidor (opcional — enviado no campo 'model'):", 13, MUTED));
        EditText mdlField = new EditText(this);
        mdlField.setTextColor(FG);
        mdlField.setSingleLine(true);
        mdlField.setHint("(usar predefinido do servidor)");
        mdlField.setHintTextColor(MUTED);
        mdlField.setText(sp.getString("agent_model", ""));
        mdlField.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int c, int d) { }
            public void onTextChanged(CharSequence s, int a, int c, int d) { }
            public void afterTextChanged(Editable e) { sp.edit().putString("agent_model", e.toString().trim()).apply(); }
        });
        root.addView(mdlField);

        button("Escolher modelo do servidor", v -> {
            Bg.run(() -> {
                try {
                    String base = AppSettings.serverUrl(this);
                    if (base == null || base.isEmpty()) throw new Exception("Inicia sessão no Odysseus primeiro.");
                    String cookie = android.webkit.CookieManager.getInstance().getCookie(base);
                    HttpURLConnection connection = (HttpURLConnection) new URL(base + "/api/models").openConnection();
                    connection.setConnectTimeout(10000);
                    connection.setReadTimeout(15000);
                    if (cookie != null) connection.setRequestProperty("Cookie", cookie);
                    try {
                        if (connection.getResponseCode() != 200) throw new Exception("Inicia sessão e tenta novamente (HTTP " + connection.getResponseCode() + ").");
                        String json;
                        try (java.io.InputStream stream = connection.getInputStream(); java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream()) {
                            byte[] buffer = new byte[4096];
                            int count;
                            while ((count = stream.read(buffer)) != -1) {
                                if (bytes.size() + count > 2_000_000) throw new Exception("Lista de modelos demasiado grande.");
                                bytes.write(buffer, 0, count);
                            }
                            json = new String(bytes.toByteArray(), StandardCharsets.UTF_8);
                        }
                        JSONArray items = new JSONObject(json).getJSONArray("items");
                        ArrayList<String> labels = new ArrayList<>();
                        ArrayList<String> ids = new ArrayList<>();
                        ArrayList<String> models = new ArrayList<>();
                        for (int i = 0; i < items.length(); i++) {
                            JSONObject item = items.optJSONObject(i);
                            if (item == null || !"llm".equals(item.optString("model_type", "llm"))) continue;
                            for (String key : new String[]{"models", "models_extra"}) {
                                JSONArray list = item.optJSONArray(key);
                                if (list == null) continue;
                                JSONArray names = item.optJSONArray(key + "_display");
                                for (int j = 0; j < list.length(); j++) {
                                    String model = list.optString(j, "");
                                    if (model.isEmpty()) continue;
                                    String name = names == null ? model : names.optString(j, model);
                                    labels.add(item.optString("endpoint_name", "Servidor") + " · " + name);
                                    ids.add(item.optString("endpoint_id", ""));
                                    models.add(model);
                                }
                            }
                        }
                        runOnUiThread(() -> {
                            if (labels.isEmpty()) {
                                Toast.makeText(this, "Nenhum modelo disponível.", Toast.LENGTH_LONG).show();
                                return;
                            }
                            new android.app.AlertDialog.Builder(this).setTitle("Escolher modelo do servidor")
                                    .setItems(labels.toArray(new String[0]), (dialog, which) -> {
                                        sp.edit().putString("agent_endpoint", "/api/android-agent/step")
                                                .putString("agent_endpoint_id", ids.get(which))
                                                .putBoolean("agent_server_model", true).apply();
                                        mdlField.setText(models.get(which));
                                        epField.setText("/api/android-agent/step");
                                        Toast.makeText(this, "Modelo selecionado: " + labels.get(which), Toast.LENGTH_LONG).show();
                                    }).setNegativeButton("Cancelar", null).show();
                        });
                    } finally { connection.disconnect(); }
                } catch (Exception e) {
                    runOnUiThread(() -> Toast.makeText(this, "Não foi possível carregar os modelos: " + e.getMessage(), Toast.LENGTH_LONG).show());
                }
            });
        });

        final TextView probeOut = text("", 13, FG);
        button("🔌 Testar ligação e Token em /agent/step", v -> {
            probeOut.setText("A testar /agent/step…");
            Bg.run(() -> {
                final String res = AgentService.probeEndpoint(getApplicationContext());
                runOnUiThread(() -> {
                    probeOut.setText(res);
                    new android.app.AlertDialog.Builder(SettingsActivity.this)
                            .setTitle("Diagnóstico /agent/step")
                            .setMessage(res)
                            .setPositiveButton("OK", null)
                            .show();
                });
            });
        });
        root.addView(probeOut);

        button("Ativar Acessibilidade do Agente", v -> startActivity(new Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        button("🤖 Abrir comando / voz do Agente", v -> startActivity(new Intent(this, AgentPromptActivity.class)));

        section("Ferramentas");
        button(L.t("Tradutor"), v -> startActivity(new Intent(this, TranslateActivity.class)));
        button(L.t("Nova tarefa"), v -> startActivity(new Intent(this, QuickTaskActivity.class)));
        button(L.t("Abrir o Gemini (imagens e perguntas)"), v -> GeminiLauncher.open(this));

        section(L.t("Consultas SNS24 registadas"));
        apptBox = new LinearLayout(this);
        apptBox.setOrientation(LinearLayout.VERTICAL);
        root.addView(apptBox);
        loadAppts();

        section(L.t("Ficheiros partilhados (últimos 7 dias)"));
        filesBox = new LinearLayout(this);
        filesBox.setOrientation(LinearLayout.VERTICAL);
        root.addView(filesBox);
        loadFiles();

        section("Sobre");
        String ver = "?";
        try { ver = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Exception ignored) { }
        root.addView(text(L.t("Versão ") + ver, 14, MUTED));
        Updater up = new Updater(this);
        button(L.t("Procurar atualizações"), v -> up.check(true));
    }

    private LinearLayout apptBox;

    private void loadAppts() {
        apptBox.removeAllViews();
        java.util.List<Long> l = new java.util.ArrayList<>();
        for (String x : getSharedPreferences(SnsListener.PREFS, MODE_PRIVATE).getStringSet(SnsListener.KEY, new java.util.HashSet<>()))
            try { l.add(Long.parseLong(x)); } catch (NumberFormatException ignored) { }
        java.util.Collections.sort(l);
        if (l.isEmpty()) { apptBox.addView(text(L.t("Nenhuma consulta registada."), 13, MUTED)); return; }
        for (long e : l) {
            LinearLayout row = new LinearLayout(this);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.addView(text(SnsListener.label(e, false), 14, FG), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
            Button x = new Button(this);
            x.setText(L.t("Apagar"));
            x.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
                    .setTitle(L.t("Apagar consulta?")).setMessage(SnsListener.label(e, false) + L.t("\nCancela os avisos e não volta a ser registada."))
                    .setPositiveButton(L.t("Apagar"), (dd, w) -> { SnsListener.remove(this, String.valueOf(e)); loadAppts(); })
                    .setNegativeButton(L.t("Cancelar"), null).show());
            row.addView(x);
            apptBox.addView(row);
        }
    }

    private void loadFiles() {
        filesBox.removeAllViews();
        filesBox.addView(text("A carregar…", 13, MUTED));
        Bg.run(() -> {
            String user = FileShare.user(this);
            JSONArray a = null;
            try { if (user != null) a = FileShare.all(this, user); } catch (Exception ignored) { }
            final JSONArray items = a;
            runOnUiThread(() -> {
                filesBox.removeAllViews();
                if (user == null) { filesBox.addView(text(L.t("Inicia sessão no Odysseus para ver os teus ficheiros."), 13, MUTED)); return; }
                if (items == null || items.length() == 0) { filesBox.addView(text(L.t("Nenhum ficheiro partilhado contigo."), 13, MUTED)); return; }
                for (int i = items.length() - 1; i >= 0; i--) {
                    JSONObject o = items.optJSONObject(i);
                    if (o == null) continue;
                    LinearLayout row = new LinearLayout(this);
                    row.setGravity(Gravity.CENTER_VERTICAL);
                    TextView t = text(o.optString("name") + "  ·  " + FileShare.human(o.optLong("size"))
                            + (FileShare.isDone(this, o.optString("id")) ? "  ✓" : ""), 14, FG);
                    row.addView(t, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
                    Button d = new Button(this);
                    d.setText("Descarregar");
                    d.setOnClickListener(v -> FileShare.download(this, user, o));
                    row.addView(d);
                    Button x = new Button(this);
                    x.setText(L.t("Apagar"));
                    x.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
                            .setTitle(L.t("Apagar ficheiro?")).setMessage(o.optString("name") + L.t("\nSai da lista e do servidor."))
                            .setPositiveButton(L.t("Apagar"), (dd, w) -> Bg.run(() -> {
                                String cookie = android.webkit.CookieManager.getInstance().getCookie(NoteSync.SITE);
                                int code;
                                try { code = Actions.send("POST", NoteSync.SITE + "/finance/files/delete", cookie, "application/json",
                                        new JSONObject().put("id", o.optString("id")).toString()); } catch (Exception ex) { code = -1; }
                                final int cd = code;
                                runOnUiThread(() -> {
                                    android.widget.Toast.makeText(this, cd == 200 ? L.t("Ficheiro apagado") : L.t("Não foi possível apagar (") + cd + ")", android.widget.Toast.LENGTH_SHORT).show();
                                    loadFiles();
                                });
                            }))
                            .setNegativeButton(L.t("Cancelar"), null).show());
                    row.addView(x);
                    filesBox.addView(row);
                }
            });
        });
    }

    // ---- tiny UI helpers ----
    interface OnToggle { void changed(boolean on); }

    private void toggle(String label, String key, boolean def, OnToggle cb) {
        SwitchCompat s = new SwitchCompat(this);
        s.setText(label);
        s.setTextColor(FG);
        s.setTextSize(15);
        s.setPadding(0, dp(6), 0, dp(6));
        s.setChecked(sp.getBoolean(key, def));
        s.setOnCheckedChangeListener((v, on) -> {
            sp.edit().putBoolean(key, on).apply();
            if (cb != null) cb.changed(on);
        });
        root.addView(s, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    private void choice(String label, String key, int[] values, int def, String unit) {
        LinearLayout row = new LinearLayout(this);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.addView(text(label, 15, FG), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        String[] names = new String[values.length];
        int sel = 0, cur = sp.getInt(key, def);
        for (int i = 0; i < values.length; i++) {
            names[i] = (values[i] == 0 ? "sempre" : values[i] + " " + unit);
            if (values[i] == cur) sel = i;
        }
        Spinner sp2 = new Spinner(this);
        ArrayAdapter<String> ad = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, names);
        sp2.setAdapter(ad);
        sp2.setSelection(sel);
        sp2.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            public void onItemSelected(AdapterView<?> p, View v, int pos, long id) { sp.edit().putInt(key, values[pos]).apply(); }
            public void onNothingSelected(AdapterView<?> p) { }
        });
        row.addView(sp2);
        root.addView(row);
    }

    private void button(String label, View.OnClickListener l) {
        Button bt = new Button(this);
        bt.setText(label);
        bt.setAllCaps(false);
        bt.setOnClickListener(l);
        root.addView(bt, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    }

    private void section(String s) {
        TextView t = text(s, 13, ACCENT);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding(0, dp(20), 0, dp(4));
        root.addView(t);
    }

    private TextView text(String s, int sp, int color) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        return t;
    }

    private android.widget.TextView healthMsg;
    private void showHealth(String m) {
        if (healthMsg != null) healthMsg.setText(m);
        new android.app.AlertDialog.Builder(this).setMessage(m).setPositiveButton("OK", null).show();
    }

    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density); }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
        super.onRequestPermissionsResult(code, perms, res);
        if (code == 4713) {
            Bg.run(() -> { boolean ok = HealthSync.sync(getApplicationContext()); String r = HealthSync.result; runOnUiThread(() -> android.widget.Toast.makeText(this, L.t(r.startsWith("Enviado ao Gym: ") ? "Enviado ao Gym: " : r) + (r.startsWith("Enviado ao Gym: ") ? r.substring(16) : ""), android.widget.Toast.LENGTH_LONG).show()); });
            if (!HealthSync.hasPerm(this)) android.widget.Toast.makeText(this, L.t("Sem permissões do Health Connect: nada é enviado."), android.widget.Toast.LENGTH_LONG).show();
        }
    }
}
