package org.odysseuskit.app;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
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


import java.util.ArrayList;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.OutputStream;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import org.json.JSONObject;
import java.util.Locale;

/**
 * Quick translator backed by the server's /translate/api (Gemini 3.6 Flash, Claude Haiku as
 * fallback), always European Portuguese. Needs the Tailscale connection like the rest of the app.
 * Also appears in the text-selection menu of other apps ("Traduzir (Odysseus)").
 */
public class TranslateActivity extends AppCompatActivity {
    private static final int BG = Color.parseColor("#282c34"), FG = Color.parseColor("#E5E9F0"),
            MUTED = Color.parseColor("#9AA3B2"), CARD = Color.parseColor("#323844");
    private static final String AUTO = "auto";
    private static final String[][] LANGS = {
            {AUTO, "Detetar idioma"}, {"pt", Tr.t("Português (Portugal)")}, {"en", Tr.t("Inglês")}, {"es", "Espanhol"}, {"fr", Tr.t("Francês")},
            {"de", Tr.t("Alemão")}, {"it", "Italiano"}, {"nl", Tr.t("Neerlandês")}, {"zh", Tr.t("Chinês")}, {"ja", Tr.t("Japonês")},
            {"ko", "Coreano"}, {"ar", Tr.t("Árabe")}, {"ru", "Russo"}, {"uk", "Ucraniano"}, {"ro", "Romeno"},
            {"pl", "Polaco"}, {"tr", "Turco"}, {"hi", "Hindi"}, {"sv", "Sueco"}, {"el", "Grego"},
    };

    private EditText input;
    private EditText output;
    private TextView status;
    private Spinner from, to;
    private int seq = 0;
    private final Handler h = new Handler(Looper.getMainLooper());
    private final Runnable run = this::translate;
    private TextToSpeech tts;
    private String lastTarget = "en";
    private boolean replaceMode = false;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(BG);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int p = dp(16);
        root.setPadding(p, p, p, p);
        sv.addView(root);
        setContentView(sv);

