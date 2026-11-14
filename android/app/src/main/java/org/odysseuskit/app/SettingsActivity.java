package org.odysseuskit.app;

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

        TextView title = text(Tr.t("Definições da app"), 22, FG);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        section("Language / Idioma");
        button("English" + ("en".equals(Tr.lang()) ? "  ✓" : ""), v -> switchLanguage("en"));
        button("Português" + ("pt".equals(Tr.lang()) ? "  ✓" : ""), v -> switchLanguage("pt"));

        section("Avisos");
        toggle("Resposta pronta nos chats", "notify_chat", true, null);
        toggle(Tr.t("Tarefas agendadas concluídas"), "notify_tasks", true, null);
        toggle(Tr.t("Lembretes das tarefas com data"), "notify_reminders", true, null);
        toggle("Ficheiros partilhados novos", "notify_files", true, null);
        toggle(Tr.t("Resumo da manhã às 08:00 (tarefas, eventos e consultas do dia)"), "morning_summary", true, null);
        toggle(Tr.t("Silêncio noturno (18:30–09:30, avisos sem som; alarmes e consultas não são afetados)"), "quiet_hours", true, null);

        section("Alarmes");
        toggle(Tr.t("Tarefas com palavra-chave tocam como alarme"), "alarms", true, null);
        root.addView(text(Tr.t("Palavras que ativam o alarme (separadas por vírgulas):"), 13, MUTED));
        EditText words = new EditText(this);
        words.setTextColor(FG);
        words.setText(AppSettings.alarmWords(this));
        words.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int c, int d) { }
            public void onTextChanged(CharSequence s, int a, int c, int d) { }
            public void afterTextChanged(Editable e) { sp.edit().putString("alarm_words", e.toString()).apply(); }
        });
        root.addView(words);
        choice("Adiar lembretes e alarmes", "snooze_minutes", new int[]{5, 10, 15, 30, 60}, 10, "min");

        section(Tr.t("Calendário"));
        toggle(Tr.t("Enviar os eventos do telemóvel para o Odysseus (calendários graváveis; só os criados aqui)"), "calendar_push", true, null);
        toggle(Tr.t("Copiar os eventos do Odysseus para o calendário do telemóvel"), "calendar_sync", true, on -> {
            new Thread(() -> {
                try {
                    if (on) NoteSync.runSync(getApplicationContext());
                    else CalendarSync.removeCalendar(getApplicationContext());
                } catch (Exception ignored) { }
            }).start();
        });

        section(Tr.t("Segurança"));
        toggle(Tr.t("Pedir impressão digital (ou PIN) ao abrir"), "lock", true, null);
        choice("Voltar a pedir depois de", "lock_minutes", new int[]{0, 1, 5, 15, 30, 60}, 5, "min em segundo plano");

        section("Ferramentas");
        button("Tradutor", v -> startActivity(new Intent(this, TranslateActivity.class)));
        button("Nova tarefa", v -> startActivity(new Intent(this, QuickTaskActivity.class)));
        button(Tr.t("Abrir o Gemini (imagens e perguntas)"), v -> GeminiLauncher.open(this));

        section("Consultas SNS24 registadas");
        apptBox = new LinearLayout(this);
        apptBox.setOrientation(LinearLayout.VERTICAL);
        root.addView(apptBox);
        loadAppts();

        section(Tr.t("Ficheiros partilhados (últimos 7 dias)"));
        filesBox = new LinearLayout(this);
        filesBox.setOrientation(LinearLayout.VERTICAL);
        root.addView(filesBox);
        loadFiles();

        section("Sobre");
        String ver = "?";
        try { ver = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Exception ignored) { }
        root.addView(text(Tr.t("Versão ") + ver, 14, MUTED));
        Updater up = new Updater(this);
        button(Tr.t("Procurar atualizações"), v -> up.check(true));
    }

    private LinearLayout apptBox;

    private void loadAppts() {
        apptBox.removeAllViews();
        java.util.List<Long> l = new java.util.ArrayList<>();
        for (String x : getSharedPreferences(SnsListener.PREFS, MODE_PRIVATE).getStringSet(SnsListener.KEY, new java.util.HashSet<>()))
            try { l.add(Long.parseLong(x)); } catch (NumberFormatException ignored) { }
        java.util.Collections.sort(l);
        if (l.isEmpty()) { apptBox.addView(text("Nenhuma consulta registada.", 13, MUTED)); return; }
        for (long e : l) {
            LinearLayout row = new LinearLayout(this);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.addView(text(SnsListener.label(e, false), 14, FG), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
            Button x = new Button(this);
            x.setText(Tr.t("Apagar"));
            x.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
                    .setTitle(Tr.t("Apagar consulta?")).setMessage(SnsListener.label(e, false) + Tr.t("\nCancela os avisos e não volta a ser registada."))
                    .setPositiveButton(Tr.t("Apagar"), (dd, w) -> { SnsListener.remove(this, String.valueOf(e)); loadAppts(); })
                    .setNegativeButton("Cancelar", null).show());
            row.addView(x);
            apptBox.addView(row);
        }
    }

    private void loadFiles() {
        filesBox.removeAllViews();
        filesBox.addView(text("A carregar…", 13, MUTED));
        new Thread(() -> {
            String user = FileShare.user(this);
            JSONArray a = null;
            try { if (user != null) a = FileShare.all(this, user); } catch (Exception ignored) { }
            final JSONArray items = a;
            runOnUiThread(() -> {
                filesBox.removeAllViews();
                if (user == null) { filesBox.addView(text(Tr.t("Inicia sessão no Odysseus para ver os teus ficheiros."), 13, MUTED)); return; }
                if (items == null || items.length() == 0) { filesBox.addView(text("Nenhum ficheiro partilhado contigo.", 13, MUTED)); return; }
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
                    x.setText(Tr.t("Apagar"));
                    x.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
                            .setTitle(Tr.t("Apagar ficheiro?")).setMessage(o.optString("name") + "\nSai da lista e do servidor.")
                            .setPositiveButton(Tr.t("Apagar"), (dd, w) -> new Thread(() -> {
                                String cookie = android.webkit.CookieManager.getInstance().getCookie(NoteSync.SITE);
                                int code;
                                try { code = Actions.send("POST", NoteSync.SITE + "/finance/files/delete", cookie, "application/json",
                                        new JSONObject().put("id", o.optString("id")).toString()); } catch (Exception ex) { code = -1; }
                                final int cd = code;
                                runOnUiThread(() -> {
                                    android.widget.Toast.makeText(this, cd == 200 ? "Ficheiro apagado" : Tr.t("Não foi possível apagar (") + cd + ")", android.widget.Toast.LENGTH_SHORT).show();
                                    loadFiles();
                                });
                            }).start())
                            .setNegativeButton("Cancelar", null).show());
                    row.addView(x);
                    filesBox.addView(row);
                }
            });
        }).start();
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

    /** Muda o idioma da app e das paginas do Odysseus (cookie lido pelas ferramentas). */
    private void switchLanguage(String l) {
        Tr.setLang(this, l);
        try {
            android.webkit.CookieManager cm = android.webkit.CookieManager.getInstance();
            cm.setCookie(NoteSync.SITE, "kitlang=" + l + "; Path=/; Max-Age=31536000; SameSite=Lax");
            cm.flush();
        } catch (Exception ignored) { }
        recreate();
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

    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density); }
}
