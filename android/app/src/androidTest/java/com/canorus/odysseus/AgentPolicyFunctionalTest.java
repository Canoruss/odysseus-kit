package com.canorus.odysseus;

import android.content.Context;
import android.graphics.Rect;
import androidx.test.core.app.ApplicationProvider;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.Test;
import org.junit.runner.RunWith;
import static org.junit.Assert.*;

@RunWith(AndroidJUnit4.class)
public class AgentPolicyFunctionalTest {
    private AgentPolicy.Decision evaluate(String goal, String action, String fg, String target,
                                           AgentAccessibilityService.NodeSnap node, String value) {
        Context ctx = ApplicationProvider.getApplicationContext();
        return AgentPolicy.evaluate(ctx, goal, action, fg, "", target, node, -1, -1, value, false, false, "");
    }
    private AgentAccessibilityService.NodeSnap node(String label) {
        return new AgentAccessibilityService.NodeSnap(1, "android.widget.Button", label, "", "", new Rect(0, 0, 100, 100), true, false, false, false, false);
    }
    @Test public void routineActionsAreAllowed() {
        assertEquals(AgentPolicy.Verdict.ALLOW, evaluate("Abre Spotify", "open_app", "", "com.spotify.music", null, "Spotify").verdict);
        assertEquals(AgentPolicy.Verdict.ALLOW, evaluate("Abre https://example.com", "open_url", "", "", null, "https://example.com").verdict);
    }
    @Test public void sensitiveActionsRequireConfirmation() {
        assertEquals(AgentPolicy.Verdict.CONFIRM, evaluate("Paga", "tap", "com.example.shop", "", node("Pagar"), "").verdict);
        assertEquals(AgentPolicy.Verdict.CONFIRM, evaluate("Abre Bitwarden", "open_app", "", "com.x8bit.bitwarden", null, "Bitwarden").verdict);
        assertEquals(AgentPolicy.Verdict.CONFIRM, evaluate("Envia mensagem", "tap", "com.example.chat", "", node("Enviar"), "").verdict);
        assertEquals(AgentPolicy.Verdict.CONFIRM, evaluate("Apaga", "tap", "com.example.app", "", node("Apagar"), "").verdict);
    }
    @Test public void refusalPreventsRepeat() {
        AgentAccessibilityService.NodeSnap n = node("Pagar");
        AgentPolicy.Decision d = evaluate("Paga", "tap", "com.example.shop", "", n, "");
        AgentSessionGuard guard = new AgentSessionGuard();
        guard.recordRefusal(d, "tap", "", "com.example.shop", n, -1, -1);
        assertTrue(guard.checkBeforeExecution(d, "tap", "", "com.example.shop", n, -1, -1, 1).abortLoop);
    }
    @Test public void unidentifiedElementIsBlockedAndFailuresStop() {
        assertEquals(AgentPolicy.Verdict.BLOCK, evaluate("Toca no botão", "tap", "com.example.app", "", null, "").verdict);
        AgentSessionGuard guard = new AgentSessionGuard();
        assertFalse(guard.afterExecution("tap", "a", false, 1).abortLoop);
        assertFalse(guard.afterExecution("tap", "b", false, 1).abortLoop);
        assertTrue(guard.afterExecution("tap", "c", false, 1).abortLoop);
    }
}
