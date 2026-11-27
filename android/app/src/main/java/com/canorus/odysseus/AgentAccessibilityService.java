package com.canorus.odysseus;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Rect;
import android.hardware.HardwareBuffer;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Base64;
import android.util.DisplayMetrics;
import android.util.SparseArray;
import android.view.Display;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Serviço de Acessibilidade do Agente Odysseus:
 * - Extrai a árvore interativa de todas as apps no ecrã (ocultando campos de password/PIN)
 * - Captura screenshots com etiquetas Set-of-Mark (Android 11+) sem Root
 * - Executa toques, swipes, escrita de texto e abertura de qualquer app instalada
 */
public class AgentAccessibilityService extends AccessibilityService {

    static volatile AgentAccessibilityService instance;
    private volatile String currentPkg = "";
    private volatile String currentClass = "";
    private final SparseArray<NodeSnap> lastNodes = new SparseArray<>();

    static final class NodeSnap {
        final int id;
        final String cls;
        final String text;
        final String desc;
        final String viewId;
        final Rect bounds;
        final boolean clickable;
        final boolean editable;
        final boolean scrollable;
        final boolean focused;
        final boolean password;

        NodeSnap(int id, String cls, String text, String desc, String viewId, Rect bounds,
                 boolean clickable, boolean editable, boolean scrollable, boolean focused, boolean password) {
            this.id = id;
            this.cls = cls;
            this.text = text;
            this.desc = desc;
            this.viewId = viewId;
            this.bounds = bounds;
            this.clickable = clickable;
            this.editable = editable;
            this.scrollable = scrollable;
            this.focused = focused;
            this.password = password;
        }
    }

    static final class ScreenState {
        final int width;
        final int height;
        final String foregroundPkg;
        final String foregroundClass;
        final String foregroundApp;
        final JSONArray uiTree;
        final List<NodeSnap> nodes;

        ScreenState(int width, int height, String foregroundPkg, String foregroundClass,
                    String foregroundApp, JSONArray uiTree, List<NodeSnap> nodes) {
            this.width = width;
            this.height = height;
            this.foregroundPkg = foregroundPkg;
            this.foregroundClass = foregroundClass;
            this.foregroundApp = foregroundApp;
            this.uiTree = uiTree;
            this.nodes = nodes;
        }
    }

    static boolean isReady() {
        return instance != null;
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
        if (AppSettings.sp(this).getBoolean("agent_overlay", false)) {
            AgentService.showIdleOverlay(this);
        }
    }

