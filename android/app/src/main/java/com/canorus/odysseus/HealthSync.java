package com.canorus.odysseus;

import android.content.Context;
import android.health.connect.AggregateRecordsRequest;
import android.health.connect.AggregateRecordsResponse;
import android.health.connect.HealthConnectException;
import android.health.connect.HealthConnectManager;
import android.health.connect.ReadRecordsRequestUsingFilters;
import android.health.connect.ReadRecordsResponse;
import android.health.connect.TimeRangeFilter;
import android.health.connect.datatypes.ActiveCaloriesBurnedRecord;
import android.health.connect.datatypes.AggregationType;
import android.health.connect.datatypes.ExerciseSessionRecord;
import android.health.connect.datatypes.HeartRateRecord;
import android.health.connect.datatypes.OxygenSaturationRecord;
import android.health.connect.datatypes.RestingHeartRateRecord;
import android.health.connect.datatypes.SleepSessionRecord;
import android.health.connect.datatypes.StepsRecord;
import android.health.connect.datatypes.units.Energy;
import android.os.Build;
import android.os.OutcomeReceiver;
import android.webkit.CookieManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Reads the watch data that the Nothing X app writes to Health Connect (Android 14+) and sends it to the Odysseus Gym. */
class HealthSync {
    static final String PERM_BG = "android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND";
    static final String PERM_SPO2 = "android.permission.health.READ_OXYGEN_SATURATION";
    /** Asked from the user; SpO2 is optional (not required by hasPerm) so older grants keep working. */
    static final String[] PERMS_ASK = {
        "android.permission.health.READ_HEART_RATE",
        "android.permission.health.READ_RESTING_HEART_RATE",
        "android.permission.health.READ_STEPS",
        "android.permission.health.READ_ACTIVE_CALORIES_BURNED",
        "android.permission.health.READ_EXERCISE",
        "android.permission.health.READ_SLEEP",
        PERM_SPO2,
        PERM_BG
    };
    static final String[] PERMS = {
        "android.permission.health.READ_HEART_RATE",
        "android.permission.health.READ_RESTING_HEART_RATE",
        "android.permission.health.READ_STEPS",
        "android.permission.health.READ_ACTIVE_CALORIES_BURNED",
        "android.permission.health.READ_EXERCISE",
        "android.permission.health.READ_SLEEP"
    };

    static boolean supported() { return Build.VERSION.SDK_INT >= 34; }

    static boolean hasPerm(Context c) {
        if (!supported()) return false;
        for (String p : PERMS) if (c.checkSelfPermission(p) != android.content.pm.PackageManager.PERMISSION_GRANTED) return false;
        return true;
    }

    private static <T> T await(CountDownLatch l, AtomicReference<T> out, AtomicReference<Exception> err) throws Exception {
        if (!l.await(25, TimeUnit.SECONDS)) throw new Exception("timeout");
        if (err.get() != null) throw err.get();
        return out.get();
    }

    static volatile String lastErr = "";
    /** Package names of the apps that wrote the data we read (Samsung Health, Garmin Connect, Nothing X...). */
    static final java.util.Set<String> origins = java.util.concurrent.ConcurrentHashMap.newKeySet();

    private static <T> T agg(HealthConnectManager m, AggregationType<T> type, TimeRangeFilter f) {
        try {
            AggregateRecordsRequest<T> req = new AggregateRecordsRequest.Builder<T>(f).addAggregationType(type).build();
            CountDownLatch l = new CountDownLatch(1);
            AtomicReference<AggregateRecordsResponse<T>> out = new AtomicReference<>();
            AtomicReference<Exception> err = new AtomicReference<>();
            m.aggregate(req, Runnable::run, new OutcomeReceiver<AggregateRecordsResponse<T>, HealthConnectException>() {
                public void onResult(AggregateRecordsResponse<T> r) { out.set(r); l.countDown(); }
                public void onError(HealthConnectException e) { err.set(e); l.countDown(); }
            });
            AggregateRecordsResponse<T> r = await(l, out, err);
            if (r == null) return null;
            try { for (android.health.connect.datatypes.DataOrigin o : r.getDataOrigins(type)) origins.add(o.getPackageName()); } catch (Exception ignored) { }
            return r.get(type);
        } catch (Exception e) { lastErr = String.valueOf(e.getMessage()); return null; }
    }

