package org.odysseuskit.app;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;

import java.text.Normalizer;
import java.util.Calendar;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Lê só as notificações do MIN.SAUDE (SNS24), extrai a data e a hora da consulta
 * e agenda um aviso no dia anterior (09:00) e um alarme 1 hora antes.
 * Tudo fica no telemóvel: não há envio para o servidor e o texto da mensagem não é guardado.
 */
public class SnsListener extends NotificationListenerService {
    static final String PREFS = "sns_appts";
    static final String KEY = "epochs";
    private static final Pattern DATE = Pattern.compile("\\b(\\d{1,2})[/.-](\\d{1,2})[/.-](\\d{4}|\\d{2})\\b");
    private static final Pattern TIME = Pattern.compile("\\b(\\d{1,2})(?::|h)(\\d{2})\\b");

    @Override
    public void onListenerConnected() {
        super.onListenerConnected();
        scheduleAll(this);
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        try {
            if (sbn == null || sbn.getPackageName() == null || sbn.getPackageName().equals(getPackageName())) return;
            Notification n = sbn.getNotification();
            if (n == null || n.extras == null) return;
            CharSequence t = n.extras.getCharSequence(Notification.EXTRA_TITLE);
            CharSequence big = n.extras.getCharSequence(Notification.EXTRA_BIG_TEXT);
            CharSequence txt = n.extras.getCharSequence(Notification.EXTRA_TEXT);
            String title = t == null ? "" : t.toString();
            String body = big != null ? big.toString() : (txt == null ? "" : txt.toString());
            if (!isHealthSender(title) && !isHealthBody(body)) return;
            long epoch = parseAppointment(body);
            android.util.Log.i("OdySns", "mensagem de saude: consulta=" + epoch);
            if (epoch <= 0) return;
            if (epoch < System.currentTimeMillis() || ignored(this, epoch)) return;

            SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
            Set<String> set = new HashSet<>(sp.getStringSet(KEY, new HashSet<>()));
            if (!set.add(String.valueOf(epoch))) return;
            sp.edit().putStringSet(KEY, set).apply();
            scheduleAll(this);
            notifyPlain(this, "Consulta registada", label(epoch, false), Math.abs(("reg" + epoch).hashCode()));
        } catch (Exception e) {
            android.util.Log.w("OdySns", "falha a ler a consulta: " + e);   // sem o texto da mensagem
        }
    }

    static boolean isHealthSender(String s) {
        String n = Normalizer.normalize(s == null ? "" : s, Normalizer.Form.NFD)
                .replaceAll("\\p{M}", "").toUpperCase();
        return n.contains("SAUDE") || n.contains("SNS24") || n.contains("SNS 24");
    }

    /** Mensagens do centro de saúde começam por "Centro Saude:" mesmo quando o remetente é um número. */
    static boolean isHealthBody(String s) {
        String n = Normalizer.normalize(s == null ? "" : s, Normalizer.Form.NFD)
                .replaceAll("\\p{M}", "").toUpperCase().trim();
        return n.startsWith("CENTRO SAUDE") || n.startsWith("CENTRO DE SAUDE") || n.startsWith("SNS24") || n.startsWith("SNS 24");
    }

    private static final Pattern DAYMONTH = Pattern.compile("(?i)\\bdia\\s+(\\d{1,2})[/.-](\\d{1,2})\\b(?![/.-]\\d)");
    private static final Pattern NAMED = Pattern.compile("\\b(\\d{1,2})[./\\s-]+(?:de\\s+)?([A-Za-z\u00C0-\u00FF]{3,9})\\.?(?:[./\\s-]+(?:de\\s+)?(\\d{4}))?\\b");
    private static final String[] MONTHS = {"jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"};

    /** Devolve o instante (ms) da consulta ou 0 se a mensagem não tiver data e hora. */
    static long parseAppointment(String body) { return parseAppointment(body, System.currentTimeMillis()); }