    boolean hasAgentControls() {
        if (Build.VERSION.SDK_INT < 24) return false;
        for (AccessibilityWindowInfo window : getWindows()) {
            if (window == null || window.getType() != AccessibilityWindowInfo.TYPE_SYSTEM) continue;
            AccessibilityNodeInfo root = window.getRoot();
            if (root != null && getPackageName().contentEquals(String.valueOf(root.getPackageName()))) {
                for (AccessibilityNodeInfo button : root.findAccessibilityNodeInfosByText(AgentService.CONTROL_WINDOW)) {
                    if (AgentService.CONTROL_WINDOW.contentEquals(String.valueOf(button.getContentDescription())) && button.isVisibleToUser() && button.isClickable()) return true;
                }
            }
        }
        return false;
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event == null || event.getPackageName() == null) return;
        String pkg = event.getPackageName().toString();
        if (!pkg.contains("inputmethod")) {
            currentPkg = pkg;
            if (event.getEventType() == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED
                    && event.getClassName() != null) {
                String cn = event.getClassName().toString();
                // Ignorar janelas auxiliares da própria app (overlay, toasts, diálogos): só atividades reais
                if (!pkg.equals(getPackageName()) || cn.endsWith("Activity")) currentClass = cn;
            }
        }
    }

    @Override
    public void onInterrupt() { }

    @Override
    public boolean onUnbind(Intent intent) {
        if (instance == this) instance = null;
        return super.onUnbind(intent);
    }

    int[] screenSize() {
        DisplayMetrics dm = getResources().getDisplayMetrics();
        try {
            WindowManager wm = (WindowManager) getSystemService(WINDOW_SERVICE);
            if (wm != null && Build.VERSION.SDK_INT >= 30) {
                Rect b = wm.getMaximumWindowMetrics().getBounds();
                if (b.width() > 0 && b.height() > 0) return new int[]{b.width(), b.height()};
            } else if (wm != null) {
                wm.getDefaultDisplay().getRealMetrics(dm);
            }
        } catch (Exception ignored) { }
        return new int[]{dm.widthPixels, dm.heightPixels};
    }

    NodeSnap getNodeSnap(int id) {
        synchronized (lastNodes) {
            return lastNodes.get(id);
        }
    }

    ScreenState inspectScreen() {
        int[] sz = screenSize();
        int sw = sz[0], sh = sz[1];
        List<NodeSnap> snaps = new ArrayList<>();
        String activePkg = currentPkg;

        List<AccessibilityWindowInfo> windows = null;
        try { windows = getWindows(); } catch (Exception ignored) { }

        if (windows != null && !windows.isEmpty()) {
            for (AccessibilityWindowInfo w : windows) {
                if (w == null) continue;
                if (w.getType() == AccessibilityWindowInfo.TYPE_ACCESSIBILITY_OVERLAY) continue;
                AccessibilityNodeInfo root = w.getRoot();
                if (root == null) continue;
                CharSequence rp = root.getPackageName();
                if (rp != null && rp.length() > 0) {
                    if (w.isActive() || activePkg.isEmpty()) activePkg = rp.toString();
                }
                collectNodes(root, sw, sh, snaps);
            }
        } else {
            AccessibilityNodeInfo root = getRootInActiveWindow();
            if (root != null) {
                if (root.getPackageName() != null) activePkg = root.getPackageName().toString();
                collectNodes(root, sw, sh, snaps);
            }
        }

        JSONArray arr = new JSONArray();
        synchronized (lastNodes) {
            lastNodes.clear();
            for (NodeSnap n : snaps) {
                lastNodes.put(n.id, n);
                try {
                    JSONObject o = new JSONObject()
                            .put("id", n.id)
                            .put("cls", n.cls)
                            .put("bounds", new JSONArray()
                                    .put(n.bounds.left).put(n.bounds.top)
                                    .put(n.bounds.right).put(n.bounds.bottom))
                            .put("center", new JSONArray()
                                    .put(n.bounds.centerX()).put(n.bounds.centerY()));
                    if (!n.text.isEmpty()) o.put("text", n.text);
                    if (!n.desc.isEmpty()) o.put("desc", n.desc);
                    if (!n.viewId.isEmpty()) o.put("view_id", n.viewId);
                    if (n.clickable) o.put("clickable", true);
                    if (n.editable) o.put("editable", true);
                    if (n.scrollable) o.put("scrollable", true);
                    if (n.focused) o.put("focused", true);
                    if (n.password) o.put("password", true);
                    arr.put(o);
                } catch (Exception ignored) { }
            }
        }
        return new ScreenState(sw, sh, activePkg, currentClass, appLabel(activePkg), arr, snaps);
    }

    private void collectNodes(AccessibilityNodeInfo node, int sw, int sh, List<NodeSnap> out) {
        if (node == null || out.size() >= 95) return;
        if (!node.isVisibleToUser()) return;

        CharSequence pkg = node.getPackageName();
        if (pkg != null && pkg.toString().equals(getPackageName())
                && node.getViewIdResourceName() != null
                && node.getViewIdResourceName().contains("ody_agent_overlay")) {
            return;
        }

        Rect r = new Rect();
        node.getBoundsInScreen(r);
        boolean validBounds = r.width() > 4 && r.height() > 4
                && r.right > 0 && r.bottom > 0 && r.left < sw && r.top < sh;

        boolean isPwd = node.isPassword();
        String text;
        if (isPwd) {
            text = "[campo protegido]";
        } else {
            text = safeStr(node.getText());
            if (text.isEmpty() && Build.VERSION.SDK_INT >= 26) {
                text = safeStr(node.getHintText());
            }
        }
        String desc = safeStr(node.getContentDescription());
        String vid = safeStr(node.getViewIdResourceName());
        int slash = vid.indexOf('/');
        if (slash >= 0 && slash + 1 < vid.length()) vid = vid.substring(slash + 1);

        boolean click = node.isClickable() || node.isLongClickable() || node.isCheckable();
        boolean edit = node.isEditable();
        boolean scroll = node.isScrollable();
        boolean hasInfo = !text.isEmpty() || !desc.isEmpty();

        if (validBounds && (click || edit || scroll || hasInfo)) {
            String rawCls = safeStr(node.getClassName());
            int dot = rawCls.lastIndexOf('.');
            String shortCls = dot >= 0 ? rawCls.substring(dot + 1) : rawCls;
            int id = out.size() + 1;
            out.add(new NodeSnap(id, shortCls, truncate(text, 120), truncate(desc, 100),
                    vid, r, click, edit, scroll, node.isFocused(), isPwd));
        }

        int count = node.getChildCount();
        for (int i = 0; i < count && out.size() < 95; i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) collectNodes(child, sw, sh, out);
        }
    }

    /** Captura o ecrã (Android 11+) e desenha etiquetas Set-of-Mark (#1, #2...) nos elementos clicáveis. */
    String captureAnnotatedScreenshotB64(List<NodeSnap> nodes, int screenW, int screenH) {
        if (Build.VERSION.SDK_INT < 30) return "";
        final CountDownLatch latch = new CountDownLatch(1);
        final AtomicReference<String> outB64 = new AtomicReference<>("");

        try {
            takeScreenshot(Display.DEFAULT_DISPLAY, Bg.io(), new TakeScreenshotCallback() {
                @Override
                public void onSuccess(ScreenshotResult sr) {
                    HardwareBuffer hb = null;
                    Bitmap hwBmp = null;
                    Bitmap softBmp = null;
                    Bitmap scaled = null;
                    try {
                        hb = sr.getHardwareBuffer();
                        hwBmp = Bitmap.wrapHardwareBuffer(hb, sr.getColorSpace());
                        if (hwBmp != null) {
                            softBmp = hwBmp.copy(Bitmap.Config.ARGB_8888, true);
                        }
                        if (softBmp != null) {
                            float factor = Math.min(1f, 1280f / Math.max(softBmp.getWidth(), softBmp.getHeight()));
                            int tw = Math.max(1, Math.round(softBmp.getWidth() * factor));
                            int th = Math.max(1, Math.round(softBmp.getHeight() * factor));
                            scaled = (factor < 0.99f)
                                    ? Bitmap.createScaledBitmap(softBmp, tw, th, true)
                                    : softBmp;
                            drawSetOfMark(scaled, nodes,
                                    (float) tw / Math.max(1, screenW),
                                    (float) th / Math.max(1, screenH));
                            ByteArrayOutputStream bo = new ByteArrayOutputStream(180 * 1024);
                            scaled.compress(Bitmap.CompressFormat.JPEG, 76, bo);
                            outB64.set(Base64.encodeToString(bo.toByteArray(), Base64.NO_WRAP));
                        }
                    } catch (Throwable ignored) {
                    } finally {
                        if (scaled != null && scaled != softBmp && !scaled.isRecycled()) scaled.recycle();
                        if (softBmp != null && !softBmp.isRecycled()) softBmp.recycle();
                        if (hwBmp != null && !hwBmp.isRecycled()) hwBmp.recycle();
                        if (hb != null) {
                            try { hb.close(); } catch (Throwable ignored) { }
                        }
                        latch.countDown();
                    }
                }

                @Override
                public void onFailure(int errorCode) {
                    latch.countDown();
                }
            });
            latch.await(4500, TimeUnit.MILLISECONDS);
        } catch (Throwable ignored) { }
        return outB64.get();
    }

    private static void drawSetOfMark(Bitmap bmp, List<NodeSnap> nodes, float sx, float sy) {
        if (nodes == null || nodes.isEmpty()) return;
        Canvas c = new Canvas(bmp);
        Paint boxPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        boxPaint.setStyle(Paint.Style.STROKE);
        boxPaint.setStrokeWidth(2.2f);

        Paint bgPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        bgPaint.setStyle(Paint.Style.FILL);

        Paint txtPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        txtPaint.setColor(Color.WHITE);
        txtPaint.setTextSize(20f);
        txtPaint.setFakeBoldText(true);

        for (NodeSnap n : nodes) {
            if (!n.clickable && !n.editable) continue;
            float l = n.bounds.left * sx;
            float t = n.bounds.top * sy;
            float r = n.bounds.right * sx;
            float b = n.bounds.bottom * sy;
            int color = n.editable ? Color.rgb(30, 160, 90) : Color.rgb(220, 65, 45);
            boxPaint.setColor(color);
            bgPaint.setColor(Color.argb(215, Color.red(color), Color.green(color), Color.blue(color)));
            c.drawRect(l, t, r, b, boxPaint);

            String tag = String.valueOf(n.id);
            float tw = txtPaint.measureText(tag) + 10f;
            float th = 24f;
            float bx = Math.max(0f, Math.min(bmp.getWidth() - tw, l));
            float by = Math.max(0f, t - th > 0 ? t - th : t);
            c.drawRect(bx, by, bx + tw, by + th, bgPaint);
            c.drawText(tag, bx + 5f, by + 18f, txtPaint);
        }
    }

    boolean tap(int nodeId, int x, int y) {
        if (nodeId > 0) {
            AccessibilityNodeInfo live = findLiveNode(nodeId);
            if (live != null) {
                AccessibilityNodeInfo cur = live;
                for (int depth = 0; depth < 4 && cur != null; depth++) {
                    if (cur.isClickable() && cur.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                        return true;
                    }
                    cur = cur.getParent();
                }
            }
            NodeSnap snap = getNodeSnap(nodeId);
            if (snap != null && (x <= 0 || y <= 0)) {
                x = snap.bounds.centerX();
                y = snap.bounds.centerY();
            }
        }
        return x > 0 && y > 0 && gestureStroke(x, y, x, y, 75);
    }

    boolean longPress(int nodeId, int x, int y) {
        if (nodeId > 0) {
            AccessibilityNodeInfo live = findLiveNode(nodeId);
            if (live != null && live.isLongClickable()
                    && live.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK)) {
                return true;
            }
            NodeSnap snap = getNodeSnap(nodeId);
            if (snap != null && (x <= 0 || y <= 0)) {
                x = snap.bounds.centerX();
                y = snap.bounds.centerY();
            }
        }
        return x > 0 && y > 0 && gestureStroke(x, y, x, y, 680);
    }

    boolean doubleTap(int nodeId, int x, int y) {
        if (nodeId > 0 && (x <= 0 || y <= 0)) {
            NodeSnap snap = getNodeSnap(nodeId);
            if (snap != null) {
                x = snap.bounds.centerX();
                y = snap.bounds.centerY();
            }
        }
        if (Build.VERSION.SDK_INT < 24 || x <= 0 || y <= 0) return false;
        try {
            Path p1 = new Path(); p1.moveTo(x, y);
            Path p2 = new Path(); p2.moveTo(x, y);
            GestureDescription gd = new GestureDescription.Builder()
                    .addStroke(new GestureDescription.StrokeDescription(p1, 0, 45))
                    .addStroke(new GestureDescription.StrokeDescription(p2, 115, 45))
                    .build();
            return dispatchSync(gd);
        } catch (Exception e) {
            return false;
        }
    }

    boolean typeText(int nodeId, int x, int y, String text, boolean submit) {
        if (text == null) return false;
        if (nodeId > 0 || (x > 0 && y > 0)) {
            tap(nodeId, x, y);
            sleepQuiet(280);
        }
        AccessibilityNodeInfo target = findFocusedOrEditable(nodeId);
        boolean typed = false;
        if (target != null) {
            if (target.isPassword()) return false; // Nunca preencher passwords automaticamente sem ação manual
            Bundle b = new Bundle();
            b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
            typed = target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, b);
            if (!typed) {
                copyToClipboard(text);
                target.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
                typed = target.performAction(AccessibilityNodeInfo.ACTION_PASTE);
            }
            if (typed && submit && Build.VERSION.SDK_INT >= 30) {
                sleepQuiet(150);
                target.performAction(AccessibilityNodeInfo.AccessibilityAction.ACTION_IME_ENTER.getId());
            }
        }
        return typed;
    }

    boolean swipeDirection(String dir) {
        int[] sz = screenSize();
        int cx = sz[0] / 2, cy = sz[1] / 2;
        int dx = Math.round(sz[0] * 0.34f);
        int dy = Math.round(sz[1] * 0.32f);
        String d = dir == null ? "up" : dir.toLowerCase(Locale.ROOT);
        switch (d) {
            case "down": return gestureStroke(cx, cy - dy, cx, cy + dy, 340);
            case "left": return gestureStroke(cx + dx, cy, cx - dx, cy, 320);
            case "right": return gestureStroke(cx - dx, cy, cx + dx, cy, 320);
            case "up":
            default: return gestureStroke(cx, cy + dy, cx, cy - dy, 340);
        }
    }

    boolean gestureStroke(int x1, int y1, int x2, int y2, int durationMs) {
        if (Build.VERSION.SDK_INT < 24) return false;
        try {
            Path p = new Path();
            p.moveTo(Math.max(1, x1), Math.max(1, y1));
            if (x1 != x2 || y1 != y2) p.lineTo(Math.max(1, x2), Math.max(1, y2));
            GestureDescription gd = new GestureDescription.Builder()
                    .addStroke(new GestureDescription.StrokeDescription(p, 0, Math.max(40, durationMs)))
                    .build();
            return dispatchSync(gd);
        } catch (Exception e) {
            return false;
        }
    }

    private boolean dispatchSync(GestureDescription gd) {
        if (Build.VERSION.SDK_INT < 24) return false;
        final CountDownLatch latch = new CountDownLatch(1);
        final boolean[] ok = {false};
        boolean queued = dispatchGesture(gd, new GestureResultCallback() {
            @Override public void onCompleted(GestureDescription gestureDescription) {
                ok[0] = true;
                latch.countDown();
            }
            @Override public void onCancelled(GestureDescription gestureDescription) {
                latch.countDown();
            }
        }, null);
        if (!queued) return false;
        try { latch.await(3000, TimeUnit.MILLISECONDS); } catch (InterruptedException ignored) { }
        return ok[0];
    }

    String resolveAppPackage(String query) {
        if (query == null || query.trim().isEmpty()) return "";
        String q = query.trim();
        PackageManager pm = getPackageManager();

        if (pm.getLaunchIntentForPackage(q) != null) {
            return q;
        }

        String ql = AgentPolicy.norm(q);
        Intent main = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> list = pm.queryIntentActivities(main, 0);
        String bestPkg = "";
        for (ResolveInfo ri : list) {
            if (ri.activityInfo == null) continue;
            String pkg = ri.activityInfo.packageName;
            String label = AgentPolicy.norm(String.valueOf(ri.loadLabel(pm)));
            if (label.equals(ql) || pkg.equalsIgnoreCase(q)) {
                return pkg;
            }
            if (bestPkg.isEmpty() && !label.isEmpty() && (label.contains(ql) || ql.contains(label))) {
                bestPkg = pkg;
            }
        }
        return bestPkg;
    }

    boolean openApp(String query) {
        String pkg = resolveAppPackage(query);
        if (pkg.isEmpty()) return false;
        Intent launch = getPackageManager().getLaunchIntentForPackage(pkg);
        if (launch == null) return false;
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
        try {
            startActivity(launch);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    boolean openUrl(String rawUrl) {
        String cleanUrl = AgentPolicy.normalizeHttpUrl(rawUrl);
        if (cleanUrl == null) return false;
        try {
            Intent view = new Intent(Intent.ACTION_VIEW, Uri.parse(cleanUrl))
                    .addCategory(Intent.CATEGORY_BROWSABLE)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(view);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    JSONArray listInstalledAppsJson() {
        return listInstalledAppsJson(null);
    }

    JSONArray listInstalledAppsJson(String goal) {
        JSONArray arr = new JSONArray();
        try {
            String normGoal = AgentPolicy.norm(goal);
            PackageManager pm = getPackageManager();
            Intent main = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
            List<ResolveInfo> list = pm.queryIntentActivities(main, 0);
            List<String[]> prioritized = new ArrayList<>();
            List<String[]> rest = new ArrayList<>();
            Set<String> seen = new HashSet<>();

            for (ResolveInfo ri : list) {
                if (ri.activityInfo == null) continue;
                String pkg = ri.activityInfo.packageName;
                if (!seen.add(pkg)) continue;
                String label = String.valueOf(ri.loadLabel(pm)).trim();
                String normLabel = AgentPolicy.norm(label);
                boolean matchesGoal = !normGoal.isEmpty() && !normLabel.isEmpty()
                        && (normGoal.contains(normLabel) || pkgMatchesGoal(pkg, normGoal));
                if (matchesGoal) prioritized.add(new String[]{label, pkg});
                else rest.add(new String[]{label, pkg});
            }

            Collections.sort(prioritized, (a, b) -> a[0].compareToIgnoreCase(b[0]));
            Collections.sort(rest, (a, b) -> a[0].compareToIgnoreCase(b[0]));
            prioritized.addAll(rest);

            for (int i = 0; i < Math.min(prioritized.size(), 300); i++) {
                arr.put(new JSONObject()
                        .put("name", prioritized.get(i)[0])
                        .put("package", prioritized.get(i)[1]));
            }
        } catch (Exception ignored) { }
        return arr;
    }

    private static boolean pkgMatchesGoal(String pkg, String normGoal) {
        String[] parts = pkg.toLowerCase(Locale.ROOT).split("\\.");
        for (String p : parts) {
            if (p.length() >= 4 && !"android".equals(p) && !"google".equals(p)
                    && !"apps".equals(p) && normGoal.contains(p)) {
                return true;
            }
        }
        return false;
    }

    private List<AccessibilityNodeInfo> interactiveRoots() {
        List<AccessibilityNodeInfo> roots = new ArrayList<>();
        AccessibilityNodeInfo active = getRootInActiveWindow();
        if (active != null) roots.add(active);
        try {
            List<AccessibilityWindowInfo> windows = getWindows();
            if (windows != null) {
                for (AccessibilityWindowInfo w : windows) {
                    if (w == null || w.getType() == AccessibilityWindowInfo.TYPE_ACCESSIBILITY_OVERLAY) continue;
                    AccessibilityNodeInfo r = w.getRoot();
                    if (r != null && r != active) roots.add(r);
                }
            }
        } catch (Exception ignored) { }
        return roots;
    }

    private AccessibilityNodeInfo findLiveNode(int nodeId) {
        NodeSnap snap = getNodeSnap(nodeId);
        if (snap == null) return null;
        for (AccessibilityNodeInfo root : interactiveRoots()) {
            AccessibilityNodeInfo found = matchByBounds(root, snap.bounds);
            if (found != null) return found;
        }
        return null;
    }

    private AccessibilityNodeInfo matchByBounds(AccessibilityNodeInfo n, Rect target) {
        if (n == null) return null;
        CharSequence pkg = n.getPackageName();
        if (pkg != null && pkg.toString().equals(getPackageName())
                && n.getViewIdResourceName() != null
                && n.getViewIdResourceName().contains("ody_agent_overlay")) {
            return null;
        }
        Rect r = new Rect();
        n.getBoundsInScreen(r);
        if (Math.abs(r.centerX() - target.centerX()) <= 16
                && Math.abs(r.centerY() - target.centerY()) <= 16
                && Math.abs(r.width() - target.width()) <= 32) {
            return n;
        }
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo found = matchByBounds(n.getChild(i), target);
            if (found != null) return found;
        }
        return null;
    }

    private AccessibilityNodeInfo findFocusedOrEditable(int nodeId) {
        List<AccessibilityNodeInfo> roots = interactiveRoots();
        if (roots.isEmpty()) return null;

        if (nodeId > 0) {
            AccessibilityNodeInfo live = findLiveNode(nodeId);
            if (live != null) {
                if (live.isEditable()) return live;
                AccessibilityNodeInfo childEdit = firstEditable(live);
                if (childEdit != null) return childEdit;
            }
            for (AccessibilityNodeInfo root : roots) {
                AccessibilityNodeInfo focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
                if (focused != null && focused.isEditable()) return focused;
            }
            // Se um nodeId específico foi pedido mas não existe nem está focado, falha de forma limpa
            // em vez de escrever às cegas no primeiro EditText do ecrã.
            return null;
        }

        for (AccessibilityNodeInfo root : roots) {
            AccessibilityNodeInfo focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
            if (focused != null && focused.isEditable()) return focused;
        }
        for (AccessibilityNodeInfo root : roots) {
            AccessibilityNodeInfo f = firstEditable(root);
            if (f != null) return f;
        }
        return null;
    }

    private AccessibilityNodeInfo firstEditable(AccessibilityNodeInfo n) {
        if (n == null) return null;
        if (n.isVisibleToUser() && n.isEditable()) return n;
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo f = firstEditable(n.getChild(i));
            if (f != null) return f;
        }
        return null;
    }

    private void copyToClipboard(String text) {
        try {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("odysseus_agent", text));
        } catch (Exception ignored) { }
    }

    private String appLabel(String pkg) {
        if (pkg == null || pkg.isEmpty()) return "";
        try {
            PackageManager pm = getPackageManager();
            ApplicationInfo ai = pm.getApplicationInfo(pkg, 0);
            return String.valueOf(pm.getApplicationLabel(ai));
        } catch (Exception e) {
            return pkg;
        }
    }

    private static String safeStr(CharSequence cs) {
        return cs == null ? "" : cs.toString().replace('\n', ' ').trim();
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max) + "…";
    }

    private static void sleepQuiet(long ms) {
        try { Thread.sleep(ms); } catch (InterruptedException ignored) { }
    }
}
