package org.odysseuskit.app;

import android.content.ContentResolver;
import android.content.ContentUris;
import android.content.ContentValues;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.provider.CalendarContract;
import android.provider.CalendarContract.Calendars;
import android.provider.CalendarContract.Events;

import org.json.JSONArray;
import org.json.JSONObject;

import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.Instant;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/** One-way sync Odysseus calendar -> a local "Odysseus" calendar in the Android Calendar Provider. */
class CalendarSync {
    static final String ACCOUNT = "Odysseus";

    static boolean hasPerm(Context c) {
        return c.checkSelfPermission(android.Manifest.permission.READ_CALENDAR) == PackageManager.PERMISSION_GRANTED
                && c.checkSelfPermission(android.Manifest.permission.WRITE_CALENDAR) == PackageManager.PERMISSION_GRANTED;
    }

    static Uri sa(Uri u) {
        return u.buildUpon()
                .appendQueryParameter(CalendarContract.CALLER_IS_SYNCADAPTER, "true")
                .appendQueryParameter(Calendars.ACCOUNT_NAME, ACCOUNT)
                .appendQueryParameter(Calendars.ACCOUNT_TYPE, CalendarContract.ACCOUNT_TYPE_LOCAL).build();
    }

    static long ensureCalendar(ContentResolver cr) {
        try (Cursor c = cr.query(Calendars.CONTENT_URI, new String[]{Calendars._ID},
                Calendars.ACCOUNT_NAME + "=? AND " + Calendars.ACCOUNT_TYPE + "=?",
                new String[]{ACCOUNT, CalendarContract.ACCOUNT_TYPE_LOCAL}, null)) {
            if (c != null && c.moveToFirst()) return c.getLong(0);
        }
        ContentValues v = new ContentValues();
        v.put(Calendars.ACCOUNT_NAME, ACCOUNT);
        v.put(Calendars.ACCOUNT_TYPE, CalendarContract.ACCOUNT_TYPE_LOCAL);
        v.put(Calendars.NAME, "odysseus");
        v.put(Calendars.CALENDAR_DISPLAY_NAME, "Odysseus");
        v.put(Calendars.CALENDAR_COLOR, Color.parseColor("#7C9CFF"));
        v.put(Calendars.CALENDAR_ACCESS_LEVEL, Calendars.CAL_ACCESS_OWNER);
        v.put(Calendars.OWNER_ACCOUNT, ACCOUNT);
        v.put(Calendars.VISIBLE, 1);
        v.put(Calendars.SYNC_EVENTS, 1);
        v.put(Calendars.CALENDAR_TIME_ZONE, java.util.TimeZone.getDefault().getID());
        Uri u = cr.insert(sa(Calendars.CONTENT_URI), v);
        return u == null ? -1 : ContentUris.parseId(u);
    }

    /** Remove the local "Odysseus" calendar (when sync is switched off in the settings). */
    static void removeCalendar(Context ctx) {
        if (!hasPerm(ctx)) return;
        ctx.getContentResolver().delete(sa(Calendars.CONTENT_URI),
                Calendars.ACCOUNT_NAME + "=? AND " + Calendars.ACCOUNT_TYPE + "=?",
                new String[]{ACCOUNT, CalendarContract.ACCOUNT_TYPE_LOCAL});
    }

    static long[] parse(JSONObject e) {
        String s = e.optString("dtstart"), en = e.optString("dtend");
        if (e.optBoolean("all_day", false)) {
            long a = LocalDate.parse(s.substring(0, 10)).atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli();
            long b = en.length() >= 10 ? LocalDate.parse(en.substring(0, 10)).atStartOfDay().toInstant(ZoneOffset.UTC).toEpochMilli() : a;
            if (b <= a) b = a + 86400000L;
            return new long[]{a, b};
        }
        long a = NoteSync.parseDue(s), b = NoteSync.parseDue(en);
        if (a < 0) return null;
        if (b <= a) b = a + 3600000L;
        return new long[]{a, b};
    }

