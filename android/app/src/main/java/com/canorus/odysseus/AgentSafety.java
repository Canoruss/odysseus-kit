package com.canorus.odysseus;

import android.content.Context;

/** Ponte para o catálogo de segurança do agente, implementado em Rust (voice-core/src/policy.rs). */
final class AgentSafety {
    private AgentSafety() { }
    static { System.loadLibrary("odysseus_voice"); }

    static final String BLOCKED_PREFIX = "BLOCKED:";

    private static native String nativeLabel(int id, String text, String desc, String viewId);

    static String check(Context ctx, String action, String foregroundPkg, String foregroundClass,
                        AgentAccessibilityService.NodeSnap node, int x, int y, String inputText,
                        boolean submit, boolean modelCritical, String modelReason) {
        AgentPolicy.Decision d = AgentPolicy.evaluate(ctx, "executar tarefa", action, foregroundPkg, foregroundClass,
                "", node, x, y, inputText, submit, modelCritical, modelReason);
        if (d.verdict == AgentPolicy.Verdict.BLOCK) return BLOCKED_PREFIX + d.reason;
        if (d.verdict == AgentPolicy.Verdict.CONFIRM) return d.reason;
        return null;
    }

    static String labelOf(AgentAccessibilityService.NodeSnap n) {
        if (n == null) return "ecrã";
        return nativeLabel(n.id, n.text, n.desc, n.viewId);
    }
}
