package org.odysseuskit.app;

import android.app.Application;

/** Aplicação: carrega o idioma e o endereço do servidor escolhidos antes de qualquer ecrã ou serviço. */
public class App extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        Tr.init(this);
        AppSettings.applyServer(this);
    }
}
