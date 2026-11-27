package com.canorus.odysseus;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.VibrationEffect;
import android.os.Vibrator;

import androidx.core.app.NotificationCompat;

/** Rings like a real alarm (looping alarm sound + vibration) until the user taps "Desligar". */
public class AlarmService extends Service {
    static final String ACTION_STOP = "com.canorus.odysseus.STOP_ALARM";
    static final String CH = Channels.ALARM_RING;
    static final String ACTION_SNOOZE = "com.canorus.odysseus.SNOOZE_ALARM";
    private String curId, curTitle, curBody;
    private MediaPlayer player;
    private PowerManager.WakeLock wl;
    private final Handler h = new Handler(Looper.getMainLooper());
    private final Runnable timeout = this::stopRinging;

    @Override public IBinder onBind(Intent i) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) { stopRinging(); return START_NOT_STICKY; }
        if (intent != null && ACTION_SNOOZE.equals(intent.getAction())) {
            if (curId != null) NoteSync.snooze(this, curId, curTitle, curBody, AppSettings.snoozeMinutes(this));
            stopRinging();
            return START_NOT_STICKY;
        }
        String title = intent == null ? null : intent.getStringExtra("title");
        String body = intent == null ? null : intent.getStringExtra("body");
        curId = intent == null ? null : intent.getStringExtra("id");
        curTitle = title;
        curBody = body;
        Channels.ensureAll(this);
        PendingIntent stop = PendingIntent.getService(this, 10, new Intent(this, AlarmService.class).setAction(ACTION_STOP),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent open = PendingIntent.getActivity(this, 11, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE);
        Notification n = new NotificationCompat.Builder(this, CH)
                .setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
                .setContentTitle(title == null || title.isEmpty() ? L.t("Alarme") : title)
                .setContentText(body == null || body.isEmpty() ? L.t("Toca para desligar") : body)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setOngoing(true)
                .setFullScreenIntent(open, true)
                .setContentIntent(stop)
                .addAction(android.R.drawable.ic_menu_close_clear_cancel, L.t("Desligar"), stop)
                .addAction(0, L.t("Adiar ") + AppSettings.snoozeMinutes(this) + " min", PendingIntent.getService(this, 12,
                        new Intent(this, AlarmService.class).setAction(ACTION_SNOOZE),
                        PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT))
                .build();
        try {
            if (Build.VERSION.SDK_INT >= 34) startForeground(3, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            else startForeground(3, n);
        } catch (Exception e) { stopSelf(); return START_NOT_STICKY; }
        startRinging();
        h.removeCallbacks(timeout);
        h.postDelayed(timeout, 10 * 60_000L); // safety stop after 10 min
        return START_NOT_STICKY;
    }

    private void startRinging() {
        if (player != null) return;
        try {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "odysseus:alarm");
            wl.acquire(11 * 60_000L);
            Uri uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
            if (uri == null) uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
            player = new MediaPlayer();
            player.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build());
            player.setDataSource(this, uri);
            player.setLooping(true);
            player.prepare();
            player.start();
        } catch (Exception ignored) { }
        try {
            Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
            long[] pat = {0, 700, 500};
            if (Build.VERSION.SDK_INT >= 26) v.vibrate(VibrationEffect.createWaveform(pat, 0));
            else v.vibrate(pat, 0);
        } catch (Exception ignored) { }
    }

    private void stopRinging() {
        h.removeCallbacks(timeout);
        try { if (player != null) { player.stop(); player.release(); } } catch (Exception ignored) { }
        player = null;
        try { ((Vibrator) getSystemService(Context.VIBRATOR_SERVICE)).cancel(); } catch (Exception ignored) { }
        try { if (wl != null && wl.isHeld()) wl.release(); } catch (Exception ignored) { }
        stopForeground(true);
        stopSelf();
    }

    @Override public void onDestroy() { stopRinging(); super.onDestroy(); }
}
