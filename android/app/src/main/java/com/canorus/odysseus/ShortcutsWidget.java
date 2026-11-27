package com.canorus.odysseus;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;

/** Home-screen widget with three quick buttons: new chat, translator, new task. */
public class ShortcutsWidget extends AppWidgetProvider {

    @Override
    public void onUpdate(Context ctx, AppWidgetManager mgr, int[] ids) {
        RemoteViews v = new RemoteViews(ctx.getPackageName(), R.layout.widget_shortcuts);
        v.setTextViewText(R.id.s_chat, L.t("💬\nNovo chat"));
        v.setTextViewText(R.id.s_translate, L.t("🌐\nTradutor"));
        v.setTextViewText(R.id.s_task, L.t("✅\nTarefa"));
        v.setTextViewText(R.id.s_voice, L.t("🎤\nFalar"));
        v.setTextViewText(R.id.s_expense, L.t("💶\nDespesa"));
        v.setOnClickPendingIntent(R.id.s_chat, activity(ctx, 30, new Intent(ctx, MainActivity.class)
                .setAction(MainActivity.ACTION_NEW_CHAT)));
        v.setOnClickPendingIntent(R.id.s_translate, activity(ctx, 31, new Intent(ctx, TranslateActivity.class)));
        v.setOnClickPendingIntent(R.id.s_task, activity(ctx, 32, new Intent(ctx, QuickTaskActivity.class)));
        v.setOnClickPendingIntent(R.id.s_voice, activity(ctx, 33, new Intent(ctx, QuickTaskActivity.class).putExtra("voice", true)));
        v.setOnClickPendingIntent(R.id.s_expense, activity(ctx, 34, new Intent(ctx, QuickExpenseActivity.class)));
        for (int id : ids) mgr.updateAppWidget(id, v);
    }

    private static PendingIntent activity(Context ctx, int req, Intent i) {
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        return PendingIntent.getActivity(ctx, req, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }
}
