package com.canorus.odysseus;

import android.content.Context;
import androidx.annotation.NonNull;
import androidx.work.*;
import java.util.concurrent.TimeUnit;

/** Periodic background sync of Health Connect data (30m Doze-friendly interval with BatteryNotLow). */
public class HealthWorker extends Worker {
    public HealthWorker(@NonNull Context c, @NonNull WorkerParameters p) { super(c, p); }

    @NonNull @Override public Result doWork() {
        Context c = getApplicationContext();
        AppSettings.applyServer(c);
        try {
            if (Bg.isOnline(c) && HealthSync.supported() && AppSettings.sp(c).getBoolean("health_sync", false) && HealthSync.hasPerm(c)) {
                HealthSync.sync(c);
            }
        } catch (Throwable ignored) { }
        return Result.success();
    }

    static void schedule(Context c) {
        Constraints constraints = new Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .setRequiresBatteryNotLow(true)
                .build();
        PeriodicWorkRequest r = new PeriodicWorkRequest.Builder(HealthWorker.class, 30, TimeUnit.MINUTES, 10, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 5, TimeUnit.MINUTES)
                .build();
        WorkManager.getInstance(c).enqueueUniquePeriodicWork("health_bg", ExistingPeriodicWorkPolicy.KEEP, r);
    }

    static void cancel(Context c) { WorkManager.getInstance(c).cancelUniqueWork("health_bg"); }
}
