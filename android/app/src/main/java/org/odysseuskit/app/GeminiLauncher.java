package org.odysseuskit.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;

/** Opens the free Gemini app (images, quick questions) or gemini.google.com if it is not installed. */
public class GeminiLauncher extends Activity {
    static final String PKG = "com.google.android.apps.bard";

    static void open(android.content.Context c) {
        Intent i = c.getPackageManager().getLaunchIntentForPackage(PKG);
        if (i == null) i = new Intent(Intent.ACTION_VIEW, Uri.parse("https://gemini.google.com/app"));
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try { c.startActivity(i); } catch (Exception ignored) { }
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        open(this);
        finish();
    }
}
