package com.canorus.odysseus;

import android.net.Uri;
import android.os.Bundle;
import android.widget.TextView;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import java.io.File;
import android.text.InputType;
import android.view.Gravity;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

/** L.t("Despesa rápida") (widget): valor + categoria + nota. Regista um gasto de hoje nas Finanças, sem abrir as Finanças. */
public class QuickExpenseActivity extends AppCompatActivity {
    private static final String[] CATS = {"comida", "restaurantes", "transportes", "combustivel", "casa", "contas", "saude", "farmacia", "roupa",
            "lazer", "ginasio", "educacao", "tecnologia", "viagens", "prestacoes", "presentes", "trabalho", "outros"};

    private EditText amountF, noteF;
    private Spinner catF;
    private TextView statusF;
    private File photo;
    private String receiptDate = null;
    private ActivityResultLauncher<Uri> cam;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (b != null && b.getString("photo") != null) photo = new File(b.getString("photo"));
        setTitle(L.t("Despesa rápida"));
        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(pad, pad, pad, pad);
        EditText amount = new EditText(this);
        amount.setHint(L.t("Valor em € (ex.: 12,50)"));
        amount.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        amountF = amount;
        Button shot = new Button(this); shot.setText(L.t("📷 Foto do talão"));
        statusF = new TextView(this);
        box.addView(shot);
        box.addView(statusF);
        box.addView(amount, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        Spinner cat = new Spinner(this);
        cat.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, CATS));
        catF = cat;
        box.addView(cat);
        EditText note = new EditText(this);
        note.setHint(L.t("Nota (opcional)"));
        note.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        noteF = note;
        box.addView(note, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.END);
        Button cancel = new Button(this); cancel.setText(L.t("Cancelar")); cancel.setOnClickListener(v -> finish());
        Button save = new Button(this); save.setText(L.t("Guardar"));
        save.setOnClickListener(v -> {
            String a = amount.getText().toString().trim().replace(',', '.');
            double val;
            try { val = Double.parseDouble(a); } catch (Exception e) { Toast.makeText(this, "Indica o valor", Toast.LENGTH_SHORT).show(); return; }
            if (val <= 0) { Toast.makeText(this, "Indica o valor", Toast.LENGTH_SHORT).show(); return; }
            String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
            if (cookie == null || cookie.isEmpty()) { Toast.makeText(this, L.t("Abre o Odysseus e inicia sessão primeiro"), Toast.LENGTH_LONG).show(); return; }
            save.setEnabled(false);
            String cs = CATS[cat.getSelectedItemPosition()];
            Bg.run(() -> {
                int code;
                JSONObject body = null;
                try {
                    body = new JSONObject().put("amount", val).put("category", cs).put("note", note.getText().toString().trim());
                    if (receiptDate != null) body.put("date", receiptDate);
                    code = Bg.isOnline(this) ? Actions.send("POST", NoteSync.SITE + "/finance/quick", cookie, "application/json", body.toString()) : -1;
                } catch (Exception e) { code = -1; }
                if (code == -1 && body != null) {
                    Outbox.enqueue(this, "/finance/quick", body);
                }
                final int c = code;
                runOnUiThread(() -> {
                    if (c == 200) { Toast.makeText(this, String.format(java.util.Locale.ROOT, L.t("Gasto registado: %.2f € (%s)"), val, cs), Toast.LENGTH_SHORT).show(); finish(); }
                    else if (c == -1) { Toast.makeText(this, L.t("Sem ligação agora — guardado no telemóvel para enviar assim que ligar."), Toast.LENGTH_LONG).show(); finish(); }
                    else {
                        save.setEnabled(true);
                        Toast.makeText(this, c == 403 ? L.t("Sem permissão nesta conta") : L.t("Não foi possível guardar (") + c + L.t("). Tens o Tailscale ligado?"), Toast.LENGTH_LONG).show();
                    }
                });
            });
        });
        actions.addView(cancel); actions.addView(save);
        box.addView(actions);
        setContentView(box);
        cam = registerForActivityResult(new ActivityResultContracts.TakePicture(), ok -> {
            if (ok != null && ok && photo != null && photo.length() > 0) readReceipt(photo);
            else if (getIntent().getBooleanExtra("photo", false) && amountF.getText().length() == 0) { /* cancelado: fica o formulário manual */ }
        });
        shot.setOnClickListener(v -> shoot());
        if (b == null && getIntent().getBooleanExtra("photo", false)) { shoot(); return; }
        amount.requestFocus();
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE);
    }

    @Override
    protected void onSaveInstanceState(Bundle o) {
        super.onSaveInstanceState(o);
        if (photo != null) o.putString("photo", photo.getAbsolutePath());
    }

    private void shoot() {
        photo = Cam.newFile(this);
        try { cam.launch(Cam.uri(this, photo)); }
        catch (Exception e) { Toast.makeText(this, L.t("Não foi possível abrir a câmara"), Toast.LENGTH_LONG).show(); }
    }

    private void readReceipt(File f) {
        String cookie = CookieManager.getInstance().getCookie(NoteSync.SITE);
        if (cookie == null || cookie.isEmpty()) { Toast.makeText(this, L.t("Abre o Odysseus e inicia sessão primeiro"), Toast.LENGTH_LONG).show(); return; }
        statusF.setText(L.t("A ler o talão…"));
        Bg.run(() -> {
            String err = null; double amt = 0; String cat = "outros", note = "", date = null;
            try {
                JSONObject j = new JSONObject(Cam.post(NoteSync.SITE + "/finance/quick/read", cookie,
                        new JSONObject().put("image", Cam.toB64(f)).toString(), 90000));
                if (j.has("error")) err = j.optString("error");
                else { amt = j.getDouble("amount"); cat = j.optString("category", "outros"); note = j.optString("note", ""); date = j.optString("date", null); }
            } catch (Exception e) { err = L.t("Não foi possível ler o talão. Tens o Tailscale ligado?"); }
            final String ferr = err, fcat = cat, fnote = note, fdate = date; final double famt = amt;
            runOnUiThread(() -> {
                if (ferr != null) { statusF.setText(ferr); return; }
                amountF.setText(String.format(java.util.Locale.ROOT, "%.2f", famt));
                for (int i = 0; i < CATS.length; i++) if (CATS[i].equals(fcat)) catF.setSelection(i);
                noteF.setText(fnote);
                receiptDate = fdate;
                statusF.setText("Lido" + (fdate != null ? " (" + fdate + ")" : "") + L.t(". Confirma os dados e carrega em Guardar."));
            });
        });
    }
}