    /** ref = momento em que a mensagem foi recebida (data sem ano resolve-se a partir dele). */
    static long parseAppointment(String body, long ref) {
        int day = -1, month = -1, year = -1;
        Matcher d = DATE.matcher(body);
        Matcher nm = NAMED.matcher(body);
        Matcher tm = TIME.matcher(body);
        if (!tm.find()) return 0;
        if (d.find()) {
            day = Integer.parseInt(d.group(1));
            month = Integer.parseInt(d.group(2));
            year = Integer.parseInt(d.group(3));
            if (year < 100) year += 2000;
        } else {
            month = 0;
            while (month == 0 && nm.find()) {
                String name = Normalizer.normalize(nm.group(2), Normalizer.Form.NFD).replaceAll("\\p{M}", "").toLowerCase();
                for (int i = 0; i < MONTHS.length; i++) if (name.startsWith(MONTHS[i])) { month = i + 1; break; }
                if (month == 0) continue;
                day = Integer.parseInt(nm.group(1));
                year = nm.group(3) == null ? -1 : Integer.parseInt(nm.group(3));
            }
            if (month == 0) {
                Matcher dm = DAYMONTH.matcher(body);   // Tr.t("dia 22/09") sem ano
                if (!dm.find()) return 0;
                day = Integer.parseInt(dm.group(1));
                month = Integer.parseInt(dm.group(2));
                year = -1;
            }
        }
        int hour = Integer.parseInt(tm.group(1));
        int min = Integer.parseInt(tm.group(2));
        if (day < 1 || day > 31 || month < 1 || month > 12 || hour > 23 || min > 59) return 0;
        Calendar c = Calendar.getInstance();
        c.clear();
        if (year < 0) {
            // Sem ano: próxima ocorrência da data (este ano, ou o seguinte se já passou)
            Calendar rc = Calendar.getInstance(); rc.setTimeInMillis(ref);
            c.set(rc.get(Calendar.YEAR), month - 1, day, hour, min, 0);
            if (c.getTimeInMillis() < ref) c.add(Calendar.YEAR, 1);
            return c.getTimeInMillis();
        }
        c.set(year, month - 1, day, hour, min, 0);
        return c.getTimeInMillis();
    }


    /** Leitura única (e repetível, sem duplicar) das SMS já recebidas do centro de saúde / SNS 24. Só guarda data e hora. */
    static int scanInbox(Context ctx) {
        int added = 0;
        try {
            if (ctx.checkSelfPermission(android.Manifest.permission.READ_SMS) != android.content.pm.PackageManager.PERMISSION_GRANTED) return -1;
            SharedPreferences sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            Set<String> set = new HashSet<>(sp.getStringSet(KEY, new HashSet<>()));
            long now = System.currentTimeMillis();
            long since = now - 400L * 86400_000L;
            try (android.database.Cursor c = ctx.getContentResolver().query(android.net.Uri.parse("content://sms/inbox"),
                    new String[]{"address", "body", "date"}, "date > ?", new String[]{String.valueOf(since)}, "date DESC")) {
                while (c != null && c.moveToNext()) {
                    String addr = c.getString(0), body = c.getString(1); long date = c.getLong(2);
                    if (body == null || (!isHealthSender(addr) && !isHealthBody(body))) continue;
                    long epoch = parseAppointment(body, date);
                    if (epoch <= now || ignored(ctx, epoch)) continue;
                    if (set.add(String.valueOf(epoch))) added++;
                }
            }
            if (added > 0) {
                sp.edit().putStringSet(KEY, set).apply();
                scheduleAll(ctx);
                notifyPlain(ctx, "Consultas encontradas nas SMS", added + (added == 1 ? " consulta registada" : " consultas registadas"), 4793);
            }
        } catch (Exception e) {
            android.util.Log.w("OdySns", "falha a ler SMS: " + e);
        }
        return added;
    }

    static String label(long epoch, boolean short_) {
        Calendar c = Calendar.getInstance();
        c.setTimeInMillis(epoch);
        return String.format("%02d/%02d/%04d às %02d:%02d", c.get(Calendar.DAY_OF_MONTH),
                c.get(Calendar.MONTH) + 1, c.get(Calendar.YEAR), c.get(Calendar.HOUR_OF_DAY), c.get(Calendar.MINUTE));
    }

