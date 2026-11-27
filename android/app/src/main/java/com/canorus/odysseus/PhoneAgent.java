package com.canorus.odysseus;

import android.Manifest;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.database.Cursor;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.provider.CalendarContract;
import android.provider.ContactsContract;
import android.telephony.SmsManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;

/** Executa no telemóvel as Tool Calls decididas pelo modelo privado no servidor. */
final class PhoneAgent {
    private PhoneAgent() { }
    static { System.loadLibrary("odysseus_voice"); }
    private static native int nativeTool(String name);
    private static native JSONObject nativeDeviceAction(Context context, JSONObject args, boolean volume);
    private static native JSONObject nativeClockAction(Context context, JSONObject args, boolean alarm);

    static JSONObject execute(Context ctx, String toolName, JSONObject args) {
        JSONObject res = new JSONObject();
        try {
            switch (nativeTool(toolName)) {
                case 1:
                    return callContact(ctx, args);
                case 2:
                    return sendSms(ctx, args);
                case 3:
                    return openWhatsApp(ctx, args);
                case 4:
                    return nativeClockAction(ctx, args, true);
                case 5:
                    return nativeClockAction(ctx, args, false);
                case 6:
                    return addCalendarEvent(ctx, args);
                case 7:
                    return openApp(ctx, args);
                case 8:
                    return nativeDeviceAction(ctx, args, false);
                case 9:
                    return nativeDeviceAction(ctx, args, true);
                default:
                    return res.put("ok", false).put("error", "Ferramenta desconhecida: " + toolName);
            }
        } catch (Exception e) {
            try { res.put("ok", false).put("error", e.getMessage()); } catch (Exception ignored) { }
            return res;
        }
    }

