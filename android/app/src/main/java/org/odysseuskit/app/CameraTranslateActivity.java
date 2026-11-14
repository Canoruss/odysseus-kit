package org.odysseuskit.app;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

import java.io.File;

/** Widget "Traduzir foto": tira uma foto a um texto (menu, sinal, documento) e mostra a tradução em pt-PT (ou inglês se já estiver em português). */
public class CameraTranslateActivity extends AppCompatActivity {
    private static final int BG = Color.parseColor("#282c34"), FG = Color.parseColor("#E5E9F0"), MUTED = Color.parseColor("#9AA3B2");
    private TextView status, original, translation;
    private File photo;
    private String lastTranslation = "";
    private ActivityResultLauncher<Uri> cam;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        if (b != null && b.getString("photo") != null) photo = new File(b.getString("photo"));
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        int p = (int) (16 * getResources().getDisplayMetrics().density);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(BG);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(p, p, p, p);
        sv.addView(root);
        setContentView(sv);
        status = tv(root, "", 14, MUTED);
        translation = tv(root, "", 20, FG);
        translation.setTextIsSelectable(true);
        original = tv(root, "", 14, MUTED);
        original.setTextIsSelectable(true);
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        Button copy = btn("Copiar", v -> {
            ((ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText(Tr.t("tradução"), lastTranslation));
            Toast.makeText(this, "Copiado", Toast.LENGTH_SHORT).show();
        });
        Button again = btn("📷 Outra foto", v -> shoot());
        Button close = btn("Fechar", v -> finish());
        row.addView(copy); row.addView(again); row.addView(close);
        root.addView(row);
        cam = registerForActivityResult(new ActivityResultContracts.TakePicture(), ok -> {
            if (ok != null && ok && photo != null && photo.length() > 0) translate(photo);
            else if (lastTranslation.isEmpty()) finish();
        });
        if (b == null) shoot();
    }

    private TextView tv(LinearLayout root, String t, int sp, int color) {
        TextView v = new TextView(this);
        v.setText(t); v.setTextSize(sp); v.setTextColor(color);
        v.setPadding(0, 0, 0, (int) (12 * getResources().getDisplayMetrics().density));
        root.addView(v, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return v;
    }

    private Button btn(String t, android.view.View.OnClickListener l) {
        Button x = new Button(this);
        x.setText(t); x.setOnClickListener(l);
        return x;
    }

    @Override
    protected void onSaveInstanceState(Bundle o) {
        super.onSaveInstanceState(o);
        if (photo != null) o.putString("photo", photo.getAbsolutePath());
    }

    private void shoot() {
        photo = Cam.newFile(this);
        try { cam.launch(Cam.uri(this, photo)); }
        catch (Exception e) { Toast.makeText(this, Tr.t("Não foi possível abrir a câmara"), Toast.LENGTH_LONG).show(); }
    }

    private void translate(File f) {
        status.setText("A ler e traduzir…");
        translation.setText(""); original.setText("");
        new Thread(() -> {
            String tr = "", orig = "", err = null;
            try {
                String img = Cam.toB64(f);
                String base = AppSettings.sp(this).getString("tr_base", NoteSync.SITE) + "/translate/api/image";
                JSONObject j = new JSONObject(Cam.post(base, null, new JSONObject().put("image", img).put("target", "pt").toString(), 90000));
                if (j.has("error")) throw new Exception(j.optString("error"));
                if ("pt".equals(j.optString("detected"))) {
                    j = new JSONObject(Cam.post(base, null, new JSONObject().put("image", img).put("target", "en").toString(), 90000));
                    if (j.has("error")) throw new Exception(j.optString("error"));
                }
                tr = j.optString("translation"); orig = j.optString("original");
                if (tr.isEmpty()) err = Tr.t("Não encontrei texto na foto. Tenta outra foto, mais perto e com boa luz.");
            } catch (Exception e) {
                err = Tr.t("Não foi possível traduzir (") + (e.getMessage() == null ? Tr.t("erro") : e.getMessage()) + Tr.t("). Tens o Tailscale ligado?");
            }
            final String ftr = tr, forig = orig, ferr = err;
            runOnUiThread(() -> {
                if (ferr != null) { status.setText(ferr); return; }
                lastTranslation = ftr;
                status.setText(Tr.t("Tradução"));
                translation.setText(ftr);
                original.setText("Original:\n" + forig);
            });
        }).start();
    }
}
