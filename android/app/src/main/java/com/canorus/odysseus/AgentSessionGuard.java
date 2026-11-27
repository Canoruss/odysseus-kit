package com.canorus.odysseus;

import java.util.List;

/** Guarda de sessão do agente. A lógica e o estado estão em Rust (voice-core/src/guard.rs). */
final class AgentSessionGuard {
    static { System.loadLibrary("odysseus_voice"); }

    static final class GuardVerdict {
        final boolean proceed;
        final boolean abortLoop;
        final String title;
        final String reason;

        private GuardVerdict(boolean proceed, boolean abortLoop, String title, String reason) {
            this.proceed = proceed;
            this.abortLoop = abortLoop;
            this.title = title;
            this.reason = reason;
        }

        static GuardVerdict ok() { return new GuardVerdict(true, false, null, null); }

        static GuardVerdict parse(String r) {
            if (r == null || r.startsWith("OK")) return ok();
            String[] f = r.split("\u001f", -1);
            String title = f.length > 1 && !f[1].isEmpty() ? f[1] : null;
            String reason = f.length > 2 ? f[2] : null;
            return "ABORT".equals(f[0]) ? new GuardVerdict(false, true, title, reason)
                    : new GuardVerdict(false, false, null, reason);
        }
    }

    private static native long nativeNew();
    private static native void nativeFree(long h);
    private static native long nativeHash(boolean present, String fgPkg, String fgClass, int total, String[] strings, int[] centers);
    private static native String nativeOnScreen(long h, boolean hasNodes, long hash, String prevAction);
    private static native void nativeRecordRefusal(long h, boolean hasPolicy, String sig, String crit, String action,
            String target, String fg, boolean hasNode, int id, String text, String desc, String viewId, int cx, int cy, int x, int y);
    private static native boolean nativeAskUserRefused(long h);
    private static native String nativeCheckBefore(long h, boolean hasPolicy, String sig, String crit, String action,
            String target, String fg, boolean hasNode, int id, String text, String desc, String viewId, int cx, int cy,
            int x, int y, long hash);
    private static native String nativeAfter(long h, String sig, boolean ok, long hash);

    private long handle = nativeNew();

    @Override
    protected void finalize() throws Throwable {
        try { long h = handle; handle = 0; nativeFree(h); } finally { super.finalize(); }
    }

    long computeScreenHash(AgentAccessibilityService.ScreenState state) {
        if (state == null) return nativeHash(false, null, null, -1, null, null);
        List<AgentAccessibilityService.NodeSnap> nodes = state.nodes;
        if (nodes == null) return nativeHash(true, state.foregroundPkg, state.foregroundClass, -1, null, null);
        int limit = Math.min(nodes.size(), 45);
        String[] s = new String[limit * 4];
        int[] c = new int[limit * 2];
        for (int i = 0; i < limit; i++) {
            AgentAccessibilityService.NodeSnap n = nodes.get(i);
            s[i * 4] = n.cls; s[i * 4 + 1] = n.viewId; s[i * 4 + 2] = n.text; s[i * 4 + 3] = n.desc;
            c[i * 2] = n.bounds.centerX(); c[i * 2 + 1] = n.bounds.centerY();
        }
        return nativeHash(true, state.foregroundPkg, state.foregroundClass, nodes.size(), s, c);
    }

    GuardVerdict onScreenInspected(AgentAccessibilityService.ScreenState state, long screenHash, String prevAction) {
        boolean has = state != null && state.nodes != null && !state.nodes.isEmpty();
        return GuardVerdict.parse(nativeOnScreen(handle, has, screenHash, prevAction));
    }

    void recordRefusal(AgentPolicy.Decision policy, String action, String targetPkg, String foregroundPkg,
                       AgentAccessibilityService.NodeSnap node, int x, int y) {
        boolean n = node != null;
        nativeRecordRefusal(handle, policy != null, policy != null ? policy.signature : null,
                policy != null ? policy.criticalPkg : null, action, targetPkg, foregroundPkg, n,
                n ? node.id : 0, n ? node.text : null, n ? node.desc : null, n ? node.viewId : null,
                n ? node.bounds.centerX() : 0, n ? node.bounds.centerY() : 0, x, y);
    }

    boolean recordAskUserRefusalAndShouldAbort() { return nativeAskUserRefused(handle); }

    GuardVerdict checkBeforeExecution(AgentPolicy.Decision policy, String action, String targetPkg, String foregroundPkg,
                                      AgentAccessibilityService.NodeSnap node, int x, int y, long currentScreenHash) {
        boolean n = node != null;
        return GuardVerdict.parse(nativeCheckBefore(handle, policy != null, policy != null ? policy.signature : null,
                policy != null ? policy.criticalPkg : null, action, targetPkg, foregroundPkg, n,
                n ? node.id : 0, n ? node.text : null, n ? node.desc : null, n ? node.viewId : null,
                n ? node.bounds.centerX() : 0, n ? node.bounds.centerY() : 0, x, y, currentScreenHash));
    }

    GuardVerdict afterExecution(String action, String signature, boolean ok, long screenHashBefore) {
        return GuardVerdict.parse(nativeAfter(handle, signature, ok, screenHashBefore));
    }
}
