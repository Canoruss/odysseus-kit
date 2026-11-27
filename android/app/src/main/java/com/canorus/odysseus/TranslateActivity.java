package com.canorus.odysseus;

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
    private int BG = Color.parseColor("#282c34"), FG = Color.parseColor("#E5E9F0"),
            MUTED = Color.parseColor("#9AA3B2"), CARD = Color.parseColor("#323844"), BTN = Color.parseColor("#3d4452"),
            ACCENT = Color.parseColor("#5b8abf");
    private boolean ryoku = false;
    private static final String AUTO = "auto";
    private static final String[][] LANGS = {
            {AUTO, L.t("Detetar idioma")}, {"pt", L.t("Português (Portugal)")}, {"en", L.t("Inglês")}, {"es", L.t("Espanhol")}, {"fr", L.t("Francês")},
            {"de", L.t("Alemão")}, {"it", L.t("Italiano")}, {"nl", L.t("Neerlandês")}, {"zh", L.t("Chinês")}, {"ja", L.t("Japonês")},
            {"ko", L.t("Coreano")}, {"ar", L.t("Árabe")}, {"ru", L.t("Russo")}, {"uk", L.t("Ucraniano")}, {"ro", L.t("Romeno")},
            {"pl", L.t("Polaco")}, {"tr", L.t("Turco")}, {"hi", L.t("Hindi")}, {"sv", L.t("Sueco")}, {"el", L.t("Grego")},
    };

    private EditText input;
    private EditText output;
    private TextView status, cnt;
    private EditText note;
    private LinearLayout repBox, convBox, convLog;
    private EditText convText;
    private Spinner convLang;
    private String convFrom, convTo;
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
        ryoku = "ryoku".equals(AppSettings.sp(this).getString("ui_theme", ""));
        if (ryoku) {   // mesma paleta do tema Ryoku do Odysseus
            BG = Color.parseColor("#000000"); FG = Color.parseColor("#cdc4ba"); MUTED = Color.parseColor("#958f87");
            CARD = Color.parseColor("#0a0a0a"); BTN = Color.parseColor("#141414"); ACCENT = Color.parseColor("#ce5e32");
        }
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
        title.setText(L.t("Tradutor"));
        title.setTextSize(22);
        title.setTextColor(FG);
        if (ryoku) title.setTextColor(ACCENT);
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

        LinearLayout extras = new LinearLayout(this);
        extras.setGravity(Gravity.CENTER_VERTICAL);
        Button bPhoto = small(L.t("📷 Foto")), bReply = small(L.t("💬 Sugerir resposta")), bConv = small(L.t("🗣 Conversa"));
        extras.addView(bPhoto); extras.addView(bReply); extras.addView(bConv);
        root.addView(extras);
        note = new EditText(this);
        note.setHint(L.t("O que queres responder (opcional)"));
        note.setHintTextColor(MUTED); note.setTextColor(FG); note.setBackgroundColor(CARD);
        note.setPadding(dp(12), dp(8), dp(12), dp(8)); note.setSingleLine(true);
        root.addView(note, matchWrap());

        input = new EditText(this);
        input.setHint(L.t("Escreve, cola ou dita o texto…"));
        input.setHintTextColor(MUTED);
        input.setTextColor(FG);
        input.setMinLines(4);
        input.setGravity(Gravity.TOP);
        input.setBackgroundColor(CARD);
        input.setPadding(p, p, p, p);
        root.addView(input, matchWrap());

        LinearLayout tools1 = new LinearLayout(this);
        Button paste = small(L.t("Colar")), mic = small(L.t("🎤 Ditar")), clear = small(L.t("Limpar"));
        tools1.addView(paste);
        tools1.addView(mic);
        tools1.addView(clear);
        cnt = new TextView(this);
        cnt.setTextColor(MUTED); cnt.setTextSize(12); cnt.setGravity(Gravity.CENTER_VERTICAL);
        tools1.addView(cnt);
        root.addView(tools1);

        status = new TextView(this);
        status.setTextColor(MUTED);
        status.setTextSize(12);
        root.addView(status);

        output = new EditText(this);   // editável: dá para corrigir a tradução antes de copiar
        output.setTextColor(FG);
        output.setTextSize(18);
        output.setHint(L.t("Tradução"));
        output.setHintTextColor(MUTED);
        output.setGravity(Gravity.TOP);
        output.setMinLines(4);
        output.setBackgroundColor(CARD);
        output.setPadding(p, p, p, p);
        root.addView(output, matchWrap());

        LinearLayout tools2 = new LinearLayout(this);
        Button copy = small(L.t("Copiar")), edit = small(L.t("✎ Editar")), speak = small(L.t("🔊 Ouvir")), share = small(L.t("Partilhar")), replace = small("Substituir");
        tools2.addView(copy);
        tools2.addView(edit);
        tools2.addView(speak);
        tools2.addView(share);
        root.addView(tools2);

        repBox = new LinearLayout(this); repBox.setOrientation(LinearLayout.VERTICAL); repBox.setBackgroundColor(CARD);
        repBox.setPadding(dp(12), dp(12), dp(12), dp(12)); repBox.setVisibility(View.GONE);
        root.addView(repBox, matchWrap());
        convBox = new LinearLayout(this); convBox.setOrientation(LinearLayout.VERTICAL); convBox.setBackgroundColor(CARD);
        convBox.setPadding(dp(12), dp(12), dp(12), dp(12)); convBox.setVisibility(View.GONE);
        root.addView(convBox, matchWrap());
        buildConv();
        bPhoto.setOnClickListener(v -> startActivity(new Intent(this, CameraTranslateActivity.class)));
        bReply.setOnClickListener(v -> suggestReply());
        bConv.setOnClickListener(v -> convBox.setVisibility(convBox.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE));

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
            public void afterTextChanged(Editable e) { cnt.setText(e.length() == 0 ? "" : e.length() + " " + L.t("car.")); h.removeCallbacks(run); h.postDelayed(run, 450); }
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
            try { startActivityForResult(r, 77); } catch (Exception e) {
                Voice.listen(this, f.equals(AUTO) ? "" : f, txt -> { if (!txt.isEmpty()) input.setText(txt); });
            }
        });
        copy.setOnClickListener(v -> {
            ((ClipboardManager) getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText(L.t("tradução"), output.getText()));
            toast(L.t("Copiado"));
        });
        share.setOnClickListener(v -> startActivity(Intent.createChooser(
                new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, output.getText().toString()), L.t("Partilhar tradução"))));
        speak.setOnClickListener(v -> speak());
        edit.setOnClickListener(v -> {
            if (output.getText().length() == 0) return;
            output.requestFocus(); output.setSelection(output.getText().length());
            ((android.view.inputmethod.InputMethodManager) getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(output, 0);
            status.setText(L.t("Podes editar a tradução"));
        });
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
        status.setText(L.t("A traduzir…"));
        Bg.run(() -> {
            if (my != seq || isFinishing()) return;
            String out = null, det = "", engine = "", err = null; long ms = 0;
            try {
                JSONObject body = new JSONObject().put("text", text).put("source", src).put("target", dst);
                Http.Resp resp = Http.request("POST", AppSettings.sp(this).getString("tr_base", NoteSync.SITE) + "/translate/api",
                        null, "application/json", body.toString(), 8000, 60000);
                int code = resp.code;
                JSONObject j = new JSONObject(resp.text() == null || resp.text().isEmpty() ? "{}" : resp.text());
                if (code >= 400 || j.has("error")) err = j.optString("error", "HTTP " + code);
                else {
                    out = j.optString("translation");
                    det = j.optString("detected");
                    engine = j.optString("engine"); ms = j.optLong("ms");
                }
            } catch (Exception e) {
                err = L.t("Sem ligação ao servidor. Tens o Tailscale ligado?");
            }
            final String fo = out, fd = det, fe = err, feng = engine; final long fms = ms;
            h.post(() -> {
                if (my != seq || isFinishing()) return;
                if (fe != null) { status.setText(fe); return; }
                output.setText(fo);
                lastTarget = dst;
                if (!fd.isEmpty()) lastDetected = fd;
                String note = (src.equals(AUTO) && !fd.isEmpty() ? L.t("Detetado: ") + name(fd) + " · " : "")
                        + engineName(feng) + " · " + String.format(java.util.Locale.US, "%.1f", fms / 1000.0) + " s";
                status.setText(note);
            });
        });
    }


    // ---- Sugerir resposta ao hóspede e Conversa: o mesmo que na janela do Odysseus ----
    private JSONObject postJson(String path, JSONObject body) throws Exception {
        Http.Resp resp = Http.request("POST", AppSettings.sp(this).getString("tr_base", NoteSync.SITE) + path,
                null, "application/json", body.toString(), 8000, 60000);
        JSONObject j = new JSONObject(resp.text() == null || resp.text().isEmpty() ? "{}" : resp.text());
        if (resp.code >= 400 || j.has("error")) throw new Exception(j.optString("error", "HTTP " + resp.code));
        return j;
    }

    private TextView label(String t) {
        TextView x = new TextView(this); x.setText(t); x.setTextColor(MUTED); x.setTextSize(12); return x;
    }

    private void suggestReply() {
        final String msg = input.getText().toString().trim();
        if (msg.isEmpty()) { status.setText(L.t("Cola primeiro a mensagem do hóspede.")); return; }
        final String f = code(from);
        final String lang = !f.equals(AUTO) ? f : (lastDetected == null ? "" : lastDetected);
        final String nt = note.getText().toString();
        repBox.removeAllViews(); repBox.setVisibility(View.VISIBLE);
        repBox.addView(label(L.t("A preparar a resposta…")));
        Bg.run(() -> {
            JSONObject j = null; String err = null;
            try { j = postJson("/translate/reply", new JSONObject().put("message", msg).put("lang", lang).put("note", nt)); }
            catch (Exception e) { err = e.getMessage() == null ? L.t("Sem ligação ao servidor. Tens o Tailscale ligado?") : e.getMessage(); }
            final JSONObject fj = j; final String fe = err;
            h.post(() -> {
                if (isFinishing()) return;
                repBox.removeAllViews();
                if (fe != null) { repBox.addView(label(L.t("Não consegui preparar a resposta: ") + fe)); return; }
                final String reply = fj.optString("reply"), rl = fj.optString("lang", "en");
                repBox.addView(label(L.t("Resposta para o hóspede (") + rl + ")"));
                TextView t1 = new TextView(this); t1.setText(reply); t1.setTextColor(FG); t1.setTextSize(17); t1.setTextIsSelectable(true); repBox.addView(t1);
                repBox.addView(label(L.t("Em português (para confirmares)")));
                TextView t2 = new TextView(this); t2.setText(fj.optString("reply_pt")); t2.setTextColor(FG); t2.setTextSize(15); t2.setTextIsSelectable(true); repBox.addView(t2);
                LinearLayout row = new LinearLayout(this);
                Button rc = small(L.t("Copiar resposta")), rs = small(L.t("🔊 Ouvir")), rx = small("✕");
                row.addView(rc); row.addView(rs); row.addView(rx); repBox.addView(row);
                rc.setOnClickListener(v -> { ((ClipboardManager) getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("resposta", reply)); toast(L.t("Resposta copiada ✓")); });
                rs.setOnClickListener(v -> speak(reply, rl));
                rx.setOnClickListener(v -> repBox.setVisibility(View.GONE));
            });
        });
    }

    private void buildConv() {
        LinearLayout r1 = new LinearLayout(this); r1.setGravity(Gravity.CENTER_VERTICAL);
        TextView who = new TextView(this); who.setText(L.t("Outra pessoa fala:")); who.setTextColor(FG);
        convLang = spinner(false);
        r1.addView(who); r1.addView(convLang, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        convBox.addView(r1);
        select(convLang, AppSettings.sp(this).getString("tr_conv", "en"));
        final Button ca = small(L.t("🎤 Eu (português)")), cb = small("🎤");
        LinearLayout r2 = new LinearLayout(this);
        r2.addView(ca); r2.addView(cb); convBox.addView(r2);
        convText = new EditText(this);
        convText.setHint(L.t("…ou escreve aqui e toca num dos botões")); convText.setHintTextColor(MUTED); convText.setTextColor(FG);
        convText.setBackgroundColor(BG); convText.setPadding(dp(10), dp(8), dp(10), dp(8)); convText.setSingleLine(true);
        convBox.addView(convText, matchWrap());
        convLog = new LinearLayout(this); convLog.setOrientation(LinearLayout.VERTICAL); convBox.addView(convLog, matchWrap());
        final Runnable upd = () -> cb.setText("🎤 " + name(code(convLang)));
        upd.run();
        convLang.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            public void onItemSelected(AdapterView<?> a, View v, int pos, long id) {
                AppSettings.sp(TranslateActivity.this).edit().putString("tr_conv", code(convLang)).apply(); upd.run();
            }
            public void onNothingSelected(AdapterView<?> a) { }
        });
        ca.setOnClickListener(v -> convStart("pt", code(convLang)));
        cb.setOnClickListener(v -> convStart(code(convLang), "pt"));
    }

    private void convStart(String f, String t) {
        String typed = convText.getText().toString().trim();
        convFrom = f; convTo = t;
        if (!typed.isEmpty()) { convText.setText(""); convTalk(typed, f, t); return; }
        Intent r = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, f.equals("pt") ? "pt-PT" : f);
        try { startActivityForResult(r, 78); } catch (Exception e) {
            Voice.listen(this, f, txt -> { if (!txt.isEmpty()) convTalk(txt, f, t); });
        }
    }

    private void convTalk(final String text, final String f, final String t) {
        status.setText(L.t("A traduzir…"));
        Bg.run(() -> {
            String out = null, err = null;
            try { out = postJson("/translate/api", new JSONObject().put("text", text).put("source", f).put("target", t)).optString("translation"); }
            catch (Exception e) { err = e.getMessage() == null ? L.t("Sem ligação ao servidor. Tens o Tailscale ligado?") : e.getMessage(); }
            final String fo = out, fe = err;
            h.post(() -> {
                if (isFinishing()) return;
                if (fe != null) { status.setText(fe); return; }
                status.setText("");
                LinearLayout item = new LinearLayout(this); item.setOrientation(LinearLayout.VERTICAL); item.setBackgroundColor(BG);
                item.setPadding(dp(10), dp(6), dp(10), dp(6));
                TextView o = new TextView(this); o.setText(text); o.setTextColor(MUTED); o.setTextSize(12);
                TextView tr = new TextView(this); tr.setText(fo); tr.setTextColor(FG); tr.setTextSize(17);
                item.addView(o); item.addView(tr);
                LinearLayout.LayoutParams lp = matchWrap(); convLog.addView(item, 0, lp);
                speak(fo, t);
            });
        });
    }

    private android.media.MediaPlayer player;

    /** "Ouvir": voz neural do servidor (MP3); se falhar, a voz do telemóvel. */
    private void speak() { speak(output.getText().toString().trim(), lastTarget); }

    private void speak(final String text, final String lang) {
        if (text == null || text.isEmpty()) return;
        lastTarget = lang;
        status.setText("A preparar a voz…");
        Bg.run(() -> {
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
        });
    }

    private void speakDevice(String text) {
        if (tts == null) {
            tts = new TextToSpeech(getApplicationContext(), st -> {
                if (st == TextToSpeech.SUCCESS) speakNow(text);
                else { tts = null; toast(L.t("Voz indisponível neste telemóvel")); }
            });
        } else speakNow(text);
    }

    private void speakNow(String text) {
        int r = tts.setLanguage(lastTarget.equals("pt") ? Locale.forLanguageTag("pt-PT") : Locale.forLanguageTag(lastTarget));
        if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) {
            r = tts.setLanguage(new Locale(lastTarget));
            if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) {
                toast(L.t("Falta a voz deste idioma. Instala-a em Definições > Texto para voz."));
                return;
            }
        }
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "tr");
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == 78 && res == RESULT_OK && data != null) {
            ArrayList<String> r = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (r != null && !r.isEmpty()) convTalk(r.get(0), convFrom, convTo);
        }
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
        for (String[] l : LANGS) if (withAuto || !l[0].equals(AUTO)) names.add(L.t(l[1]));
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

    private static String engineName(String e) {
        if (e == null) e = "";
        if (e.startsWith("gemini-3.6")) return "Gemini 3.6 Flash";
        if (e.startsWith("gemini-3.5")) return "Gemini 3.5 Flash";
        if (e.startsWith("gemini")) return "Gemini";
        if (e.startsWith("claude")) return L.t("Claude Haiku (reserva)");
        return e.isEmpty() ? L.t("Tradução") : e;
    }

    private static String name(String code) {
        for (String[] l : LANGS) if (l[0].equals(code)) return L.t(l[1]);
        return code;
    }

    private Button small(String t) {
        Button b = new Button(this);
        b.setText(t);
        b.setAllCaps(false);
        b.setTextColor(FG);
        b.setBackgroundColor(BTN);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.rightMargin = dp(6); lp.topMargin = dp(6);
        b.setLayoutParams(lp);
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
