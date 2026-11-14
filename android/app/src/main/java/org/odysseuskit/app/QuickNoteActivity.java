package org.odysseuskit.app;

import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

/** "Nova nota" (widget): guarda uma nota simples (sem data) no Odysseus. */
public class QuickNoteActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setTitle("Nova nota");
        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(pad, pad, pad, pad);
        EditText text = new EditText(this);
        text.setHint("Escreve a nota…");
        text.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        text.setMinLines(4);
        text.setGravity(Gravity.TOP);
        box.addView(text, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.END);
        Button cancel = new Button(this); cancel.setText("Cancelar"); cancel.setOnClickListener(v -> finish());
        Button save = new Button(this); save.setText(Tr.t("Guardar"));
        save.setOnClickListener(v -> {
            String t = text.getText().toString().trim();
            if (t.isEmpty()) { Toast.makeText(this, "Escreve a nota", Toast.LENGTH_SHORT).show(); return; }
            String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
            if (cookie == null || cookie.isEmpty()) { Toast.makeText(this, Tr.t("Abre o Odysseus e inicia sessão primeiro"), Toast.LENGTH_LONG).show(); return; }
            save.setEnabled(false);
            new Thread(() -> {
                int code;
                try {
                    String first = t.split("\n", 2)[0];
                    if (first.length() > 60) first = first.substring(0, 60);
                    JSONObject body = new JSONObject().put("title", first).put("content", t);
                    code = Actions.send("POST", NoteSync.SITE + "/api/notes", cookie, "application/json", body.toString());
                } catch (Exception e) { code = -1; }
                final int c = code;
                runOnUiThread(() -> {
                    if (c == 200) { Toast.makeText(this, "Nota guardada", Toast.LENGTH_SHORT).show(); finish(); }
                    else { save.setEnabled(true); Toast.makeText(this, Tr.t("Não foi possível guardar (") + c + Tr.t("). Tens o Tailscale ligado?"), Toast.LENGTH_LONG).show(); }
                });
            }).start();
        });
        actions.addView(cancel); actions.addView(save);
        box.addView(actions);
        setContentView(box);
        text.requestFocus();
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE);
    }
}