    /** Average and minimum SpO2 (%) of the records in the range; {} when none / no permission. */
    private static double[] spo2(Context ctx, HealthConnectManager m, TimeRangeFilter f) {
        try {
            if (ctx.checkSelfPermission(PERM_SPO2) != android.content.pm.PackageManager.PERMISSION_GRANTED) return null;
            ReadRecordsRequestUsingFilters<OxygenSaturationRecord> rq = new ReadRecordsRequestUsingFilters.Builder<>(OxygenSaturationRecord.class).setTimeRangeFilter(f).build();
            CountDownLatch l = new CountDownLatch(1);
            AtomicReference<ReadRecordsResponse<OxygenSaturationRecord>> out = new AtomicReference<>();
            AtomicReference<Exception> err = new AtomicReference<>();
            m.readRecords(rq, Runnable::run, new OutcomeReceiver<ReadRecordsResponse<OxygenSaturationRecord>, HealthConnectException>() {
                public void onResult(ReadRecordsResponse<OxygenSaturationRecord> r) { out.set(r); l.countDown(); }
                public void onError(HealthConnectException e) { err.set(e); l.countDown(); }
            });
            ReadRecordsResponse<OxygenSaturationRecord> r = await(l, out, err);
            double sum = 0, min = 101; int n = 0;
            for (OxygenSaturationRecord o : r.getRecords()) {
                double v = o.getPercentage().getValue();
                if (v <= 0 || v > 100) continue;
                sum += v; n++; if (v < min) min = v;
            }
            return n == 0 ? null : new double[]{sum / n, min};
        } catch (Exception e) { return null; }
    }

    private static TimeRangeFilter range(Instant a, Instant b) {
        return new android.health.connect.TimeInstantRangeFilter.Builder().setStartTime(a).setEndTime(b).build();
    }

    private static void put(JSONObject o, String k, Number n) throws Exception { if (n != null) o.put(k, n.doubleValue()); }

    static String typeName(int t) {
        switch (t) {
            case 79: return "Caminhada"; case 56: return "Corrida"; case 8: return "Ciclismo";
            case 74: return "Treino de força"; case 70: return "Treino intervalado (HIIT)"; case 37: return "Ginásio";
            case 83: return "Natação"; case 81: return "Yoga"; case 35: return "Elíptica"; case 13: return "Aeróbica";
            default: return "Treino";
        }
    }

