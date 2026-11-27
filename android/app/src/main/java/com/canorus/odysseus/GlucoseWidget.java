package com.canorus.odysseus;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.webkit.CookieManager;
import android.widget.RemoteViews;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.DateFormat;
import java.util.Date;

public class GlucoseWidget extends AppWidgetProvider {
    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] ids) {
        render(context, ids, null, 0);
        NoteSync.enqueueImmediateWork(context);
    }

    static void refreshIfAdded(Context context) {
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        int[] ids = manager.getAppWidgetIds(new ComponentName(context, GlucoseWidget.class));
        if (ids.length == 0) return;

        String server = AppSettings.serverUrl(context);
        if (server == null || !server.regionMatches(true, 0, "https://", 0, 8)) {
            render(context, ids, null, 0);
            return;
        }

        try {
            String cookie = CookieManager.getInstance().getCookie(server + "/finance/glucose/now");
            if (cookie == null || cookie.isEmpty()) {
                render(context, ids, null, 0);
                return;
            }
            JSONObject reading = fetchReading(server, cookie);
            double value = reading.optDouble("v", Double.NaN);
            long age = reading.optLong("age", -1);
            if (!Double.isFinite(value) || value <= 0 || age < 0 || age > 30L * 24 * 60 * 60) {
                render(context, ids, null, 0);
                return;
            }
            render(context, ids, Math.round(value) + " mg/dL", System.currentTimeMillis() - age * 1000);
        } catch (Exception e) {
            render(context, ids, null, 0);
        }
    }

    private static JSONObject fetchReading(String server, String cookie) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(server + "/finance/glucose/now").openConnection();
        try {
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(10000);
            connection.setUseCaches(false);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("Cookie", cookie);
            connection.setRequestProperty("Accept", "application/json");
            if (connection.getResponseCode() != 200) throw new IllegalStateException("Glucose request failed");
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(connection.getInputStream(), StandardCharsets.UTF_8))) {
                String line = reader.readLine();
                if (line == null || line.length() > 4096) throw new IllegalStateException("Invalid reading");
                return new JSONObject(line);
            }
        } finally {
            connection.disconnect();
        }
    }

    private static void render(Context context, int[] ids, String value, long timestamp) {
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.widget_glucose);
        views.setTextViewText(R.id.glucose_value, value == null ? context.getString(R.string.glucose_no_data) : value);
        String time = timestamp == 0 ? "" : context.getString(R.string.glucose_reading) + " "
                + DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(new Date(timestamp));
        views.setTextViewText(R.id.glucose_time, time);
        Intent open = new Intent(context, MainActivity.class);
        PendingIntent pending = PendingIntent.getActivity(context, 145, open,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        views.setOnClickPendingIntent(R.id.glucose_root, pending);
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        for (int id : ids) manager.updateAppWidget(id, views);
    }
}
