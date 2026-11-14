package org.odysseuskit.app;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Date;
import java.util.Locale;

/** Home-screen widget: next dated tasks (filled by NoteSync) + "+" for a new task. */
public class OdysseusWidget extends AppWidgetProvider {

    @Override
    public void onUpdate(Context ctx, AppWidgetManager mgr, int[] ids) {
        render(ctx, mgr, ids);
        NoteSync.syncNow(ctx);
    }

    static void updateAll(Context ctx) {
        AppWidgetManager mgr = AppWidgetManager.getInstance(ctx);
        int[] ids = mgr.getAppWidgetIds(new ComponentName(ctx, OdysseusWidget.class));
        if (ids != null && ids.length > 0) render(ctx, mgr, ids);
    }

    private static void render(Context ctx, AppWidgetManager mgr, int[] ids) {
        RemoteViews v = new RemoteViews(ctx.getPackageName(), R.layout.widget_tasks);
        v.setTextViewText(R.id.w_list, text(ctx));
        PendingIntent open = PendingIntent.getActivity(ctx, 20, new Intent(ctx, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        PendingIntent add = PendingIntent.getActivity(ctx, 21, new Intent(ctx, QuickTaskActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK), PendingIntent.FLAG_IMMUTABLE);
        v.setOnClickPendingIntent(R.id.w_root, open);
        v.setOnClickPendingIntent(R.id.w_list, open);
        v.setOnClickPendingIntent(R.id.w_add, add);
        for (int id : ids) mgr.updateAppWidget(id, v);
    }

    private static CharSequence text(Context ctx) {
        try {
            String s = ctx.getSharedPreferences(NoteSync.PREFS, Context.MODE_PRIVATE).getString("widget_items", null);
            if (s == null) return Tr.t("Abre a app uma vez para carregar as tarefas.");
            JSONArray a = new JSONArray(s);
            if (a.length() == 0) return Tr.t("Sem tarefas com data. Toca em + para criar.");
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < a.length(); i++) {
                JSONObject o = a.getJSONObject(i);
                if (sb.length() > 0) sb.append('\n');
                sb.append(when(o.optLong("t"))).append("  ").append(o.optString("title", Tr.t("(sem título)")));
            }
            return sb;
        } catch (Exception e) {
            return Tr.t("Sem dados.");
        }
    }

    private static String when(long t) {
        Calendar c = Calendar.getInstance(), now = Calendar.getInstance();
        c.setTimeInMillis(t);
        String hm = new SimpleDateFormat("HH:mm", Locale.ROOT).format(new Date(t));
        int dd = c.get(Calendar.DAY_OF_YEAR) - now.get(Calendar.DAY_OF_YEAR) + 365 * (c.get(Calendar.YEAR) - now.get(Calendar.YEAR));
        if (dd == 0) return "Hoje " + hm;
        if (dd == 1) return Tr.t("Amanhã ") + hm;
        return new SimpleDateFormat("dd/MM HH:mm", Locale.ROOT).format(new Date(t));
    }
}
