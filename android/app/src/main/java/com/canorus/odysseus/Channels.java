package com.canorus.odysseus;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.media.AudioAttributes;
import android.media.RingtoneManager;
import android.os.Build;

/**
 * Registers all Android NotificationChannels once at startup (and only refreshes labels when
 * the user switches app language), eliminating repeated NotificationManager Binder IPC calls.
 */
final class Channels {
    private Channels() { }

    static final String REMINDERS = "odysseus_reminders";
    static final String ALARMS = "odysseus_alarms";
    static final String ALARM_RING = "odysseus_alarm_ring";
    static final String SYNC_FG = "odysseus_sync";
    static final String CHAT = "odysseus_chat";
    static final String FILES = "odysseus_files";
    static final String UPDATES = "updates";

    private static volatile String initializedLang = null;

    static void ensureAll(Context ctx) {
        if (Build.VERSION.SDK_INT < 26 || ctx == null) return;
        String lang = L.lang();
        if (lang.equals(initializedLang)) return;
        synchronized (Channels.class) {
            if (lang.equals(initializedLang)) return;
            NotificationManager nm = ctx.getSystemService(NotificationManager.class);
            if (nm == null) return;

            NotificationChannel rem = new NotificationChannel(
                    REMINDERS, L.t("Lembretes e tarefas"), NotificationManager.IMPORTANCE_HIGH);
            rem.setDescription(L.t("Avisos das tarefas e lembretes do Odysseus"));
            nm.createNotificationChannel(rem);

            NotificationChannel al = new NotificationChannel(
                    ALARMS, L.t("Alarmes"), NotificationManager.IMPORTANCE_HIGH);
            al.setDescription(L.t("Tarefas com 'alarme' no título tocam como alarme"));
            al.setSound(
                    RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM),
                    new AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_ALARM)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                            .build());
            al.enableVibration(true);
            al.setVibrationPattern(new long[]{0, 600, 400, 600, 400, 600});
            nm.createNotificationChannel(al);

            NotificationChannel ring = new NotificationChannel(
                    ALARM_RING, L.t("Alarme a tocar"), NotificationManager.IMPORTANCE_HIGH);
            ring.setSound(null, null);
            ring.enableVibration(false);
            nm.createNotificationChannel(ring);

            NotificationChannel syncFg = new NotificationChannel(
                    SYNC_FG, L.t("Ligação em segundo plano"), NotificationManager.IMPORTANCE_LOW);
            syncFg.setSound(null, null);
            syncFg.enableVibration(false);
            syncFg.setShowBadge(false);
            nm.createNotificationChannel(syncFg);

            NotificationChannel chat = new NotificationChannel(
                    CHAT, L.t("Respostas e tarefas concluídas"), NotificationManager.IMPORTANCE_HIGH);
            nm.createNotificationChannel(chat);

            NotificationChannel files = new NotificationChannel(
                    FILES, L.t("Ficheiros partilhados"), NotificationManager.IMPORTANCE_DEFAULT);
            nm.createNotificationChannel(files);

            NotificationChannel upd = new NotificationChannel(
                    UPDATES, L.t("Atualizações da app"), NotificationManager.IMPORTANCE_DEFAULT);
            nm.createNotificationChannel(upd);

            initializedLang = lang;
        }
    }

    static void invalidateAndRefresh(Context ctx) {
        initializedLang = null;
        ensureAll(ctx);
    }
}