    static void scheduleAll(Context ctx) {
        SharedPreferences sp = ctx.getSharedPreferences(PREFS, MODE_PRIVATE);
        Set<String> set = sp.getStringSet(KEY, new HashSet<>());
        long now = System.currentTimeMillis();
        Set<String> keep = new HashSet<>();
        for (String s : set) {
            long epoch;
            try { epoch = Long.parseLong(s); } catch (NumberFormatException e) { continue; }
            if (epoch < now - 3600_000L) continue; // consulta já passou: deixa de a guardar
            keep.add(s);
            String hora = label(epoch, true).substring(label(epoch, true).indexOf("às"));
            // Dia anterior às 09:00
            Calendar d = Calendar.getInstance();
            d.setTimeInMillis(epoch);
            d.add(Calendar.DAY_OF_MONTH, -1);
            d.set(Calendar.HOUR_OF_DAY, 9);
            d.set(Calendar.MINUTE, 0);
            d.set(Calendar.SECOND, 0);
            d.set(Calendar.MILLISECOND, 0);
            if (d.getTimeInMillis() > now) {
                at(ctx, d.getTimeInMillis(), "sns-d-" + s, Tr.t("Consulta amanhã ") + hora,
                        "MIN.SAUDE: " + label(epoch, true), null);
            }
            // 1 hora antes, com alarme (⏰ no título)
            long alarm = Math.max(epoch - 3600_000L, now + 3000L);
            if (epoch > now && !sp.getBoolean("fired-" + s, false)) {
                at(ctx, alarm, "sns-a-" + s, "⏰ Consulta " + hora + (epoch - now > 3500_000L ? Tr.t(" (em 1 hora)") : ""),
                        "MIN.SAUDE: " + label(epoch, true), "fired-" + s);
            }
        }
        if (keep.size() != set.size()) {
            SharedPreferences.Editor ed = sp.edit().putStringSet(KEY, keep);
            for (String s : set) if (!keep.contains(s)) ed.remove("fired-" + s);
            ed.apply();
        }
    }

    /** Apaga uma consulta registada, cancela os avisos e impede que a leitura das SMS a volte a registar. */
    static void remove(Context ctx, String epochStr) {
        SharedPreferences sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        Set<String> set = new HashSet<>(sp.getStringSet(KEY, new HashSet<>()));
        Set<String> ign = new HashSet<>(sp.getStringSet("ignored", new HashSet<>()));
        set.remove(epochStr); ign.add(epochStr);
        sp.edit().putStringSet(KEY, set).putStringSet("ignored", ign).remove("fired-" + epochStr).apply();
        AlarmManager am = ctx.getSystemService(AlarmManager.class);
        for (String tag : new String[]{"sns-d-" + epochStr, "sns-a-" + epochStr}) {
            int code = Math.abs(tag.hashCode());
            PendingIntent pi = PendingIntent.getBroadcast(ctx, code, new Intent(ctx, Fire.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            am.cancel(pi); pi.cancel();
        }
    }

    static boolean ignored(Context ctx, long epoch) {
        return ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getStringSet("ignored", new HashSet<>()).contains(String.valueOf(epoch));
    }

    static void at(Context ctx, long t, String tag, String title, String body, String firedKey) {
        int code = Math.abs(tag.hashCode());
        Intent i = new Intent(ctx, Fire.class).putExtra("title", title).putExtra("body", body)
                .putExtra("nid", code).putExtra("fired", firedKey);
        PendingIntent pi = PendingIntent.getBroadcast(ctx, code, i,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        AlarmManager am = ctx.getSystemService(AlarmManager.class);
        try {
            am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, t, pi);
        } catch (SecurityException e) {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, t, pi);
        }
    }

    static void notifyPlain(Context ctx, String title, String body, int nid) {
        NoteSync.ensureChannel(ctx);
        Intent open = new Intent(ctx, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(ctx, 0, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification nf = new NotificationCompat.Builder(ctx, NoteSync.CHANNEL)
                .setSmallIcon(android.R.drawable.ic_popup_reminder)
                .setContentTitle(title)
                .setContentText(body)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setAutoCancel(true)
                .setContentIntent(pi)
                .build();
        try {
            ctx.getSystemService(NotificationManager.class).notify(nid, nf);
        } catch (SecurityException ignored) { }
    }

    public static class Fire extends BroadcastReceiver {
        @Override
        public void onReceive(Context ctx, Intent i) {
            String title = i.getStringExtra("title");
            String body = i.getStringExtra("body");
            int nid = i.getIntExtra("nid", 0);
            String fired = i.getStringExtra("fired");
            if (fired != null) ctx.getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean(fired, true).apply();
            if (title != null && title.startsWith("⏰")) {
                try {
                    ContextCompat.startForegroundService(ctx, new Intent(ctx, AlarmService.class)
                            .putExtra("id", "sns" + nid).putExtra("title", title).putExtra("body", body));
                    return;
                } catch (Exception ignored) { /* cai para notificação normal */ }
            }
            notifyPlain(ctx, title == null ? "Consulta" : title, body == null ? "" : body, nid);
        }
    }
}