    /** Reads the last 7 days + the last 10 sessions and posts them to the server. Needs the background thread. */
    static String result = "";
    static boolean sync(Context ctx) {
        result = "";
        if (!supported()) { result = "Precisa do Android 14 ou superior."; return false; }
        try {
            origins.clear();
            String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
            if (cookie == null || cookie.isEmpty()) { result = "Sem sessão iniciada no Odysseus."; return false; }
            HealthConnectManager m = ctx.getSystemService(HealthConnectManager.class);
            if (m == null) { result = "Health Connect indisponível neste telemóvel."; return false; }
            ZoneId z = ZoneId.systemDefault();
            JSONArray days = new JSONArray();
            for (int i = 0; i < 7; i++) {
                LocalDate d = LocalDate.now(z).minusDays(i);
                Instant a = d.atStartOfDay(z).toInstant();
                Instant b = i == 0 ? Instant.now() : d.plusDays(1).atStartOfDay(z).toInstant();
                TimeRangeFilter f = range(a, b);
                JSONObject o = new JSONObject();
                o.put("date", d.toString());
                put(o, "steps", agg(m, StepsRecord.STEPS_COUNT_TOTAL, f));
                Energy e = agg(m, ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL, f);
                if (e != null) o.put("kcal", e.getInCalories() / 1000.0);
                put(o, "hr_min", agg(m, HeartRateRecord.BPM_MIN, f));
                put(o, "hr_avg", agg(m, HeartRateRecord.BPM_AVG, f));
                put(o, "hr_max", agg(m, HeartRateRecord.BPM_MAX, f));
                put(o, "hr_rest", agg(m, RestingHeartRateRecord.BPM_AVG, f));
                double[] ox = spo2(ctx, m, f);
                if (ox != null) { o.put("spo2_avg", ox[0]); o.put("spo2_min", ox[1]); }
                Long sl = agg(m, SleepSessionRecord.SLEEP_DURATION_TOTAL, f);
                if (sl != null) o.put("sleep_min", sl / 60000.0);
                if (o.length() > 1) days.put(o);
            }
            JSONArray works = new JSONArray();
            try {
                ReadRecordsRequestUsingFilters<ExerciseSessionRecord> rq = new ReadRecordsRequestUsingFilters.Builder<>(ExerciseSessionRecord.class)
                        .setTimeRangeFilter(range(Instant.now().minusSeconds(7L * 86400), Instant.now())).build();
                CountDownLatch l = new CountDownLatch(1);
                AtomicReference<ReadRecordsResponse<ExerciseSessionRecord>> out = new AtomicReference<>();
                AtomicReference<Exception> err = new AtomicReference<>();
                m.readRecords(rq, Runnable::run, new OutcomeReceiver<ReadRecordsResponse<ExerciseSessionRecord>, HealthConnectException>() {
                    public void onResult(ReadRecordsResponse<ExerciseSessionRecord> r) { out.set(r); l.countDown(); }
                    public void onError(HealthConnectException e) { err.set(e); l.countDown(); }
                });
                ReadRecordsResponse<ExerciseSessionRecord> r = await(l, out, err);
                java.util.List<ExerciseSessionRecord> recs = r.getRecords();
                for (int i = Math.max(0, recs.size() - 10); i < recs.size(); i++) {
                    ExerciseSessionRecord s = recs.get(i);
                    try { origins.add(s.getMetadata().getDataOrigin().getPackageName()); } catch (Exception ignored) { }
                    TimeRangeFilter f = range(s.getStartTime(), s.getEndTime());
                    JSONObject w = new JSONObject();
                    w.put("start", s.getStartTime().toString());
                    w.put("end", s.getEndTime().toString());
                    w.put("type", typeName(s.getExerciseType()));
                    put(w, "hr_avg", agg(m, HeartRateRecord.BPM_AVG, f));
                    put(w, "hr_max", agg(m, HeartRateRecord.BPM_MAX, f));
                    Energy e = agg(m, ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL, f);
                    if (e != null) w.put("kcal", e.getInCalories() / 1000.0);
                    works.put(w);
                }
            } catch (Exception ignored) { }
            int granted = 0;
            for (String p : PERMS_ASK) if (ctx.checkSelfPermission(p) == android.content.pm.PackageManager.PERMISSION_GRANTED) granted++;
            String diag = "perms " + granted + "/" + PERMS_ASK.length + ", days " + days.length() + ", workouts " + works.length()
                    + (lastErr.isEmpty() ? "" : ", err: " + lastErr) + ", sdk " + Build.VERSION.SDK_INT;
            JSONObject body = new JSONObject().put("days", days).put("workouts", works).put("diag", diag).put("sources", new JSONArray(origins));
            int rc = Http.request("POST", NoteSync.SITE + "/finance/health/sync", cookie,
                    "application/json", body.toString(), 10000, 20000).code;
            result = rc == 200 ? "Enviado ao Gym: " + diag : "Servidor respondeu " + rc;
            return rc == 200;
        } catch (Exception e) { result = "Erro: " + e.getClass().getSimpleName() + " " + String.valueOf(e.getMessage()); return false; }
    }
}
