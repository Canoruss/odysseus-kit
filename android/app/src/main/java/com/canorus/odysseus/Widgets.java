package com.canorus.odysseus;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.content.Intent;
import android.view.View;
import android.widget.RemoteViews;

/** Widgets pequenos (2x1), um por função: chat, tradução, tradução por foto, notas, tarefa rápida e despesas. */
public final class Widgets {
    private Widgets() {}

    abstract static class Base extends AppWidgetProvider {
        abstract int code();
        abstract String[] labels();
        abstract Intent[] intents(Context c);

        @Override
        public void onUpdate(Context ctx, AppWidgetManager mgr, int[] ids) {
            RemoteViews v = new RemoteViews(ctx.getPackageName(), R.layout.widget_icon);
            String[] l = labels();
            Intent[] in = intents(ctx);
            v.setTextViewText(R.id.w_a, l[0]);
            v.setOnClickPendingIntent(R.id.w_a, pi(ctx, code(), in[0]));
            if (l.length > 1) {
                v.setViewVisibility(R.id.w_b, View.VISIBLE);
                v.setTextViewText(R.id.w_b, l[1]);
                v.setOnClickPendingIntent(R.id.w_b, pi(ctx, code() + 1, in[1]));
            } else v.setViewVisibility(R.id.w_b, View.GONE);
            for (int id : ids) mgr.updateAppWidget(id, v);
        }

        static PendingIntent pi(Context ctx, int req, Intent i) {
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            return PendingIntent.getActivity(ctx, req, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        }
    }

    public static class Chat extends Base {
        int code() { return 40; }
        String[] labels() { return new String[]{L.t("💬\nNovo chat")}; }
        Intent[] intents(Context c) { return new Intent[]{new Intent(c, MainActivity.class).setAction(MainActivity.ACTION_NEW_CHAT)}; }
    }

    public static class Translate extends Base {
        int code() { return 42; }
        String[] labels() { return new String[]{L.t("🌐\nTradutor")}; }
        Intent[] intents(Context c) { return new Intent[]{new Intent(c, TranslateActivity.class)}; }
    }

    public static class Photo extends Base {
        int code() { return 44; }
        String[] labels() { return new String[]{L.t("📷\nTraduzir foto")}; }
        Intent[] intents(Context c) { return new Intent[]{new Intent(c, CameraTranslateActivity.class)}; }
    }

    public static class Notes extends AppWidgetProvider {
        @Override
        public void onUpdate(Context ctx, AppWidgetManager mgr, int[] ids) {
            render(ctx, mgr, ids);
            if (System.currentTimeMillis() - ctx.getSharedPreferences(NoteSync.PREFS, Context.MODE_PRIVATE).getLong("widget_at", 0L) > 10 * 60_000L) NoteSync.enqueueImmediateWork(ctx);
        }

        static void updateAll(Context ctx) {
            AppWidgetManager mgr = AppWidgetManager.getInstance(ctx);
            int[] ids = mgr.getAppWidgetIds(new android.content.ComponentName(ctx, Notes.class));
            if (ids != null && ids.length > 0) render(ctx, mgr, ids);
        }

        static void render(Context ctx, AppWidgetManager mgr, int[] ids) {
            RemoteViews v = new RemoteViews(ctx.getPackageName(), R.layout.widget_tasks);
            v.setTextViewText(R.id.w_title, L.t("Notas"));
            v.setTextViewText(R.id.w_list, text(ctx));
            PendingIntent open = Base.pi(ctx, 52, new Intent(ctx, MainActivity.class));
            v.setOnClickPendingIntent(R.id.w_root, open);
            v.setOnClickPendingIntent(R.id.w_list, open);
            v.setOnClickPendingIntent(R.id.w_add, Base.pi(ctx, 53, new Intent(ctx, QuickNoteActivity.class)));
            for (int id : ids) mgr.updateAppWidget(id, v);
        }

        static CharSequence text(Context ctx) {
            try {
                String s = ctx.getSharedPreferences(NoteSync.PREFS, Context.MODE_PRIVATE).getString("notes_items", null);
                if (s == null) return L.t("Abre a app uma vez para carregar as notas.");
                org.json.JSONArray a = new org.json.JSONArray(s);
                if (a.length() == 0) return L.t("Sem notas. Toca em + para criar.");
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < a.length(); i++) {
                    org.json.JSONObject o = a.getJSONObject(i);
                    if (sb.length() > 0) sb.append("\n\n");
                    sb.append(o.optString("title")).append("  ·  ").append(o.optString("when"));
                    String pv = o.optString("preview");
                    if (!pv.isEmpty()) sb.append('\n').append(pv);
                }
                return sb;
            } catch (Exception e) { return L.t("Sem dados."); }
        }
    }

    public static class Tasks extends Base {
        int code() { return 48; }
        String[] labels() { return new String[]{L.t("✅\nTarefa"), L.t("🎤\nFalar")}; }
        Intent[] intents(Context c) {
            return new Intent[]{new Intent(c, QuickTaskActivity.class), new Intent(c, QuickTaskActivity.class).putExtra("voice", true)};
        }
    }

    public static class Expenses extends Base {
        int code() { return 50; }
        String[] labels() { return new String[]{L.t("💶\nDespesa"), L.t("📷\nTalão")}; }
        Intent[] intents(Context c) {
            return new Intent[]{new Intent(c, QuickExpenseActivity.class), new Intent(c, QuickExpenseActivity.class).putExtra("photo", true)};
        }
    }
}
