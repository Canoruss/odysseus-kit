package com.canorus.odysseus;

import android.content.Context;
import android.content.SharedPreferences;
import java.util.Calendar;
import java.util.Locale;
import java.util.TimeZone;

/** User-facing switches of the app (edited in SettingsActivity). */
final class AppSettings {
    private AppSettings() { }
    static { System.loadLibrary("odysseus_voice"); }
    private static native boolean nativeQuiet(boolean enabled, int minutes);
    private static native boolean nativeHealthTitle(String title);

    static final String PREFS = "app_settings";

    static SharedPreferences sp(Context c) {
        return c.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static String serverUrl(Context c) { return sp(c).getString("server_url", null); }
    static boolean setupDone(Context c) { return serverUrl(c) != null; }
    static void applyServer(Context c) {
        String u = serverUrl(c);
        if (u != null) { NoteSync.SITE = u; Updater.BASE = u + "/odysseus-app/"; }
    }

    // ---- Configuração e Autenticação do Agente Android (/agent/step SSE) ----
    static String agentEndpoint(Context c) {
        String ep = sp(c).getString("agent_endpoint", "/agent/step").trim();
        if (ep.isEmpty() || "/api/agent/android".equals(ep)) {
            ep = "/agent/step";
            sp(c).edit().putString("agent_endpoint", ep).apply();
        }
        return ep;
    }

    static String agentToken(Context c) {
        return sp(c).getString("agent_token", "").trim();
    }

    static String agentAuthHeader(Context c) {
        String h = sp(c).getString("agent_auth_header", "Authorization").trim();
        return h.isEmpty() ? "Authorization" : h;
    }

    static String formatAgentAuthValue(Context c) {
        String tok = agentToken(c);
        if (tok.isEmpty()) return "";
        String hdr = agentAuthHeader(c);
        if ("Authorization".equalsIgnoreCase(hdr)
                && !tok.regionMatches(true, 0, "Bearer ", 0, 7)
                && !tok.regionMatches(true, 0, "Token ", 0, 6)) {
            return "Bearer " + tok;
        }
        return tok;
    }

    static boolean agentConfirmAllSteps(Context c) {
        SharedPreferences p = sp(c);
        if (!p.getBoolean("agent_routine_policy_v2", false)) {
            p.edit()
                    .putBoolean("agent_confirm_all_steps", false)
                    .putBoolean("agent_routine_policy_v2", true)
                    .apply();
        }
        return p.getBoolean("agent_confirm_all_steps", false);
    }

    static boolean agentConfirmCritical(Context c) {
        return sp(c).getBoolean("agent_confirm_critical", true);
    }

    static boolean chatNotifications(Context c) { return sp(c).getBoolean("notify_chat", true); }
    static boolean taskNotifications(Context c) { return sp(c).getBoolean("notify_tasks", true); }
    static boolean reminders(Context c) { return sp(c).getBoolean("notify_reminders", true); }

    /**
     * Modo poupança de bateria (predefinido: true).
     * Quando ativo, a app usa apenas WorkManager (sem serviço permanente a acordar o CPU de 20 em 20s),
     * mantendo o serviço ativo apenas enquanto uma resposta de chat estiver a ser gerada em tempo real.
     */
    static boolean batterySaver(Context c) { return sp(c).getBoolean("battery_saver", true); }

    /** Silêncio noturno: das 18:30 às 09:30 (hora local do dispositivo) sem som nem vibração. */
    static boolean quiet(Context c) {
        if (!sp(c).getBoolean("quiet_hours", true)) return false;
        Calendar k = Calendar.getInstance(TimeZone.getDefault());
        int m = k.get(Calendar.HOUR_OF_DAY) * 60 + k.get(Calendar.MINUTE);
        return nativeQuiet(true, m);
    }

    static boolean morningSummary(Context c) { return sp(c).getBoolean("morning_summary", true); }
    static boolean calendarPush(Context c) { return sp(c).getBoolean("calendar_push", true); }

    /** Lembretes de saúde (glicose, insulina, consulta) tocam mesmo no silêncio noturno. */
    static boolean healthTitle(String t) {
        return nativeHealthTitle(t);
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
        String t = title.toLowerCase(Locale.ROOT);
        for (String w : alarmWords(c).split(",")) {
            String x = w.trim().toLowerCase(Locale.ROOT);
            if (!x.isEmpty() && t.contains(x)) return true;
        }
        return false;
    }
}
