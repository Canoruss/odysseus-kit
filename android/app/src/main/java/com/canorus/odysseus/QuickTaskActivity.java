package com.canorus.odysseus;

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

/** Small L.t("Nova tarefa") window (launcher shortcut and widget "+"): title + optional date/time. */
public class QuickTaskActivity extends AppCompatActivity {
    private final Calendar when = Calendar.getInstance();
    private boolean hasDate = false;
    private Button dateBtn, timeBtn, micBtn;
    private EditText title;
    private boolean voiceMode = false;
    private LinearLayout rootBox;
    private boolean ownRecorder = false;   // a gravação própria está ativa: ignorar resultados do reconhecedor da Google
    private int fg = 0xFFE5E9F0, btnBg = 0xFF3d4452;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setTitle(L.t("Nova tarefa"));
        int pad = dp(20);
        LinearLayout box = new LinearLayout(this);
        rootBox = box;
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(pad, pad, pad, pad);
        if ("ryoku".equals(AppSettings.sp(this).getString("ui_theme", ""))) {   // mesmo tema Ryoku do resto da app
            fg = 0xFFcdc4ba; btnBg = 0xFF141414;
            box.setBackgroundColor(0xFF0a0a0a);
            getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(0xFF0a0a0a));
        } else {
            box.setBackgroundColor(0xFF282c34);
            getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(0xFF282c34));
        }

        title = new EditText(this);
        title.setTextColor(fg); title.setHintTextColor(0xFF958f87);
        title.setHint(L.t("O que tens de fazer? (escreve \"alarme\" para tocar como alarme)"));
        title.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        box.addView(title, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout row = new LinearLayout(this);
        row.setGravity(Gravity.CENTER_VERTICAL);
        dateBtn = new Button(this);
        timeBtn = new Button(this);
        dateBtn.setText(L.t("Sem data"));
        timeBtn.setText(L.t("Hora"));
        timeBtn.setEnabled(false);
        micBtn = new Button(this);
        micBtn.setText(L.t("🎤 Ditar"));
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
        cancel.setText(L.t("Cancelar"));
        cancel.setOnClickListener(v -> finish());
        Button save = new Button(this);
        save.setText(L.t("Guardar"));
        save.setOnClickListener(v -> save(title.getText().toString().trim(), save));
        actions.addView(cancel);
        actions.addView(save);
        box.addView(actions);

        for (Button bb : new Button[] { dateBtn, timeBtn, micBtn, cancel, save }) { bb.setTextColor(fg); bb.setBackgroundColor(btnBg); bb.setAllCaps(false); }
        setContentView(box);
        voiceMode = getIntent().getBooleanExtra("voice", false);
        if (voiceMode && getIntent().getStringExtra("spoken") == null) {
            box.setVisibility(android.view.View.INVISIBLE);
            getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(0x00000000));
            setTitle("");
        }
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
                    .putExtra(RecognizerIntent.EXTRA_PROMPT, L.t("Diz a tarefa (ex.: \"ligar ao Pedro amanhã às 10\")"));
            if (i.resolveActivity(getPackageManager()) == null) throw new android.content.ActivityNotFoundException("sem reconhecedor");
            startActivityForResult(i, 77);
        } catch (Exception e) {
            ownRecorder = true;
            // sem reconhecimento da Google: grava e transcreve no servidor
            Voice.listen(this, L.isEn() ? "en" : "pt", txt -> {
                ownRecorder = false;
                if (txt.isEmpty()) { noSpeech(); return; }
                showForm();
                applySpoken(txt);
                if (voiceMode) {
                    String when1 = hasDate ? " — " + dateBtn.getText() + " " + timeBtn.getText() : "";
                    Toast.makeText(this, L.t("Tarefa: ") + title.getText() + when1, Toast.LENGTH_LONG).show();
                    save(title.getText().toString().trim(), micBtn);
                }
            });
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != 77 || ownRecorder) return;
        ArrayList<String> r = res == RESULT_OK && data != null ? data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS) : null;
        if (r == null || r.isEmpty() || r.get(0).trim().isEmpty()) { noSpeech(); return; }
        showForm();
        applySpoken(r.get(0).trim());
        if (voiceMode) {
            String when1 = hasDate ? " — " + dateBtn.getText() + " " + timeBtn.getText() : "";
            Toast.makeText(this, L.t("Tarefa: ") + title.getText() + when1, Toast.LENGTH_LONG).show();
            save(title.getText().toString().trim(), micBtn);
        }
    }

    /** Nada reconhecido: mostra o formulário para escrever e diz porquê, em vez de fechar em silêncio. */
    private void showForm() {
        boolean ry = "ryoku".equals(AppSettings.sp(this).getString("ui_theme", ""));
        getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(ry ? 0xFF0a0a0a : 0xFF282c34));
        setTitle(L.t("Nova tarefa"));
        rootBox.setVisibility(android.view.View.VISIBLE);
    }

    private void noSpeech() {
        showForm();
        Toast.makeText(this, L.t("Não percebi nada. Escreve a tarefa ou carrega em Ditar."), Toast.LENGTH_LONG).show();
        title.requestFocus();
    }

    /** Interpreta "amanhã", "hoje", "depois de amanhã", "às 9", "às 18h30", "daqui a 20 minutos / 2 horas". */
    private void applySpoken(String spoken) {
        String t = spoken;
        if (L.isEn()) {   // inglês falado -> mesmas expressões que o interpretador português já entende
            t = t.replaceAll("(?i)\\bday after tomorrow\\b", "depois de amanhã")
                 .replaceAll("(?i)\\btomorrow\\b", "amanhã")
                 .replaceAll("(?i)\\btoday\\b", "hoje")
                 .replaceAll("(?i)\\bin (\\d+) (minutes?|mins?|hours?)\\b", "daqui a $1 $2")
                 .replaceAll("(?i)daqui a (\\d+) (minutes?|mins?)", "daqui a $1 minutos")
                 .replaceAll("(?i)daqui a (\\d+) hours?", "daqui a $1 horas")
                 .replaceAll("(?i)\\bat (\\d{1,2}):(\\d{2}) ?a\\.?m\\b\\.?", "às $1:$2 da manhã")
                 .replaceAll("(?i)\\bat (\\d{1,2}):(\\d{2}) ?p\\.?m\\b\\.?", "às $1:$2 da tarde")
                 .replaceAll("(?i)\\bat (\\d{1,2}) ?a\\.?m\\b\\.?", "às $1:00 da manhã")
                 .replaceAll("(?i)\\bat (\\d{1,2}) ?p\\.?m\\b\\.?", "às $1:00 da tarde")
                 .replaceAll("(?i)\\bat (\\d{1,2}):(\\d{2})\\b", "às $1:$2")
                 .replaceAll("(?i)\\bat (\\d{1,2})\\b", "às $1:00")
                 .replaceAll("(?i)\\bo'?clock\\b", "");
        }
        Calendar c = Calendar.getInstance();
        boolean date = false, time = false;
        Matcher m = Pattern.compile("(?i)daqui a (\\d+) (minutos?|horas?)").matcher(t);
        if (m.find()) {
            int n = Integer.parseInt(m.group(1));
            c.add(m.group(2).toLowerCase(Locale.ROOT).startsWith("min") ? Calendar.MINUTE : Calendar.HOUR_OF_DAY, n);
            t = t.replace(m.group(), ""); date = true; time = true;
        } else {
            m = Pattern.compile("(?i)depois de amanh[ãa]").matcher(t);
            if (m.find()) { c.add(Calendar.DAY_OF_MONTH, 2); t = t.replace(m.group(), ""); date = true; }
            else {
                m = Pattern.compile("(?i)amanh[ãa]").matcher(t);
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
        if (title.isEmpty()) { Toast.makeText(this, L.t("Escreve o título da tarefa"), Toast.LENGTH_SHORT).show(); return; }
        String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
        if (cookie == null || cookie.isEmpty()) {
            Toast.makeText(this, L.t("Abre o Odysseus e inicia sessão primeiro"), Toast.LENGTH_LONG).show();
            return;
        }
        btn.setEnabled(false);
        Bg.run(() -> {
            int code;
            JSONObject body = null;
            try {
                body = new JSONObject().put("title", title).put("content", "");
                if (hasDate) {
                    body.put("due_date", String.format(Locale.ROOT, "%04d-%02d-%02dT%02d:%02d:00",
                            when.get(Calendar.YEAR), when.get(Calendar.MONTH) + 1, when.get(Calendar.DAY_OF_MONTH),
                            when.get(Calendar.HOUR_OF_DAY), when.get(Calendar.MINUTE)));
                }
                code = Bg.isOnline(this) ? Actions.send("POST", NoteSync.SITE + "/api/notes", cookie, "application/json", body.toString()) : -1;
            } catch (Exception e) { code = -1; }
            if (code == -1 && body != null) {
                Outbox.enqueue(this, "/api/notes", body);
            }
            final int c = code;
            if (c == 200) NoteSync.runSync(getApplicationContext(), true);
            runOnUiThread(() -> {
                if (c == 200) {
                    Toast.makeText(this, L.t("Tarefa guardada"), Toast.LENGTH_SHORT).show();
                    finish();
                } else if (c == -1) {
                    Toast.makeText(this, L.t("Sem ligação agora — guardado no telemóvel para enviar assim que ligar."), Toast.LENGTH_LONG).show();
                    finish();
                } else {
                    btn.setEnabled(true);
                    Toast.makeText(this, L.t("Não foi possível guardar (") + c + L.t("). Tens o Tailscale ligado?"), Toast.LENGTH_LONG).show();
                }
            });
        });
    }

    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density); }
}