        TextView title = new TextView(this);
        title.setText("Tradutor");
        title.setTextSize(22);
        title.setTextColor(FG);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        LinearLayout langs = new LinearLayout(this);
        langs.setGravity(Gravity.CENTER_VERTICAL);
        from = spinner(true);
        to = spinner(false);
        Button swap = small("⇄");
        langs.addView(from, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        langs.addView(swap);
        langs.addView(to, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        root.addView(langs);

        input = new EditText(this);
        input.setHint(Tr.t("Escreve, cola ou dita o texto…"));
        input.setHintTextColor(MUTED);
        input.setTextColor(FG);
        input.setMinLines(4);
        input.setGravity(Gravity.TOP);
        input.setBackgroundColor(CARD);
        input.setPadding(p, p, p, p);
        root.addView(input, matchWrap());

        LinearLayout tools1 = new LinearLayout(this);
        Button paste = small("Colar"), mic = small("🎤 Ditar"), clear = small("Limpar");
        tools1.addView(paste);
        tools1.addView(mic);
        tools1.addView(clear);
        root.addView(tools1);

        status = new TextView(this);
        status.setTextColor(MUTED);
        status.setTextSize(12);
        root.addView(status);

        output = new EditText(this);   // editável: dá para corrigir a tradução antes de copiar
        output.setTextColor(FG);
        output.setTextSize(18);
        output.setHint(Tr.t("Tradução"));
        output.setHintTextColor(MUTED);
        output.setGravity(Gravity.TOP);
        output.setMinLines(4);
        output.setBackgroundColor(CARD);
        output.setPadding(p, p, p, p);
        root.addView(output, matchWrap());

        LinearLayout tools2 = new LinearLayout(this);
        Button copy = small("Copiar"), speak = small("🔊 Ouvir"), share = small("Partilhar"), replace = small("Substituir");
        tools2.addView(copy);
        tools2.addView(speak);
        tools2.addView(share);
        root.addView(tools2);

        // Text coming from the selection menu of another app, or shared to the translator.
        Intent in = getIntent();
        CharSequence incoming = in.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT);
        if (incoming == null) incoming = in.getCharSequenceExtra(Intent.EXTRA_TEXT);
        if (Intent.ACTION_PROCESS_TEXT.equals(in.getAction()) && !in.getBooleanExtra(Intent.EXTRA_PROCESS_TEXT_READONLY, true)) {
            replaceMode = true;
            tools2.addView(replace);
        }

        input.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int a, int c, int d) { }
            public void onTextChanged(CharSequence s, int a, int c, int d) { }
            public void afterTextChanged(Editable e) { h.removeCallbacks(run); h.postDelayed(run, 450); }
        });
        AdapterView.OnItemSelectedListener re = new AdapterView.OnItemSelectedListener() {
            public void onItemSelected(AdapterView<?> a, View v, int pos, long id) {
                AppSettings.sp(TranslateActivity.this).edit()
                        .putString("tr_from", code(from)).putString("tr_to", code(to)).apply();
                translate();
            }
            public void onNothingSelected(AdapterView<?> a) { }
        };
        from.setOnItemSelectedListener(re);
        to.setOnItemSelectedListener(re);

        swap.setOnClickListener(v -> {
            String f = code(from).equals(AUTO) ? lastDetected : code(from);
            String t = code(to);
            select(from, t);
            select(to, f == null ? "pt" : f);
            CharSequence out = output.getText();
            if (out.length() > 0) input.setText(out);
        });
        paste.setOnClickListener(v -> {
            ClipboardManager cm = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            ClipData c = cm.getPrimaryClip();
            if (c != null && c.getItemCount() > 0) input.setText(c.getItemAt(0).coerceToText(this));
        });
        clear.setOnClickListener(v -> { input.setText(""); output.setText(""); });
        mic.setOnClickListener(v -> {
            Intent r = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            String f = code(from);
            if (!f.equals(AUTO)) r.putExtra(RecognizerIntent.EXTRA_LANGUAGE, f.equals("pt") ? "pt-PT" : f);
            try { startActivityForResult(r, 77); } catch (Exception e) { toast(Tr.t("Ditado indisponível: ativa a escrita por voz da Google no telemóvel")); }
        });
        copy.setOnClickListener(v -> {
            ((ClipboardManager) getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText(Tr.t("tradução"), output.getText()));
            toast("Copiado");
        });
        share.setOnClickListener(v -> startActivity(Intent.createChooser(
                new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, output.getText().toString()), Tr.t("Partilhar tradução"))));
        speak.setOnClickListener(v -> speak());
        replace.setOnClickListener(v -> {
            setResult(RESULT_OK, new Intent().putExtra(Intent.EXTRA_PROCESS_TEXT, output.getText().toString()));
            finish();
        });

        select(from, AppSettings.sp(this).getString("tr_from", AUTO));
        select(to, AppSettings.sp(this).getString("tr_to", "en"));
        if (incoming != null) {
            select(from, AUTO);
            select(to, "pt");
            input.setText(incoming);
        } else {
            input.requestFocus();
        }
    }

    private String lastDetected = null;

    private void translate() {
        String text = input.getText().toString().trim();
        if (text.isEmpty()) { seq++; output.setText(""); status.setText(""); return; }
        final String src = code(from), dst = code(to);
        final int my = ++seq;
        status.setText("A traduzir…");
        new Thread(() -> {
            String out = null, det = "", engine = "", err = null;
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(AppSettings.sp(this).getString("tr_base", NoteSync.SITE) + "/translate/api").openConnection();
                c.setConnectTimeout(8000);
                c.setReadTimeout(60000);
                c.setRequestMethod("POST");
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                JSONObject body = new JSONObject().put("text", text).put("source", src).put("target", dst);
                try (OutputStream os = c.getOutputStream()) { os.write(body.toString().getBytes("UTF-8")); }
                int code = c.getResponseCode();
                InputStream is = code < 400 ? c.getInputStream() : c.getErrorStream();
                ByteArrayOutputStream bo = new ByteArrayOutputStream();
                byte[] buf = new byte[4096]; int n;
                while (is != null && (n = is.read(buf)) > 0) bo.write(buf, 0, n);
                JSONObject j = new JSONObject(bo.toString("UTF-8"));
                if (code >= 400 || j.has("error")) err = j.optString("error", "HTTP " + code);
                else {
                    out = j.optString("translation");
                    det = j.optString("detected");
                    engine = j.optString("engine");
                }
            } catch (Exception e) {
                err = Tr.t("Sem ligação ao servidor. Tens o Tailscale ligado?");
            }
            final String fo = out, fd = det, fe = err, feng = engine;
            h.post(() -> {
                if (my != seq || isFinishing()) return;
                if (fe != null) { status.setText(fe); return; }
                output.setText(fo);
                lastTarget = dst;
                if (!fd.isEmpty()) lastDetected = fd;
                String note = (src.equals(AUTO) && !fd.isEmpty() ? "Detetado: " + name(fd) + " · " : "")
                        + (feng.startsWith("gemini") ? "Gemini" : "Claude Haiku (reserva)");
                status.setText(note);
            });
        }).start();
    }

    private android.media.MediaPlayer player;

    /** "Ouvir": voz neural do servidor (MP3); se falhar, a voz do telemóvel. */
    private void speak() {
        final String text = output.getText().toString().trim();
        if (text.isEmpty()) return;
        final String lang = lastTarget;
        status.setText("A preparar a voz…");
        new Thread(() -> {
            java.io.File f = new java.io.File(getCacheDir(), "tts.mp3");
            boolean ok = false;
            try {
                HttpURLConnection c = (HttpURLConnection) new URL(AppSettings.sp(this).getString("tr_base", NoteSync.SITE) + "/translate/tts").openConnection();
                c.setConnectTimeout(8000);
                c.setReadTimeout(60000);
                c.setRequestMethod("POST");
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                try (OutputStream os = c.getOutputStream()) { os.write(new JSONObject().put("text", text).put("lang", lang).toString().getBytes("UTF-8")); }
                if (c.getResponseCode() == 200) {
                    try (InputStream is = c.getInputStream(); java.io.FileOutputStream fo = new java.io.FileOutputStream(f)) {
                        byte[] buf = new byte[8192]; int n;
                        while ((n = is.read(buf)) > 0) fo.write(buf, 0, n);
                    }
                    ok = f.length() > 0;
                }
            } catch (Exception ignored) { }
            final boolean got = ok;
            h.post(() -> {
                if (isFinishing()) return;
                status.setText("");
                if (got) {
                    try {
                        if (player != null) player.release();
                        player = new android.media.MediaPlayer();
                        player.setDataSource(f.getAbsolutePath());
                        player.setOnCompletionListener(mp -> { mp.release(); if (player == mp) player = null; });
                        player.prepare();
                        player.start();
                        return;
                    } catch (Exception e) { player = null; }
                }
                speakDevice(text);
            });
        }).start();
    }

    private void speakDevice(String text) {
        if (tts == null) {
            tts = new TextToSpeech(getApplicationContext(), st -> {
                if (st == TextToSpeech.SUCCESS) speakNow(text);
                else { tts = null; toast(Tr.t("Voz indisponível neste telemóvel")); }
            });
        } else speakNow(text);
    }

    private void speakNow(String text) {
        int r = tts.setLanguage(lastTarget.equals("pt") ? Locale.forLanguageTag("pt-PT") : Locale.forLanguageTag(lastTarget));
        if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) {
            r = tts.setLanguage(new Locale(lastTarget));
            if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) {
                toast(Tr.t("Falta a voz deste idioma. Instala-a em Definições > Texto para voz."));
                return;
            }
        }
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "tr");
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == 77 && res == RESULT_OK && data != null) {
            ArrayList<String> r = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (r != null && !r.isEmpty()) input.setText(r.get(0));
        }
    }

    @Override
    protected void onDestroy() {
        if (tts != null) tts.shutdown();
        try { if (player != null) player.release(); } catch (Exception ignored) { }
        super.onDestroy();
    }

    // ---- helpers ----
    private Spinner spinner(boolean withAuto) {
        ArrayList<String> names = new ArrayList<>();
        for (String[] l : LANGS) if (withAuto || !l[0].equals(AUTO)) names.add(l[1]);
        Spinner s = new Spinner(this);
        ArrayAdapter<String> a = new ArrayAdapter<String>(this, android.R.layout.simple_spinner_item, names) {
            @Override public View getView(int pos, View v, ViewGroup p) {
                View x = super.getView(pos, v, p);
                ((TextView) x).setTextColor(FG);
                return x;
            }
        };
        a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        s.setAdapter(a);
        s.setTag(withAuto);
        return s;
    }

    private String code(Spinner s) {
        int pos = s.getSelectedItemPosition();
        boolean withAuto = (Boolean) s.getTag();
        return LANGS[withAuto ? pos : pos + 1][0];
    }

    private void select(Spinner s, String code) {
        boolean withAuto = (Boolean) s.getTag();
        for (int i = 0; i < LANGS.length; i++) {
            if (LANGS[i][0].equals(code)) {
                int pos = withAuto ? i : i - 1;
                if (pos >= 0) s.setSelection(pos);
                return;
            }
        }
    }

    private static String name(String code) {
        for (String[] l : LANGS) if (l[0].equals(code)) return l[1];
        return code;
    }

    private Button small(String t) {
        Button b = new Button(this);
        b.setText(t);
        b.setAllCaps(false);
        return b;
    }

    private LinearLayout.LayoutParams matchWrap() {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(8);
        return lp;
    }

    private void toast(String m) { Toast.makeText(this, m, Toast.LENGTH_SHORT).show(); }

    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density); }
}
