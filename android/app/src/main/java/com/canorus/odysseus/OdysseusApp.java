package com.canorus.odysseus;

import android.app.Application;

public class OdysseusApp extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        L.init(this);
        AppSettings.applyServer(this);
        Channels.ensureAll(this);
    }
}
