package org.odysseuskit.app;

import android.content.Context;
import android.content.res.AssetManager;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

/**
 * Tradução dos textos da app. O código-fonte está em português; com o idioma "en" cada texto é procurado em
 * assets/i18n_en.json (gerado por scripts/build_i18n.py). Textos sem tradução ficam como estão.
 */
final class Tr {
    private Tr() { }

    static volatile Context app;
    private static volatile String lang = "en";
    private static volatile Map<String, String> map;

    static void init(Context c) {
        app = c.getApplicationContext();
        lang = AppSettings.language(app);
        map = null;
    }

    static void setLang(Context c, String l) {
        AppSettings.sp(c).edit().putString("lang", l).apply();
        init(c);
    }

    static String lang() { return lang; }

    /** Devolve o texto no idioma escolhido (a chave é o texto em português). */
    static String t(String pt) {
        if (pt == null || !"en".equals(lang)) return pt;
        Map<String, String> m = map;
        if (m == null) m = load();
        String v = m.get(pt);
        return v != null ? v : pt;
    }

    private static synchronized Map<String, String> load() {
        if (map != null) return map;
        Map<String, String> m = new HashMap<>();
        try {
            Context c = app;
            if (c != null) {
                AssetManager am = c.getAssets();
                try (InputStream in = am.open("i18n_en.json")) {
                    ByteArrayOutputStream out = new ByteArrayOutputStream();
                    byte[] buf = new byte[8192];
                    int n;
                    while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                    JSONObject o = new JSONObject(out.toString("UTF-8"));
                    java.util.Iterator<String> it = o.keys();
                    while (it.hasNext()) {
                        String k = it.next();
                        m.put(k, o.getString(k));
                    }
                }
            }
        } catch (Exception ignored) { }
        map = m;
        return m;
    }
}