    static void sync(Context ctx, String cookie) throws Exception {
        if (!hasPerm(ctx)) return;
        ContentResolver cr = ctx.getContentResolver();
        long cal = ensureCalendar(cr);
        if (cal < 0) return;
        long now = System.currentTimeMillis();
        long winStart = now - 86400000L, winEnd = now + 180L * 86400000L;
        String url = NoteSync.SITE + "/api/calendar/events?start=" + URLEncoder.encode(Instant.ofEpochMilli(winStart).toString(), "UTF-8")
                + "&end=" + URLEncoder.encode(Instant.ofEpochMilli(winEnd).toString(), "UTF-8");
        String body = NoteSync.httpGet(url, cookie);
        if (body == null) return;
        JSONArray evs = new JSONObject(body).getJSONArray("events");

        Map<String, long[]> existing = new HashMap<>(); // key -> [id, dtstart]
        Map<String, String> hashes = new HashMap<>();
        try (Cursor c = cr.query(sa(Events.CONTENT_URI), new String[]{Events._ID, Events.SYNC_DATA1, Events.SYNC_DATA2, Events.DTSTART},
                Events.CALENDAR_ID + "=?", new String[]{String.valueOf(cal)}, null)) {
            while (c != null && c.moveToNext()) {
                existing.put(c.getString(1), new long[]{c.getLong(0), c.getLong(3)});
                hashes.put(c.getString(1), c.getString(2));
            }
        }
        Set<String> seen = new HashSet<>();
        java.util.Calendar d0 = java.util.Calendar.getInstance(); d0.set(java.util.Calendar.HOUR_OF_DAY, 0); d0.set(java.util.Calendar.MINUTE, 0); d0.set(java.util.Calendar.SECOND, 0);
        long dayStart = d0.getTimeInMillis(), dayEnd = dayStart + 86400000L;
        JSONArray todayEv = new JSONArray();
        for (int i = 0; i < evs.length(); i++) {
            JSONObject e = evs.getJSONObject(i);
            long[] t;
            try { t = parse(e); } catch (Exception ex) { continue; }
            if (t == null) continue;
            boolean ad = e.optBoolean("all_day", false);
            if ((ad ? t[0] < dayEnd + 86400000L && t[0] >= dayStart - 3600_000L && Math.abs(t[0] - dayStart) < 43200000L : t[0] >= dayStart && t[0] < dayEnd))
                todayEv.put(new JSONObject().put("t", ad ? dayStart : t[0]).put("title", NoteSync.s(e, "summary", "")).put("allday", ad));
            if (NoteSync.s(e, "description", "").contains("[android:")) continue;   // veio deste telemóvel: não voltar a espelhar
            String key = e.optString("uid") + "|" + e.optString("dtstart");
            String hash = NoteSync.s(e, "summary", "") + "|" + t[0] + "|" + t[1] + "|" + NoteSync.s(e, "location", "") + "|" + NoteSync.s(e, "description", "");
            seen.add(key);
            ContentValues v = new ContentValues();
            v.put(Events.TITLE, NoteSync.s(e, "summary", Tr.t("(sem título)")));
            v.put(Events.DESCRIPTION, NoteSync.s(e, "description", ""));
            v.put(Events.EVENT_LOCATION, NoteSync.s(e, "location", ""));
            v.put(Events.DTSTART, t[0]);
            v.put(Events.DTEND, t[1]);
            boolean allDay = e.optBoolean("all_day", false);
            v.put(Events.ALL_DAY, allDay ? 1 : 0);
            v.put(Events.EVENT_TIMEZONE, allDay ? "UTC" : java.util.TimeZone.getDefault().getID());
            v.put(Events.SYNC_DATA2, hash);
            long[] ex = existing.get(key);
            if (ex == null) {
                v.put(Events.CALENDAR_ID, cal);
                v.put(Events.SYNC_DATA1, key);
                cr.insert(sa(Events.CONTENT_URI), v);
            } else if (!hash.equals(hashes.get(key))) {
                cr.update(sa(ContentUris.withAppendedId(Events.CONTENT_URI, ex[0])), v, null, null);
            }
        }
        for (Map.Entry<String, long[]> en : existing.entrySet()) {
            if (!seen.contains(en.getKey()) && en.getValue()[1] >= winStart) {
                cr.delete(sa(ContentUris.withAppendedId(Events.CONTENT_URI, en.getValue()[0])), null, null);
            }
        }
        ctx.getSharedPreferences(NoteSync.PREFS, Context.MODE_PRIVATE).edit().putString("today_events", todayEv.toString()).apply();
        try { if (AppSettings.calendarPush(ctx)) pushPhoneEvents(ctx, cookie); } catch (Exception ignored) { }
    }