    private static JSONObject callContact(Context ctx, JSONObject args) throws Exception {
        JSONObject res = new JSONObject();
        if (ctx.checkSelfPermission(Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
            return res.put("ok", false).put("missing_permission", Manifest.permission.CALL_PHONE);
        }
        String number = args.optString("number", "").trim();
        String name = args.optString("name", "").trim();
        boolean speaker = args.optBoolean("speaker", false);

        if (number.isEmpty()) {
            if (ctx.checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
                return res.put("ok", false).put("missing_permission", Manifest.permission.READ_CONTACTS);
            }
            List<ContactMatch> matches = findContacts(ctx, name);
            if (matches.isEmpty()) {
                return res.put("ok", false).put("error", "Nenhum contacto encontrado para: " + name);
            }
            if (matches.size() > 1) {
                JSONArray arr = new JSONArray();
                for (ContactMatch m : matches) {
                    arr.put(new JSONObject().put("name", m.name).put("number", m.number));
                }
                return res.put("ok", false).put("ambiguous", true).put("candidates", arr);
            }
            number = matches.get(0).number;
            name = matches.get(0).name;
        }

        Intent i = new Intent(Intent.ACTION_CALL, Uri.parse("tel:" + Uri.encode(number)));
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        ctx.startActivity(i);

        if (speaker) {
            new Handler(Looper.getMainLooper()).postDelayed(() -> {
                AudioManager am = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
                if (am != null) am.setSpeakerphoneOn(true);
            }, 1500);
        }
        return res.put("ok", true).put("called_name", name).put("called_number", number);
    }

    private static JSONObject sendSms(Context ctx, JSONObject args) throws Exception {
        JSONObject res = new JSONObject();
        if (ctx.checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            return res.put("ok", false).put("missing_permission", Manifest.permission.SEND_SMS);
        }
        String number = args.optString("number", "").trim();
        String name = args.optString("name", "").trim();
        String message = args.optString("message", "").trim();
        if (message.isEmpty()) return res.put("ok", false).put("error", "Mensagem vazia");

        if (number.isEmpty()) {
            List<ContactMatch> matches = findContacts(ctx, name);
            if (matches.isEmpty()) return res.put("ok", false).put("error", "Contacto não encontrado: " + name);
            if (matches.size() > 1) {
                JSONArray arr = new JSONArray();
                for (ContactMatch m : matches) arr.put(new JSONObject().put("name", m.name).put("number", m.number));
                return res.put("ok", false).put("ambiguous", true).put("candidates", arr);
            }
            number = matches.get(0).number;
            name = matches.get(0).name;
        }

        SmsManager sms = Build.VERSION.SDK_INT >= 31
                ? ctx.getSystemService(SmsManager.class)
                : SmsManager.getDefault();
        ArrayList<String> parts = sms.divideMessage(message);
        sms.sendMultipartTextMessage(number, null, parts, null, null);
        return res.put("ok", true).put("sent_to", name.isEmpty() ? number : name);
    }

    private static JSONObject openWhatsApp(Context ctx, JSONObject args) throws Exception {
        JSONObject res = new JSONObject();
        String number = args.optString("number", "").trim();
        String name = args.optString("name", "").trim();
        String message = args.optString("message", "").trim();

        if (number.isEmpty()) {
            List<ContactMatch> matches = findContacts(ctx, name);
            if (matches.isEmpty()) return res.put("ok", false).put("error", "Contacto não encontrado: " + name);
            if (matches.size() > 1) {
                JSONArray arr = new JSONArray();
                for (ContactMatch m : matches) arr.put(new JSONObject().put("name", m.name).put("number", m.number));
                return res.put("ok", false).put("ambiguous", true).put("candidates", arr);
            }
            number = matches.get(0).number;
            name = matches.get(0).name;
        }

        String digits = number.replaceAll("[^0-9+]", "");
        if (digits.startsWith("+")) digits = digits.substring(1);
        else if (digits.length() == 9) digits = "351" + digits; // Código PT por defeito

        Uri uri = Uri.parse("https://api.whatsapp.com/send?phone=" + digits + "&text=" + Uri.encode(message));
        Intent i = new Intent(Intent.ACTION_VIEW, uri).setPackage("com.whatsapp");
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        ctx.startActivity(i);
        return res.put("ok", true).put("contact", name);
    }

    private static JSONObject addCalendarEvent(Context ctx, JSONObject args) throws Exception {
        JSONObject res = new JSONObject();
        if (ctx.checkSelfPermission(Manifest.permission.WRITE_CALENDAR) != PackageManager.PERMISSION_GRANTED) {
            return res.put("ok", false).put("missing_permission", Manifest.permission.WRITE_CALENDAR);
        }
        long calId = getPrimaryCalendarId(ctx);
        if (calId == -1) return res.put("ok", false).put("error", "Nenhum calendário local encontrado");

        long startMs = args.getLong("start_ms");
        long endMs = args.optLong("end_ms", startMs + 3600_000L);
        ContentValues cv = new ContentValues();
        cv.put(CalendarContract.Events.CALENDAR_ID, calId);
        cv.put(CalendarContract.Events.TITLE, args.getString("title"));
        cv.put(CalendarContract.Events.DESCRIPTION, args.optString("description", ""));
        cv.put(CalendarContract.Events.EVENT_LOCATION, args.optString("location", ""));
        cv.put(CalendarContract.Events.DTSTART, startMs);
        cv.put(CalendarContract.Events.DTEND, endMs);
        cv.put(CalendarContract.Events.EVENT_TIMEZONE, TimeZone.getDefault().getID());
        Uri uri = ctx.getContentResolver().insert(CalendarContract.Events.CONTENT_URI, cv);
        return res.put("ok", uri != null);
    }

    private static JSONObject openApp(Context ctx, JSONObject args) throws Exception {
        String target = norm(args.getString("app_name"));
        PackageManager pm = ctx.getPackageManager();
        Intent main = new Intent(Intent.ACTION_MAIN, null).addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> apps = pm.queryIntentActivities(main, 0);
        for (ResolveInfo ri : apps) {
            String label = norm(ri.loadLabel(pm).toString());
            if (label.equals(target) || label.contains(target) || target.contains(label)) {
                Intent launch = pm.getLaunchIntentForPackage(ri.activityInfo.packageName);
                if (launch != null) {
                    launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    ctx.startActivity(launch);
                    return new JSONObject().put("ok", true).put("opened", ri.loadLabel(pm).toString());
                }
            }
        }
        return new JSONObject().put("ok", false).put("error", "App não encontrada: " + args.optString("app_name"));
    }

    // --- Auxiliares de pesquisa de contactos sem acentos ---

    private static final class ContactMatch {
        final String name, number;
        ContactMatch(String name, String number) { this.name = name; this.number = number; }
    }

    private static List<ContactMatch> findContacts(Context ctx, String query) {
        String q = norm(query);
        if (q.isEmpty()) return new ArrayList<>();
        String[] tokens = q.split("\\s+");
        Map<String, ContactMatch> unique = new LinkedHashMap<>();
        String[] proj = {
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER
        };
        try (Cursor c = ctx.getContentResolver().query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI, proj, null, null, null)) {
            while (c != null && c.moveToNext()) {
                String disp = c.getString(0);
                String num = c.getString(1);
                if (disp == null || num == null) continue;
                String nd = norm(disp);
                boolean allMatch = true;
                for (String t : tokens) {
                    if (!t.isEmpty() && !nd.contains(t)) { allMatch = false; break; }
                }
                if (allMatch) {
                    String cleanKey = disp + "|" + num.replaceAll("[^0-9+]", "");
                    unique.putIfAbsent(cleanKey, new ContactMatch(disp, num));
                }
            }
        }
        return new ArrayList<>(unique.values());
    }

    private static long getPrimaryCalendarId(Context ctx) {
        String[] proj = { CalendarContract.Calendars._ID, CalendarContract.Calendars.IS_PRIMARY };
        String sel = CalendarContract.Calendars.VISIBLE + " = 1 AND "
                + CalendarContract.Calendars.CALENDAR_ACCESS_LEVEL + " >= "
                + CalendarContract.Calendars.CAL_ACCESS_CONTRIBUTOR;
        try (Cursor c = ctx.getContentResolver().query(CalendarContract.Calendars.CONTENT_URI, proj, sel, null, null)) {
            long fallback = -1;
            while (c != null && c.moveToNext()) {
                if (fallback == -1) fallback = c.getLong(0);
                if (c.getInt(1) == 1) return c.getLong(0);
            }
            return fallback;
        }
    }

    private static String norm(String s) {
        if (s == null) return "";
        return Normalizer.normalize(s, Normalizer.Form.NFD)
                .replaceAll("\\p{InCombiningDiacriticalMarks}+", "")
                .toLowerCase(Locale.ROOT).trim();
    }
}
