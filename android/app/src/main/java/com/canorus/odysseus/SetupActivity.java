package com.canorus.odysseus;

import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Primeiro ecrã da app: idioma, endereço do servidor (com teste de ligação) e o que vem a seguir.
 * As chaves de API, emails e restantes serviços configuram-se depois do início de sessão, no assistente
 * "Setup" do Odysseus (Tools → Setup), que abre sozinho na primeira vez.
 */
public class SetupActivity extends AppCompatActivity {
    private static final int BG = Color.parseColor("#282c34"), FG = Color.parseColor("#E5E9F0"),
            MUTED = Color.parseColor("#9AA3B2"), ACCENT = Color.parseColor("#7C9CFF"), OK = Color.parseColor("#4cc38a"),
            BAD = Color.parseColor("#ef6b6b");
    private EditText url;
    private TextView status;
    private Button go;
    private volatile String testedUrl;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(BG);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int p = dp(22);
        root.setPadding(p, p * 2, p, p);
        sv.addView(root);
        setContentView(sv);

        TextView h = text("Odysseus KIT", 26, FG);
        h.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(h);
        TextView sub = text(L.t("Vamos configurar a app em 2 passos."), 15, MUTED);
        root.addView(sub);

        // 1) idioma
        root.addView(section(L.t("1. Idioma")));
        RadioGroup rg = new RadioGroup(this);
        RadioButton en = radio("English", "en");
        RadioButton pt = radio("Português", "pt");
        rg.addView(en);
        rg.addView(pt);
        String cur = L.lang();
        (("pt".equals(cur)) ? pt : en).setChecked(true);
        rg.setOnCheckedChangeListener((g, id) -> {
            L.set(id == pt.getId() ? "pt" : "en");
            recreate();
        });
        root.addView(rg);

        // 2) servidor
        root.addView(section(L.t("2. O teu servidor")));
        root.addView(text(L.t("Endereço do teu Odysseus (o mesmo que abres no browser), por exemplo https://o-teu-servidor.tuarede.ts.net"), 13, MUTED));
        url = new EditText(this);
        url.setTextColor(FG);
        url.setHintTextColor(MUTED);
        url.setHint("https://...");
        url.setSingleLine(true);
        url.setInputType(android.text.InputType.TYPE_TEXT_VARIATION_URI);
        String saved = AppSettings.serverUrl(this);
        if (saved != null) url.setText(saved);
        root.addView(url);

        status = text("", 14, MUTED);
        root.addView(status);
        Button test = button(L.t("Testar ligação"));
        test.setOnClickListener(v -> testConnection());
        root.addView(test);

        TextView next = text(L.t("Depois de iniciares sessão no Odysseus, abre-se o assistente de configuração (Tools → Setup), onde indicas as chaves e ativas só o que quiseres. Podes saltar passos e voltar mais tarde."), 13, MUTED);
        next.setPadding(0, dp(14), 0, dp(6));
        root.addView(next);

        go = button(L.t("Continuar"));
        go.setOnClickListener(v -> finishSetup());
        root.addView(go);
    }

    private void testConnection() {
        final String u = clean(url.getText().toString());
        if (u == null) { show(L.t("Escreve um endereço que comece por https://"), BAD); return; }
        testedUrl = null;
        show(L.t("A testar..."), MUTED);
        Bg.run(() -> {
            String msg; int color;
            try {
                int code = Http.headOrGetCode(u + "/api/auth/status", null, 8000);
                if (code == 200) { msg = L.t("Ligação OK. Odysseus encontrado."); color = OK; testedUrl = u; }
                else if (code < 0) { msg = L.t("Não consegui ligar. Confirma o endereço e se o Tailscale (ou a VPN) está ligado."); color = BAD; }
                else { msg = L.t("O servidor respondeu, mas não parece ser o Odysseus (código ") + code + ")."; color = BAD; }
            } catch (Exception e) {
                msg = L.t("Não consegui ligar. Confirma o endereço e se o Tailscale (ou a VPN) está ligado."); color = BAD;
            }
            final String m = msg; final int col = color;
            runOnUiThread(() -> show(m, col));
        });
    }

    private void finishSetup() {
        String u = clean(url.getText().toString());
        if (u == null) { show(L.t("Escreve um endereço que comece por https://"), BAD); return; }
        if (!u.equals(testedUrl)) { show(L.t("Testa a ligação antes de continuar."), BAD); return; }
        AppSettings.sp(this).edit().putString("server_url", u).putBoolean("setup_done", true).apply();
        AppSettings.applyServer(this);
        startActivity(new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
        finish();
    }

    /** Aceita endereços HTTPS e remove a barra final. */
    private static String clean(String s) {
        if (s == null) return null;
        s = s.trim();
        try {
            java.net.URI uri = new java.net.URI(s);
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                    || uri.getRawUserInfo() != null || uri.getRawQuery() != null || uri.getRawFragment() != null) return null;
        } catch (java.net.URISyntaxException e) {
            return null;
        }
        while (s.endsWith("/")) s = s.substring(0, s.length() - 1);
        return s.length() > 8 ? s : null;
    }

    private void show(String m, int color) { status.setText(m); status.setTextColor(color); }

    private TextView text(String s, int sp, int color) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setPadding(0, dp(6), 0, dp(6));
        return t;
    }

    private TextView section(String s) {
        TextView t = text(s, 17, ACCENT);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setPadding(0, dp(20), 0, dp(4));
        return t;
    }

    private RadioButton radio(String label, String tag) {
        RadioButton r = new RadioButton(this);
        r.setText(label);
        r.setTextColor(FG);
        r.setId(View.generateViewId());
        r.setTag(tag);
        return r;
    }

    private Button button(String s) {
        Button b = new Button(this);
        b.setText(s);
        b.setAllCaps(false);
        return b;
    }

    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density); }
}
