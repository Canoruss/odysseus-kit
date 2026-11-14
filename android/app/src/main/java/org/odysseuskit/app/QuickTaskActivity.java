package org.odysseuskit.app;

import android.app.DatePickerDialog;
import android.app.TimePickerDialog;
import android.content.Intent;
import android.speech.RecognizerIntent;
import java.util.ArrayList;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

import java.util.Calendar;
import java.util.Locale;

/** Small "Nova tarefa" window (launcher shortcut and widget "+"): title + optional date/time. */
public class QuickTaskActivity extends AppCompatActivity {
    private final Calendar when = Calendar.getInstance();
    private boolean hasDate = false;
    private Button dateBtn, timeBtn, micBtn;
    private EditText title;
    private boolean voiceMode = false;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setTitle("Nova tarefa");
        int pad = dp(20);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(pad, pad, pad, pad);

        title = new EditText(this);
        title.setHint(Tr.t("O que tens de fazer? (escreve \"alarme\" para tocar como alarme)"));
        title.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        box.addView(title, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout row = new LinearLayout(this);
        row.setGravity(Gravity.CENTER_VERTICAL);
        dateBtn = new Button(this);
        timeBtn = new Button(this);
        dateBtn.setText(Tr.t("Sem data"));
        timeBtn.setText(Tr.t("Hora"));
        timeBtn.setEnabled(false);
        micBtn = new Button(this);
        micBtn.setText("🎤 Ditar");
        micBtn.setOnClickListener(v -> startVoice());
        row.addView(dateBtn);
        row.addView(timeBtn);
        row.addView(micBtn);
        box.addView(row);

        dateBtn.setOnClickListener(v -> new DatePickerDialog(this, (dp, y, m, d) -> {
            when.set(y, m, d);
            if (!hasDate) { when.set(Calendar.HOUR_OF_DAY, 9); when.set(Calendar.MINUTE, 0); }
            hasDate = true;
            timeBtn.setEnabled(true);
            refresh();
        }, when.get(Calendar.YEAR), when.get(Calendar.MONTH), when.get(Calendar.DAY_OF_MONTH)).show());
        timeBtn.setOnClickListener(v -> new TimePickerDialog(this, (tp, hh, mm) -> {
            when.set(Calendar.HOUR_OF_DAY, hh);
            when.set(Calendar.MINUTE, mm);
            refresh();
        }, when.get(Calendar.HOUR_OF_DAY), when.get(Calendar.MINUTE), true).show());

        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.END);
        Button cancel = new Button(this);
        cancel.setText("Cancelar");
        cancel.setOnClickListener(v -> finish());
        Button save = new Button(this);
        save.setText(Tr.t("Guardar"));
        save.setOnClickListener(v -> save(title.getText().toString().trim(), save));
        actions.addView(cancel);
        actions.addView(save);
        box.addView(actions);

