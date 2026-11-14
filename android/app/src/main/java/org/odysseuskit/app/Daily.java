package org.odysseuskit.app;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

import androidx.core.app.NotificationCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Calendar;
import java.util.Locale;
import java.util.Set;

/** Tr.t("Resumo da manhã"): uma notificação por dia, a partir das 08:00, com as tarefas, eventos e consultas de hoje. */
class Daily {
    static void tick(Context ctx) {
        try {
            if (!AppSettings.morningSummary(ctx)) return;
            Calendar now = Calendar.getInstance();
            int h = now.get(Calendar.HOUR_OF_DAY);
            SharedPreferences sp = ctx.getSharedPreferences(NoteSync.PREFS, Context.MODE_PRIVATE);
            if ((h < 8 || h >= 12) && !sp.getBoolean("summary_force", false)) return;
            String today = String.format(Locale.ROOT, "%04d-%02d-%02d", now.get(Calendar.YEAR), now.get(Calendar.MONTH) + 1, now.get(Calendar.DAY_OF_MONTH));
            if (today.equals(sp.getString("summary_date", ""))) return;
            NoteSync.runSync(ctx);                       // dados do dia atualizados (tarefas e eventos)
            sp.edit().putString("summary_date", today).apply();
            StringBuilder b = new StringBuilder();
            int n = 0;
            n += add(b, sp.getString("today_items", "[]"), "");
            n += add(b, sp.getString("today_events", "[]"), "📅 ");
            Set<String> ap = ctx.getSharedPreferences(SnsListener.PREFS, Context.MODE_PRIVATE).getStringSet(SnsListener.KEY, new java.util.HashSet<>());
            Calendar a0 = (Calendar) now.clone(); a0.set(Calendar.HOUR_OF_DAY, 0); a0.set(Calendar.MINUTE, 0); a0.set(Calendar.SECOND, 0);
            long s = a0.getTimeInMillis(), e = s + 86400000L;
            for (String x : ap) {
                try {
                    long t = Long.parseLong(x);
                    if (t >= s && t < e) { Calendar c = Calendar.getInstance(); c.setTimeInMillis(t);
                        b.append(String.format(Locale.ROOT, Tr.t("🩺 Consulta às %02d:%02d\n"), c.get(Calendar.HOUR_OF_DAY), c.get(Calendar.MINUTE))); n++; }
                } catch (NumberFormatException ignored) { }
            }
            if (n == 0) return;
            NoteSync.ensureChannel(ctx);
            PendingIntent pi = PendingIntent.getActivity(ctx, 77, new Intent(ctx, MainActivity.class)
                    .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP), PendingIntent.FLAG_IMMUTABLE);
            String text = b.toString().trim();
            Notification nf = new NotificationCompat.Builder(ctx, NoteSync.CHANNEL)
                    .setSmallIcon(android.R.drawable.ic_popup_reminder)
                    .setContentTitle(Tr.t("Bom dia! O teu dia: ") + n + (n == 1 ? " item" : " itens"))
                    .setContentText(text.split("\n")[0])
                    .setStyle(new NotificationCompat.BigTextStyle().bigText(text))
                    .setPriority(NotificationCompat.PRIORITY_HIGH).setAutoCancel(true).setContentIntent(pi).build();
            ctx.getSystemService(NotificationManager.class).notify(7700, nf);
        } catch (Exception | Error ignored) { }
    }

    private static int add(StringBuilder b, String json, String icon) throws Exception {
        JSONArray a = new JSONArray(json);
        int n = 0;
        for (int i = 0; i < a.length() && i < 12; i++) {
            JSONObject o = a.getJSONObject(i);
            Calendar c = Calendar.getInstance(); c.setTimeInMillis(o.optLong("t"));
            boolean allDay = o.optBoolean("allday", false);
            b.append(icon).append(allDay ? "" : String.format(Locale.ROOT, "%02d:%02d ", c.get(Calendar.HOUR_OF_DAY), c.get(Calendar.MINUTE)))
                    .append(o.optString("title", "")).append('\n');
            n++;
        }
        return n;
    }
}
