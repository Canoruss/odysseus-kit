package com.canorus.odysseus;

import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.speech.RecognizerIntent;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import java.util.ArrayList;

/**
 * Janela rápida sobreposta (texto + voz) para comandar o Agente Odysseus.
 * Proteção ativa: nunca inicia tarefas externas automaticamente — exige revisão e toque explícito em ▶ Executar.
 */
public class AgentPromptActivity extends AppCompatActivity {

    private EditText goalInput;
    private boolean ownRecorder = false;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        AppSettings.applyServer(this);
        String action = getIntent().getAction();
        if (Intent.ACTION_ASSIST.equals(action) || Intent.ACTION_VOICE_COMMAND.equals(action)) {
            GeminiLauncher.open(this);
            finish();
            return;
        }
        boolean ryoku = "ryoku".equals(AppSettings.sp(this).getString("ui_theme", ""));
        int bg = ryoku ? 0xFF0a0a0a : 0xFF282c34;
        int fg = ryoku ? 0xFFcdc4ba : 0xFFE5E9F0;
        int ac = ryoku ? 0xFFce5e32 : 0xFF7C9CFF;
        int btnBg = ryoku ? 0xFF141414 : 0xFF3d4452;

        getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(bg));
        int p = dp(18);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(p, p, p, p);
        box.setBackgroundColor(bg);

        TextView title = new TextView(this);
        title.setText("🤖 Agente Odysseus");
        title.setTextSize(19);
        title.setTextColor(ac);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        box.addView(title);

        if (!AgentAccessibilityService.isReady()) {
            Button a11yBtn = actionBtn("⚠️ 1. Ativar Acessibilidade (Controlo de Ecrã)", 0xFFd97706, Color.WHITE);
            a11yBtn.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
            box.addView(a11yBtn);
        }

        if (!Settings.canDrawOverlays(this)) {
            Button ovBtn = actionBtn("⚠️ 2. Permitir Botão Flutuante (Obrigatório p/ PARAR e Confirmações)", 0xFFd97706, Color.WHITE);
            ovBtn.setOnClickListener(v -> startActivity(new Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + getPackageName()))));
            box.addView(ovBtn);
        }

        if (AppSettings.agentToken(this).isEmpty() && !"/api/android-agent/step".equals(AppSettings.agentEndpoint(this))) {
            Button tokBtn = actionBtn("🔑 Configurar Token de /agent/step nas Definições", btnBg, 0xFFf0a540);
            tokBtn.setOnClickListener(v -> startActivity(new Intent(this, SettingsActivity.class)));
            box.addView(tokBtn);
        }

        goalInput = new EditText(this);
        goalInput.setHint("O que queres que o agente faça? Revê o texto e toca em ▶ Executar.");
        goalInput.setHintTextColor(0xFF9AA3B2);
        goalInput.setTextColor(fg);
        goalInput.setMinLines(3);
        goalInput.setGravity(Gravity.TOP);
        goalInput.setPadding(dp(10), dp(10), dp(10), dp(10));
        box.addView(goalInput, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout row = new LinearLayout(this);
        row.setGravity(Gravity.END);

        Button micBtn = actionBtn("🎤 Falar", btnBg, fg);
        micBtn.setOnClickListener(v -> startVoiceCapture());

        Button stopBtn = actionBtn("⏹ Parar", 0xFFd94848, Color.WHITE);
        stopBtn.setOnClickListener(v -> {
            AgentService.stopAgent(this);
            finish();
        });

        Button goBtn = actionBtn("▶ Executar", ac, Color.WHITE);
        goBtn.setOnClickListener(v -> submitGoal());

        row.addView(micBtn);
        row.addView(stopBtn);
        row.addView(goBtn);
        box.addView(row);

        setContentView(box);

        // Pré-preenche sem NUNCA iniciar automaticamente (protege contra Intents externos não confiáveis)
        String preset = getIntent().getStringExtra("goal");
        if (preset != null && !preset.trim().isEmpty()) {
            goalInput.setText(preset.trim());
            goalInput.setSelection(goalInput.getText().length());
            goalInput.requestFocus();
            return;
        }

        if (getIntent().getBooleanExtra("voice", false)) {
            startVoiceCapture();
        } else {
            goalInput.requestFocus();
        }
    }

    private void startVoiceCapture() {
        try {
            Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE, L.isEn() ? "en-US" : "pt-PT")
                    .putExtra(RecognizerIntent.EXTRA_PROMPT, "Diz a instrução (vais poder rever antes de Executar)…");
            if (i.resolveActivity(getPackageManager()) == null) throw new Exception("no_stt");
            startActivityForResult(i, 91);
        } catch (Exception e) {
            ownRecorder = true;
            Voice.listen(this, L.isEn() ? "en" : "pt", txt -> {
                ownRecorder = false;
                if (txt != null && !txt.trim().isEmpty()) {
                    goalInput.setText(txt.trim());
                    goalInput.setSelection(goalInput.getText().length());
                }
            });
        }
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != 91 || ownRecorder) return;
        ArrayList<String> list = (res == RESULT_OK && data != null)
                ? data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS) : null;
        if (list != null && !list.isEmpty() && !list.get(0).trim().isEmpty()) {
            goalInput.setText(list.get(0).trim());
            goalInput.setSelection(goalInput.getText().length());
        }
    }

    private void submitGoal() {
        String g = goalInput.getText().toString().trim();
        if (g.isEmpty()) {
            Toast.makeText(this, "Escreve ou dita primeiro o objetivo.", Toast.LENGTH_SHORT).show();
            return;
        }
        if (!AgentAccessibilityService.isReady()) {
            Toast.makeText(this, "Ativa primeiro o serviço de Acessibilidade do Odysseus.", Toast.LENGTH_LONG).show();
            startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
            return;
        }
        if (!Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "Permite primeiro Sobrepor a outras apps (necessário para confirmações e botão PARAR).", Toast.LENGTH_LONG).show();
            startActivity(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName())));
            return;
        }
        AgentService.startGoal(this, g);
        moveTaskToBack(true);
        finish();
    }

    private Button actionBtn(String label, int bg, int fg) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextColor(fg);
        b.setBackgroundColor(bg);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(8);
        lp.rightMargin = dp(6);
        b.setLayoutParams(lp);
        return b;
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }
}
