package org.odysseuskit.app;

import android.content.Context;
import android.content.SharedPreferences;

/** User-facing switches of the app (edited in SettingsActivity). */
final class AppSettings {
    private AppSettings() { }

    static final String PREFS = "app_settings";

    static SharedPreferences sp(Context c) {
        return c.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** Idioma da app: escolhido nas definicoes; por omissao o do telemovel (pt ou en). */
    static String language(Context c) {
        String l = sp(c).getString("lang", null);
        if (l != null) return l;
        return "pt".equals(java.util.Locale.getDefault().getLanguage()) ? "pt" : "en";
    }
    static String serverUrl(Context c) { return sp(c).getString("server_url", null); }
    static boolean setupDone(Context c) { return sp(c).getBoolean("setup_done", false) && serverUrl(c) != null; }
    /** Aplica o endereco do servidor escolhido no primeiro ecra. */
    static void applyServer(Context c) {
        String u = serverUrl(c);
        if (u != null) { NoteSync.SITE = u; Updater.BASE = u + "/odysseus-app/"; }
    }

    static boolean chatNotifications(Context c) { return sp(c).getBoolean("notify_chat", true); }
    static boolean taskNotifications(Context c) { return sp(c).getBoolean("notify_tasks", true); }
    static boolean reminders(Context c) { return sp(c).getBoolean("notify_reminders", true); }
    /** Silêncio noturno: das 18:30 às 09:30 os avisos normais chegam sem som nem vibração (alarmes não são afetados). */
    static boolean quiet(Context c) {
        if (!sp(c).getBoolean("quiet_hours", true)) return false;
        java.util.Calendar k = java.util.Calendar.getInstance(java.util.TimeZone.getDefault());
        int m = k.get(java.util.Calendar.HOUR_OF_DAY) * 60 + k.get(java.util.Calendar.MINUTE);
        return m >= 18 * 60 + 30 || m < 9 * 60 + 30;
    }
    static boolean morningSummary(Context c) { return sp(c).getBoolean("morning_summary", true); }
    static boolean calendarPush(Context c) { return sp(c).getBoolean("calendar_push", true); }
    /** Lembretes de saúde (glicose, insulina, consulta) tocam mesmo no silêncio noturno. */
    static boolean healthTitle(String t) {
        String l = t == null ? "" : t.toLowerCase(java.util.Locale.ROOT);
        return l.contains("glicose") || l.contains("insulina") || l.contains("consulta") || l.contains("hipoglic")
                || l.contains("glucose") || l.contains("insulin") || l.contains("appointment") || l.contains("hypo");
    }
    static boolean alarms(Context c) { return sp(c).getBoolean("alarms", true); }
    static boolean fileNotifications(Context c) { return sp(c).getBoolean("notify_files", true); }
    static boolean calendarSync(Context c) { return sp(c).getBoolean("calendar_sync", true); }
    static boolean lockEnabled(Context c) { return sp(c).getBoolean("lock", true); }
    static int lockMinutes(Context c) { return sp(c).getInt("lock_minutes", 5); }
    static int snoozeMinutes(Context c) { return sp(c).getInt("snooze_minutes", 10); }

    /** Words (comma separated) that turn a reminder into a ringing alarm. */
    static String alarmWords(Context c) { return sp(c).getString("alarm_words", "alarme, alarm, ⏰"); }

    static boolean isAlarmTitle(Context c, String title) {
        if (!alarms(c) || title == null) return false;
        String t = title.toLowerCase();
        for (String w : alarmWords(c).split(",")) {
            String x = w.trim().toLowerCase();
            if (!x.isEmpty() && t.contains(x)) return true;
        }
        return false;
    }
}
