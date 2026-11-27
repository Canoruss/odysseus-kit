package com.canorus.odysseus;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.widget.Toast;

/** Receives PackageInstaller results for the self-updater, and reopens the app after an update. */
public class InstallReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context ctx, Intent intent) {
        android.util.Log.i("OdysseusUpdater", "receiver " + intent.getAction() + " status=" + intent.getIntExtra(PackageInstaller.EXTRA_STATUS, -99));
        if (Intent.ACTION_MY_PACKAGE_REPLACED.equals(intent.getAction())) {
            Updater.notifyUpdated(ctx);
            // A atualização mata o processo: volta a ligar os avisos em segundo plano
            // sem esperar que a app seja aberta.
            try { AppSettings.applyServer(ctx); SyncService.startIfNeeded(ctx); NoteSync.schedule(ctx); NoteSync.enqueueImmediateWork(ctx); SnsListener.scheduleAll(ctx); } catch (Exception ignored) { }
            return;
        }
        int status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
        if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            Intent confirm = intent.getParcelableExtra(Intent.EXTRA_INTENT);
            if (confirm != null) {
                confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                ctx.startActivity(confirm);
            }
        } else if (status == PackageInstaller.STATUS_SUCCESS) {
            Updater.notifyUpdated(ctx); // same id as MY_PACKAGE_REPLACED, so never shown twice
        } else {
            String msg = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);
            Toast.makeText(ctx, L.t("Atualização não instalada") + (msg != null ? ": " + msg : ""), Toast.LENGTH_LONG).show();
        }
    }
}
