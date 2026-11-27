package com.canorus.odysseus;

import android.content.Context;

/** Idioma da app (o mesmo da interface web: 'pt' ou 'en'). L.t("texto em português") devolve o texto no idioma ativo.
 *  Gerado a partir de ~/odysseus-i18n/native/en_native.py (gen_L.py). */
final class L {
    private L() { }

    static Context app;
    private static String cached;

    static void init(Context c) { if (app == null && c != null) app = c.getApplicationContext(); }

    static String lang() {
        if (cached != null) return cached;
        String l = "pt";
        try { if (app != null) l = AppSettings.sp(app).getString("kitlang", "pt"); } catch (Exception ignored) { }
        cached = "en".equals(l) ? "en" : "pt";
        return cached;
    }

    static boolean isEn() { return "en".equals(lang()); }

    /** Guarda o idioma e redesenha os widgets. Devolve true se mudou. */
    static boolean set(String l) {
        String n = "en".equals(l) ? "en" : "pt";
        boolean changed = !n.equals(lang());
        cached = n;
        if (app != null) AppSettings.sp(app).edit().putString("kitlang", n).apply();
        if (changed && app != null) { Channels.invalidateAndRefresh(app); refreshWidgets(app); }
        return changed;
    }

    static void refreshWidgets(Context c) {
        Class<?>[] cls = { OdysseusWidget.class, ShortcutsWidget.class, Widgets.Chat.class, Widgets.Translate.class,
                Widgets.Photo.class, Widgets.Notes.class, Widgets.Tasks.class, Widgets.Expenses.class };
        android.appwidget.AppWidgetManager m = android.appwidget.AppWidgetManager.getInstance(c);
        for (Class<?> k : cls) {
            try {
                int[] ids = m.getAppWidgetIds(new android.content.ComponentName(c, k));
                if (ids == null || ids.length == 0) continue;
                c.sendBroadcast(new android.content.Intent(android.appwidget.AppWidgetManager.ACTION_APPWIDGET_UPDATE)
                        .setComponent(new android.content.ComponentName(c, k))
                        .putExtra(android.appwidget.AppWidgetManager.EXTRA_APPWIDGET_IDS, ids));
            } catch (Exception ignored) { }
        }
    }

    static { System.loadLibrary("odysseus_voice"); }
    private static native String english(String text);

    static String t(String pt) {
        return pt == null || !isEn() ? pt : english(pt);
    }
}