    // ---------- telemóvel -> Odysseus ----------
    private static String call(String method, String url, String cookie, JSONObject body) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setRequestMethod(method);
        c.setConnectTimeout(10000); c.setReadTimeout(20000);
        c.setRequestProperty("Cookie", cookie);
        c.setRequestProperty("Content-Type", "application/json");
        if (body != null) { c.setDoOutput(true); try (java.io.OutputStream os = c.getOutputStream()) { os.write(body.toString().getBytes("UTF-8")); } }
        int code = c.getResponseCode();
        if (code != 200) return null;
        try (java.io.InputStream in = c.getInputStream()) {
            java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[4096]; int r;
            while ((r = in.read(buf)) > 0) bo.write(buf, 0, r);
            return bo.toString("UTF-8");
        }
    }

    /** Copia os eventos dos calendários do telemóvel (graváveis, visíveis, fora o "Odysseus") para o Odysseus. Só cria, atualiza e apaga o que foi criado por aqui. */
    static void pushPhoneEvents(Context ctx, String cookie) throws Exception {
        if (ctx.checkSelfPermission(android.Manifest.permission.READ_CALENDAR) != PackageManager.PERMISSION_GRANTED) return;
        ContentResolver cr = ctx.getContentResolver();
        long now = System.currentTimeMillis();
        long b0 = now - 86400000L, e0 = now + 60L * 86400000L;
        Uri.Builder ub = CalendarContract.Instances.CONTENT_URI.buildUpon();
        android.content.ContentUris.appendId(ub, b0); android.content.ContentUris.appendId(ub, e0);
        String[] proj = {CalendarContract.Instances.EVENT_ID, CalendarContract.Instances.CALENDAR_ID, CalendarContract.Instances.BEGIN, CalendarContract.Instances.END,
                CalendarContract.Instances.TITLE, CalendarContract.Instances.DESCRIPTION, CalendarContract.Instances.EVENT_LOCATION, CalendarContract.Instances.ALL_DAY,
                Calendars.ACCOUNT_NAME, Calendars.CALENDAR_ACCESS_LEVEL, Calendars.VISIBLE};
        SharedPreferences sp = ctx.getSharedPreferences("cal_push", Context.MODE_PRIVATE);
        JSONObject map = new JSONObject(sp.getString("map", "{}"));
        Set<String> present = new HashSet<>();
        int made = 0;
        try (Cursor c = cr.query(ub.build(), proj, null, null, CalendarContract.Instances.BEGIN + " ASC")) {
            while (c != null && c.moveToNext()) {
                if (ACCOUNT.equals(c.getString(8)) || c.getInt(9) < Calendars.CAL_ACCESS_CONTRIBUTOR || c.getInt(10) != 1) continue;
                String desc = c.getString(5) == null ? "" : c.getString(5);
                if (desc.contains("[android:")) continue;
                long begin = c.getLong(2), end = c.getLong(3);
                boolean ad = c.getInt(7) == 1;
                String key = c.getLong(1) + ":" + c.getLong(0) + ":" + begin;
                present.add(key);
                String title = c.getString(4) == null || c.getString(4).isEmpty() ? Tr.t("(sem título)") : c.getString(4);
                String loc = c.getString(6) == null ? "" : c.getString(6);
                String hash = title + "|" + begin + "|" + end + "|" + loc + "|" + desc;
                JSONObject body = new JSONObject().put("summary", title).put("location", loc)
                        .put("description", (desc.isEmpty() ? "" : desc + "\n") + "[android:" + key + "]").put("all_day", ad);
                if (ad) {
                    body.put("dtstart", LocalDate.ofEpochDay(begin / 86400000L).toString());
                    body.put("dtend", LocalDate.ofEpochDay(Math.max(begin, end - 1) / 86400000L).plusDays(1).toString());
                } else {
                    body.put("dtstart", Instant.ofEpochMilli(begin).toString()).put("dtend", Instant.ofEpochMilli(Math.max(end, begin + 60000L)).toString());
                }
                JSONObject ent = map.optJSONObject(key);
                if (ent == null) {
                    if (made >= 40) continue;           // no máximo 40 novos por sincronização
                    String r = call("POST", NoteSync.SITE + "/api/calendar/events", cookie, body);
                    if (r != null) { map.put(key, new JSONObject().put("uid", new JSONObject(r).optString("uid")).put("h", hash)); made++; }
                } else if (!hash.equals(ent.optString("h"))) {
                    JSONObject upd = new JSONObject(body.toString()); upd.remove("all_day");
                    call("PUT", NoteSync.SITE + "/api/calendar/events/" + ent.optString("uid"), cookie, upd);
                    ent.put("h", hash);
                }
            }
        }
        java.util.Iterator<String> it = map.keys();
        java.util.List<String> gone = new java.util.ArrayList<>();
        while (it.hasNext()) { String k = it.next(); if (!present.contains(k)) gone.add(k); }
        for (String k : gone) {
            long begin = 0; try { begin = Long.parseLong(k.substring(k.lastIndexOf(':') + 1)); } catch (Exception ignored) { }
            if (begin < b0) { map.remove(k); continue; }       // fora da janela: já passou, deixa de ser seguido
            call("DELETE", NoteSync.SITE + "/api/calendar/events/" + map.getJSONObject(k).optString("uid"), cookie, null);
            map.remove(k);
        }
        sp.edit().putString("map", map.toString()).apply();
    }
}
