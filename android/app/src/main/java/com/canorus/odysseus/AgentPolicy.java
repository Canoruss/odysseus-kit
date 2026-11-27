package com.canorus.odysseus;

import android.content.Context;

/** Avaliador de intenção e risco do agente. A lógica está em Rust (voice-core/src/policy.rs). */
final class AgentPolicy {
    private AgentPolicy() { }
    static { System.loadLibrary("odysseus_voice"); }

    enum Verdict { ALLOW, CONFIRM, BLOCK }

    enum Category {
        ROUTINE, SELF_PROTECTION, PASSWORD_AUTOFILL, PAYMENT, PASSWORD_MANAGER, MESSAGE_SEND,
        DATA_DELETE, SYSTEM_SENSITIVE, MODEL_CRITICAL, UNCLEAR_INTENT, STEP_DEBUG
    }

    static final class Decision {
        final Verdict verdict;
        final Category category;
        final String reason;
        final String signature;
        final String criticalPkg;

        Decision(Verdict verdict, Category category, String reason, String signature, String criticalPkg) {
            this.verdict = verdict;
            this.category = category;
            this.reason = reason;
            this.signature = signature == null ? "" : signature;
            this.criticalPkg = criticalPkg == null ? "" : criticalPkg;
        }
    }

    private static native String nativeEvaluate(String selfPkg, String goal, String action, String fgPkg,
            String fgClass, String targetPkg, boolean hasNode, int nodeId, String nodeText, String nodeDesc,
            String nodeViewId, int nodeCx, int nodeCy, boolean nodeEditable, boolean nodePassword,
            int x, int y, String textOrUrl, boolean submit, boolean modelCritical, String modelReason,
            boolean confirmCritical, boolean confirmAllSteps);

    static native String norm(String s);

    static native String normalizeHttpUrl(String raw);

    static Decision evaluate(Context ctx, String goal, String action, String foregroundPkg, String foregroundClass,
                             String resolvedTargetPkg, AgentAccessibilityService.NodeSnap node, int x, int y,
                             String textOrUrl, boolean submit, boolean modelCritical, String modelReason) {
        boolean has = node != null;
        String r = nativeEvaluate(ctx.getPackageName(), goal, action, foregroundPkg, foregroundClass, resolvedTargetPkg,
                has, has ? node.id : 0, has ? node.text : null, has ? node.desc : null, has ? node.viewId : null,
                has && node.bounds != null ? node.bounds.centerX() : 0, has && node.bounds != null ? node.bounds.centerY() : 0,
                has && node.editable, has && node.password, x, y, textOrUrl, submit, modelCritical, modelReason,
                AppSettings.agentConfirmCritical(ctx), AppSettings.agentConfirmAllSteps(ctx));
        String[] f = r == null ? new String[0] : r.split("\u001f", -1);
        if (f.length < 5) {
            return new Decision(Verdict.BLOCK, Category.SELF_PROTECTION, "Erro interno na política do agente.", "", "");
        }
        return new Decision(Verdict.valueOf(f[0]), Category.valueOf(f[1]), f[4].isEmpty() ? null : f[4], f[2], f[3]);
    }
}
