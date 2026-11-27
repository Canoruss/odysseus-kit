package com.canorus.odysseus;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

/** Shown by Health Connect ("Privacy policy" link) so the permissions can be granted. */
public class HealthRationaleActivity extends Activity {
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        TextView t = new TextView(this);
        t.setPadding(48, 96, 48, 48);
        t.setTextSize(16);
        t.setText(L.t("O Odysseus lê do Health Connect os batimentos, passos, calorias, sono, oxigénio no sangue e treinos do teu relógio e envia-os só para o teu Odysseus (aba Gym). Não partilha com terceiros. Podes retirar a permissão a qualquer momento nas definições do Health Connect."));
        setContentView(t);
    }
}