        setContentView(box);
        voiceMode = getIntent().getBooleanExtra("voice", false);
        String preset = getIntent().getStringExtra("spoken");   // texto já falado (testes / atalhos)
        if (preset != null && !preset.isEmpty()) applySpoken(preset);
        else if (voiceMode) startVoice(); else title.requestFocus();
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE);
    }

    private void startVoice() {
        try {
            Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-PT")
                    .putExtra(RecognizerIntent.EXTRA_PROMPT, Tr.t("Diz a tarefa (ex.: \"ligar ao Pedro amanhã às 10\")"));
            startActivityForResult(i, 77);
        } catch (Exception e) {
            Toast.makeText(this, Tr.t("Ditado indisponível neste telemóvel"), Toast.LENGTH_LONG).show();
            voiceMode = false;
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != 77) return;
        ArrayList<String> r = res == RESULT_OK && data != null ? data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS) : null;
        if (r == null || r.isEmpty() || r.get(0).trim().isEmpty()) { if (voiceMode) finish(); return; }
        applySpoken(r.get(0).trim());
        if (voiceMode) {
            String when1 = hasDate ? " — " + dateBtn.getText() + " " + timeBtn.getText() : "";
            Toast.makeText(this, "Tarefa: " + title.getText() + when1, Toast.LENGTH_LONG).show();
            save(title.getText().toString().trim(), micBtn);
        }
    }

    /** Interpreta Tr.t("amanhã"), "hoje", Tr.t("depois de amanhã"), "às 9", "às 18h30", "daqui a 20 minutos / 2 horas". */
    private void applySpoken(String spoken) {
        String t = spoken;
        Calendar c = Calendar.getInstance();
        boolean date = false, time = false;
        Matcher m = Pattern.compile("(?i)daqui a (\\d+) (minutos?|horas?)").matcher(t);
        if (m.find()) {
            int n = Integer.parseInt(m.group(1));
            c.add(m.group(2).toLowerCase(Locale.ROOT).startsWith("min") ? Calendar.MINUTE : Calendar.HOUR_OF_DAY, n);
            t = t.replace(m.group(), ""); date = true; time = true;
        } else {
            m = Pattern.compile(Tr.t("(?i)depois de amanh[ãa]")).matcher(t);
            if (m.find()) { c.add(Calendar.DAY_OF_MONTH, 2); t = t.replace(m.group(), ""); date = true; }
            else {
                m = Pattern.compile(Tr.t("(?i)amanh[ãa]")).matcher(t);
                if (m.find()) { c.add(Calendar.DAY_OF_MONTH, 1); t = t.replace(m.group(), ""); date = true; }
                else { m = Pattern.compile("(?i)\\bhoje\\b").matcher(t); if (m.find()) { t = t.replace(m.group(), ""); date = true; } }
            }
            m = Pattern.compile("(?i)\\b[àa]s (\\d{1,2})(?:[:h](\\d{2}))?(?: ?horas?)?(?: da (manhã|tarde|noite))?").matcher(t);
            if (m.find()) {
                int h = Integer.parseInt(m.group(1)), mi = m.group(2) == null ? 0 : Integer.parseInt(m.group(2));
                String part = m.group(3);
                if (part != null && !part.equals("manhã") && h < 12) h += 12;
                if (h < 24 && mi < 60) {
                    c.set(Calendar.HOUR_OF_DAY, h); c.set(Calendar.MINUTE, mi); c.set(Calendar.SECOND, 0);
                    t = t.replace(m.group(), ""); time = true;
                    if (!date && c.getTimeInMillis() < System.currentTimeMillis()) c.add(Calendar.DAY_OF_MONTH, 1);
                    date = true;
                }
            }
            if (date && !time) { c.set(Calendar.HOUR_OF_DAY, 9); c.set(Calendar.MINUTE, 0); c.set(Calendar.SECOND, 0); }
        }
        t = t.replaceAll("\\s+", " ").replaceAll("^[\\s,.-]+|[\\s,.-]+$", "");
        if (t.isEmpty()) t = spoken;
        t = t.substring(0, 1).toUpperCase(Locale.ROOT) + t.substring(1);
        title.setText(t);
        if (date) {
            when.setTimeInMillis(c.getTimeInMillis());
            hasDate = true; timeBtn.setEnabled(true); refresh();
        }
    }

    private void refresh() {
        dateBtn.setText(String.format(Locale.ROOT, "%02d/%02d/%d", when.get(Calendar.DAY_OF_MONTH), when.get(Calendar.MONTH) + 1, when.get(Calendar.YEAR)));
        timeBtn.setText(String.format(Locale.ROOT, "%02d:%02d", when.get(Calendar.HOUR_OF_DAY), when.get(Calendar.MINUTE)));
    }

    private void save(String title, Button btn) {
        if (title.isEmpty()) { Toast.makeText(this, Tr.t("Escreve o título da tarefa"), Toast.LENGTH_SHORT).show(); return; }
        String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
        if (cookie == null || cookie.isEmpty()) {
            Toast.makeText(this, Tr.t("Abre o Odysseus e inicia sessão primeiro"), Toast.LENGTH_LONG).show();
            return;
        }
        btn.setEnabled(false);
        new Thread(() -> {
            int code;
            try {
                JSONObject body = new JSONObject().put("title", title).put("content", "");
                if (hasDate) {
                    // Local wall-clock time, no zone (same format the Odysseus web UI sends).
                    body.put("due_date", String.format(Locale.ROOT, "%04d-%02d-%02dT%02d:%02d:00",
                            when.get(Calendar.YEAR), when.get(Calendar.MONTH) + 1, when.get(Calendar.DAY_OF_MONTH),
                            when.get(Calendar.HOUR_OF_DAY), when.get(Calendar.MINUTE)));
                }
                code = Actions.send("POST", NoteSync.SITE + "/api/notes", cookie, "application/json", body.toString());
            } catch (Exception e) { code = -1; }
            final int c = code;
            if (c == 200) NoteSync.runSync(getApplicationContext());
            runOnUiThread(() -> {
                if (c == 200) {
                    Toast.makeText(this, "Tarefa guardada", Toast.LENGTH_SHORT).show();
                    finish();
                } else {
                    btn.setEnabled(true);
                    Toast.makeText(this, Tr.t("Não foi possível guardar (") + c + Tr.t("). Tens o Tailscale ligado?"), Toast.LENGTH_LONG).show();
                }
            });
        }).start();
    }

    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density); }
}
