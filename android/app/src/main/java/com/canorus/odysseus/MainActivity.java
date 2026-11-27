package com.canorus.odysseus;

import android.app.DownloadManager;
import android.content.ContentValues;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.view.Window;
import android.webkit.CookieManager;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import android.webkit.MimeTypeMap;
import android.webkit.URLUtil;
import android.webkit.WebView;
import android.widget.Toast;
import androidx.activity.OnBackPressedCallback;
import androidx.core.graphics.ColorUtils;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.WebViewListener;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

public class MainActivity extends BridgeActivity {

    static final String EXTRA_SESSION = "open_session";
    static final String ACTION_NEW_CHAT = "com.canorus.odysseus.NEW_CHAT";
    private Intent pendingIntent;          // share / shortcut / notification waiting for the page
    private boolean pageReady = false;
    private volatile boolean webStreamActive = false;
    private long backgroundSince = 0;
    private boolean unlocked = false;
    private boolean prompting = false;
    private android.view.View lockCover;
    private OnBackPressedCallback backCallback;

    private static final int DEFAULT_BG = Color.parseColor("#282c34");
    private Updater updater;
    private static final String TAILSCALE_PKG = "com.tailscale.ipn";

    // Injected into every page: keeps the system bars in sync with the Odysseus theme
    // (theme.js updates <meta name="theme-color">) and turns blob:/data: downloads,
    // which a plain WebView ignores, into real files saved by the app.
    private static final String INJECT_JS =
        "(function(){" +
        "if(window.__odyApp)return;window.__odyApp=1;" +
        "var N=window.OdysseusNative;if(!N)return;" +
        "function addAndroidSettings(){" +
        "var system=document.querySelector('button[data-settings-tab=system]');" +
        "if(!system||system.parentElement.querySelector('[data-ody-android-settings]'))return;" +
        "var button=document.createElement('button');button.type='button';" +
        "button.className='settings-nav-item';button.setAttribute('data-ody-android-settings','');" +
        "var icon=system.querySelector('svg');if(icon)button.appendChild(icon.cloneNode(true));" +
        "var label=document.createElement('span');label.textContent='Android';button.appendChild(label);" +
        "button.addEventListener('click',function(e){e.stopPropagation();N.openSettings();});" +
        "system.after(button);}" +
        "addAndroidSettings();" +
        "new MutationObserver(addAndroidSettings).observe(document.body,{childList:true,subtree:true});" +
        "var lastC='';" +
        "function bg(){var m=document.querySelector('meta[name=\"theme-color\"]');" +
        "var c=m&&m.getAttribute('content');" +
        "if(!c&&document.body)c=getComputedStyle(document.body).backgroundColor;" +
        "if(c&&c!==lastC){lastC=c;N.setBarColor(c);}}" +
        "bg();" +
        "var meta=document.querySelector('meta[name=\"theme-color\"]');" +
        "var mo=new MutationObserver(bg);" +
        "if(meta)mo.observe(meta,{attributes:true,attributeFilter:['content']});" +
        "else if(document.head)mo.observe(document.head,{childList:true,attributes:true,attributeFilter:['content']});" +
        "var of=window.fetch,st=null;window.fetch=function(u,o){" +
        "var m='GET',url='',tracked=false;" +
        "try{m=((o&&o.method)||(u&&u.method)||'GET').toUpperCase();url=String(u&&u.url||u);" +
        "if(m!=='GET'&&/\\/api\\/(chat|agent|research)/.test(url)){tracked=true;try{N.streamState(true);}catch(e){}}" +
        "}catch(e){}" +
        "var p=of.apply(this,arguments);" +
        "try{" +
        "if(tracked)p.then(function(){setTimeout(function(){try{N.streamState(false);}catch(e){}},2000);},function(){try{N.streamState(false);}catch(e){}});" +
        "if(m!=='GET'&&/\\/api\\/(notes|calendar)/.test(url)){p.then(function(){clearTimeout(st);st=setTimeout(function(){try{N.syncNotes();}catch(e){}},1500);});}" +
        "}catch(e){}return p;};" +
        "var blobs=new Map();var oc=URL.createObjectURL;" +
        "URL.createObjectURL=function(o){var u=oc.apply(URL,arguments);try{if(o instanceof Blob)blobs.set(u,o);}catch(e){}return u;};" +
        "function save(name,blob){var r=new FileReader();r.onload=function(){" +
        "var s=String(r.result);N.saveFile(s.substring(s.indexOf(',')+1),name||'download',blob.type||'application/octet-stream');};" +
        "r.readAsDataURL(blob);}" +
        "function handle(a){var h=a.href||'';if(!a.hasAttribute('download')&&h.indexOf('blob:')!==0)return false;" +
        "var name=a.getAttribute('download')||'';" +
        "if(h.indexOf('blob:')===0){var b=blobs.get(h);" +
        "if(b){save(name,b);return true;}" +
        "fetch(h).then(function(r){return r.blob();}).then(function(b){save(name,b);});return true;}" +
        "if(h.indexOf('data:')===0){fetch(h).then(function(r){return r.blob();}).then(function(b){save(name,b);});return true;}" +
        "return false;}" +
        "var ck=HTMLAnchorElement.prototype.click;" +
        "HTMLAnchorElement.prototype.click=function(){if(handle(this))return;return ck.apply(this,arguments);};" +
        "document.addEventListener('click',function(e){var a=e.target&&e.target.closest&&e.target.closest('a');" +
        "if(a&&handle(a))e.preventDefault();},true);" +
        "function syncNav(){setTimeout(function(){try{N.syncBackState();}catch(e){}},50);}" +
        "window.addEventListener('popstate',syncNav);window.addEventListener('hashchange',syncNav);" +
        "var ps=history.pushState,rs=history.replaceState;" +
        "history.pushState=function(){var r=ps.apply(this,arguments);syncNav();return r;};" +
        "history.replaceState=function(){var r=rs.apply(this,arguments);syncNav();return r;};" +
        "syncNav();" +
        "})();";

    @Override
    public void onCreate(Bundle savedInstanceState) {
        AppSettings.applyServer(this);
        if (!AppSettings.setupDone(this)) {
            this.config = new com.getcapacitor.CapConfig.Builder(this).create();
            super.onCreate(savedInstanceState);
            startActivity(new android.content.Intent(this, SetupActivity.class));
            finish();
            return;
        }
        this.config = new com.getcapacitor.CapConfig.Builder(this).setServerUrl(NoteSync.SITE).setErrorPath("error.html")
                .setAppendedUserAgentString("OdysseusApp").setBackgroundColor("#282c34").create();
        super.onCreate(savedInstanceState);

        // Content sits between the status bar and the navigation bar (no overlap).
        WindowCompat.setDecorFitsSystemWindows(getWindow(), true);
        applyBarColor(DEFAULT_BG);

        updater = new Updater(this);

        WebView webView = bridge.getWebView();
        webView.setBackgroundColor(DEFAULT_BG);
        installNativeBridge(webView);
        webView.setDownloadListener(this::onHttpDownload);

        bridge.addWebViewListener(new WebViewListener() {
            @Override
            public void onPageLoaded(WebView view) {
                view.evaluateJavascript(INJECT_JS, null);
                pageReady = true;
                refreshBackCallback();
                if (pendingIntent != null) { Intent i = pendingIntent; pendingIntent = null; handleIntent(i); }
            }
        });

        pendingIntent = getIntent();

        // Dynamic predictive back (Android 14/15/16+): enabled only when WebView has history to go back,
        // allowing Android's native fluid home-screen shrink animation at the root page.
        backCallback = new OnBackPressedCallback(false) {
            @Override
            public void handleOnBackPressed() {
                WebView wv = bridge != null ? bridge.getWebView() : null;
                if (wv != null && wv.canGoBack()) {
                    wv.goBack();
                    wv.postDelayed(MainActivity.this::refreshBackCallback, 80);
                } else {
                    setEnabled(false);
                    moveTaskToBack(true);
                }
            }
        };
        getOnBackPressedDispatcher().addCallback(this, backCallback);
    }

    // While on screen, check for shared files every 60 s (plus immediately on onResume).
    private final android.os.Handler fsHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    private final Runnable fsTick = new Runnable() {
        @Override public void run() {
            FileShare.prompt(MainActivity.this);
            fsHandler.postDelayed(this, 60000);
        }
    };

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (pageReady) handleIntent(intent); else pendingIntent = intent;
    }

    /** Notification "open chat", launcher shortcuts and "Partilhar com o Odysseus". */
    private void handleIntent(Intent in) {
        if (in == null) return;
        String action = in.getAction() == null ? "" : in.getAction();
        WebView wv = bridge.getWebView();
        String session = in.getStringExtra(EXTRA_SESSION);
        if (session != null && session.matches("[A-Za-z0-9-]+")) {
            in.removeExtra(EXTRA_SESSION);
            // Full reload (a hash-only change is ignored by the single-page app).
            wv.loadUrl(NoteSync.SITE + "/?open=" + System.currentTimeMillis() + "#" + session);
            return;
        }
        if (ACTION_NEW_CHAT.equals(action)) {
            in.setAction(null);
            wv.evaluateJavascript(Share.NEW_CHAT_JS, null);
            return;
        }
        if (Intent.ACTION_SEND.equals(action) || Intent.ACTION_SEND_MULTIPLE.equals(action)) {
            in.setAction(null);
            Share.deliver(this, wv, in);
        }
    }

    private void refreshBackCallback() {
        if (backCallback == null || bridge == null) return;
        WebView wv = bridge.getWebView();
        backCallback.setEnabled(wv != null && wv.canGoBack());
    }

    private void syncSecureFlag() {
        getWindow().clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
    }

    private long lastHealth = 0;

    @Override
    public void onResume() {
        super.onResume();
        try {
            WebView wv = bridge != null ? bridge.getWebView() : null;
            if (wv != null) {
                wv.onResume();
                wv.resumeTimers();
            }
        } catch (Exception ignored) { }
        try {
            String ck = android.webkit.CookieManager.getInstance().getCookie(bridge.getServerUrl());
            java.util.regex.Matcher km = java.util.regex.Pattern.compile("(?:^|;\\s*)kitlang=(en|pt)\\b").matcher(ck == null ? "" : ck);
            if (km.find()) L.set(km.group(1));
        } catch (Exception ignored) { }
        syncSecureFlag();
        refreshBackCallback();
        checkLock();
        final android.content.Context appCtx = getApplicationContext();
        Bg.run(() -> { Outbox.flush(appCtx); SnsListener.scanInbox(appCtx); });
        try {
            long now = System.currentTimeMillis();
            if (HealthSync.supported() && AppSettings.sp(this).getBoolean("health_sync", false)) {
                HealthWorker.schedule(appCtx);
                if (HealthSync.hasPerm(this) && now - lastHealth > 30 * 60_000L) {
                    lastHealth = now;
                    Bg.run(() -> { try { HealthSync.sync(appCtx); } catch (Throwable ignored) { } });
                }
            }
        } catch (Throwable ignored) { }
        if (updater != null) updater.onResume();
        FileShare.current = this;
        FileShare.prompt(this);
        fsHandler.removeCallbacks(fsTick);
        fsHandler.postDelayed(fsTick, 60000);
        SyncService.appVisible = true;
        NoteSync.schedule(this);
        NoteSync.enqueueImmediateWork(this);
        SyncService.startIfNeeded(this);
        askPermissionsOnce();
    }

    // ---- Fingerprint / screen-lock gate ----
    private void checkLock() {
        if (prompting) return;
        boolean expired = !unlocked || (backgroundSince > 0
                && System.currentTimeMillis() - backgroundSince > AppSettings.lockMinutes(this) * 60_000L);
        backgroundSince = 0;
        if (!AppSettings.lockEnabled(this) || !expired) return;
        int auth = androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_WEAK
                | androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL;
        if (androidx.biometric.BiometricManager.from(this).canAuthenticate(auth)
                != androidx.biometric.BiometricManager.BIOMETRIC_SUCCESS) { unlocked = true; return; }
        unlocked = false;
        prompting = true;
        showCover(true);
        androidx.biometric.BiometricPrompt bp = new androidx.biometric.BiometricPrompt(this,
                androidx.core.content.ContextCompat.getMainExecutor(this),
                new androidx.biometric.BiometricPrompt.AuthenticationCallback() {
                    @Override public void onAuthenticationSucceeded(androidx.biometric.BiometricPrompt.AuthenticationResult r) {
                        prompting = false; unlocked = true; showCover(false);
                    }
                    @Override public void onAuthenticationError(int code, CharSequence msg) {
                        prompting = false;
                        if (!unlocked) moveTaskToBack(true);
                    }
                });
        bp.authenticate(new androidx.biometric.BiometricPrompt.PromptInfo.Builder()
                .setTitle("Desbloquear o Odysseus").setAllowedAuthenticators(auth).build());
    }

    private void showCover(boolean on) {
        android.view.ViewGroup root = (android.view.ViewGroup) getWindow().getDecorView();
        if (on && lockCover == null) {
            lockCover = new android.widget.FrameLayout(this);
            lockCover.setBackgroundColor(DEFAULT_BG);
            lockCover.setClickable(true);
            android.widget.ImageView logo = new android.widget.ImageView(this);
            logo.setImageResource(R.mipmap.ic_launcher_foreground);
            ((android.widget.FrameLayout) lockCover).addView(logo, new android.widget.FrameLayout.LayoutParams(
                    android.view.ViewGroup.LayoutParams.WRAP_CONTENT, android.view.ViewGroup.LayoutParams.WRAP_CONTENT, android.view.Gravity.CENTER));
            lockCover.setOnClickListener(v -> checkLockAgain());
            root.addView(lockCover, new android.view.ViewGroup.LayoutParams(-1, -1));
        } else if (!on && lockCover != null) {
            root.removeView(lockCover);
            lockCover = null;
        }
    }

    private void checkLockAgain() { unlocked = false; backgroundSince = 0; checkLock(); }

    @Override
    public void onPause() {
        syncSecureFlag();
        if (unlocked) backgroundSince = System.currentTimeMillis();
        if (AppSettings.lockEnabled(this) && AppSettings.lockMinutes(this) == 0) {
            showCover(true);
        }
        if (FileShare.current == this) FileShare.current = null;
        fsHandler.removeCallbacks(fsTick);
        SyncService.appVisible = false;
        if (webStreamActive) {
            // Keep watching the active reply in the background until it finishes
            SyncService.watchActiveStream(this);
        } else {
            try {
                WebView wv = bridge != null ? bridge.getWebView() : null;
                if (wv != null) {
                    wv.onPause();
                    wv.pauseTimers();
                }
            } catch (Exception ignored) { }
        }
        // Persist the session cookie now: WorkManager and reminders read it in the background.
        Bg.run(() -> { try { CookieManager.getInstance().flush(); } catch (Exception ignored) { } });
        super.onPause();
    }

    private boolean permDialogOpen = false;

    /** Notifications (Android 13+) and calendar in one system dialog; battery exemption afterwards. */
    private void askPermissionsOnce() {
        if (permDialogOpen) return;
        try {
            android.content.SharedPreferences sp = getSharedPreferences(NoteSync.PREFS, MODE_PRIVATE);
            java.util.List<String> want = new java.util.ArrayList<>();
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED)
                want.add(android.Manifest.permission.POST_NOTIFICATIONS);
            if (checkSelfPermission(android.Manifest.permission.READ_SMS) != android.content.pm.PackageManager.PERMISSION_GRANTED)
                want.add(android.Manifest.permission.READ_SMS);
            if (!CalendarSync.hasPerm(this)) {
                want.add(android.Manifest.permission.READ_CALENDAR);
                want.add(android.Manifest.permission.WRITE_CALENDAR);
            }
            if (!want.isEmpty() && sp.getInt("perm_asked", 0) < 2) {
                sp.edit().putInt("perm_asked", sp.getInt("perm_asked", 0) + 1).apply();
                permDialogOpen = true;
                requestPermissions(want.toArray(new String[0]), 4712);
                return;
            }
        } catch (Exception ignored) { }
        askBatteryOnce();
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
        super.onRequestPermissionsResult(code, perms, res);
        if (code == 4712) {
            permDialogOpen = false;
            Bg.run(() -> SnsListener.scanInbox(getApplicationContext()));
            NoteSync.syncNow(this);
            askBatteryOnce();
        }
    }

    private void applyBarColor(int color) {
        Window w = getWindow();
        w.setStatusBarColor(color);
        w.setNavigationBarColor(color);
        if (Build.VERSION.SDK_INT >= 29) {
            w.setNavigationBarContrastEnforced(false);
            w.setStatusBarContrastEnforced(false);
        }
        boolean light = ColorUtils.calculateLuminance(color) > 0.5;
        WindowInsetsControllerCompat ic = WindowCompat.getInsetsController(w, w.getDecorView());
        ic.setAppearanceLightStatusBars(light);
        ic.setAppearanceLightNavigationBars(light);
        w.getDecorView().setBackgroundColor(color);
    }

    private static Integer parseCssColor(String c) {
        if (c == null) return null;
        c = c.trim();
        try {
            if (c.startsWith("#")) {
                if (c.length() == 4) {
                    c = "#" + c.charAt(1) + c.charAt(1) + c.charAt(2) + c.charAt(2) + c.charAt(3) + c.charAt(3);
                }
                return Color.parseColor(c);
            }
            if (c.startsWith("rgb")) {
                String[] p = c.substring(c.indexOf('(') + 1, c.indexOf(')')).split("[,\\s/]+");
                int r = Math.round(Float.parseFloat(p[0]));
                int g = Math.round(Float.parseFloat(p[1]));
                int b = Math.round(Float.parseFloat(p[2]));
                if (p.length > 3 && Float.parseFloat(p[3]) == 0f) return null; // transparent
                return Color.rgb(r, g, b);
            }
            return Color.parseColor(c);
        } catch (Exception e) {
            return null;
        }
    }

    // Normal http(s) downloads (Content-Disposition: attachment): hand them to Android's
    // download manager with the session cookies so authenticated files work.
    private void onHttpDownload(String url, String userAgent, String contentDisposition, String mimeType, long length) {
        if (url.startsWith("blob:") || url.startsWith("data:")) return; // handled in JS
        try {
            String name = URLUtil.guessFileName(url, contentDisposition, mimeType);
            DownloadManager.Request req = new DownloadManager.Request(Uri.parse(url));
            req.setMimeType(mimeType);
            String cookies = CookieManager.getInstance().getCookie(url);
            if (cookies != null) req.addRequestHeader("Cookie", cookies);
            req.addRequestHeader("User-Agent", userAgent);
            req.setTitle(name);
            req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
            ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(req);
            Toast.makeText(this, "A transferir " + name, Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, L.t("Falha na transferência: ") + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private void saveBytes(byte[] data, String name, String mime) throws Exception {
        if (mime == null || mime.isEmpty()) mime = "application/octet-stream";
        if (name == null || name.trim().isEmpty()) {
            String ext = MimeTypeMap.getSingleton().getExtensionFromMimeType(mime);
            name = "odysseus-" + System.currentTimeMillis() + (ext != null ? "." + ext : "");
        }
        name = name.replaceAll("[\\\\/:*?\"<>|]", "_");
        if (Build.VERSION.SDK_INT >= 29) {
            ContentValues v = new ContentValues();
            v.put(MediaStore.Downloads.DISPLAY_NAME, name);
            v.put(MediaStore.Downloads.MIME_TYPE, mime);
            v.put(MediaStore.Downloads.IS_PENDING, 1);
            Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
            if (uri == null) throw new Exception("MediaStore insert failed");
            try (OutputStream os = getContentResolver().openOutputStream(uri)) {
                os.write(data);
            }
            v.clear();
            v.put(MediaStore.Downloads.IS_PENDING, 0);
            getContentResolver().update(uri, v, null, null);
        } else {
            File dir = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
            try (FileOutputStream os = new FileOutputStream(new File(dir, name))) {
                os.write(data);
            }
        }
        final String shown = name;
        runOnUiThread(() -> Toast.makeText(this, L.t("Guardado em Transferências: ") + shown, Toast.LENGTH_LONG).show());
    }

    // ---- Voz (botão "Ouvir" da tradução dentro do Odysseus) ----
    private android.speech.tts.TextToSpeech tts;
    private boolean ttsReady = false;

    private void speakText(String text, String lang) {
        if (text == null || text.trim().isEmpty()) return;
        if (tts == null) {
            tts = new android.speech.tts.TextToSpeech(getApplicationContext(), st -> {
                ttsReady = st == android.speech.tts.TextToSpeech.SUCCESS;
                if (ttsReady) speakText(text, lang);
                else { tts = null; Toast.makeText(this, L.t("Voz indisponível neste telemóvel"), Toast.LENGTH_LONG).show(); }
            });
            return;
        }
        if (!ttsReady) return;
        java.util.Locale loc = java.util.Locale.forLanguageTag(lang == null || lang.isEmpty() ? "pt-PT" : lang);
        int r = tts.setLanguage(loc);
        if (r == android.speech.tts.TextToSpeech.LANG_MISSING_DATA || r == android.speech.tts.TextToSpeech.LANG_NOT_SUPPORTED) {
            r = tts.setLanguage(new java.util.Locale(loc.getLanguage()));
            if (r == android.speech.tts.TextToSpeech.LANG_MISSING_DATA || r == android.speech.tts.TextToSpeech.LANG_NOT_SUPPORTED) {
                Toast.makeText(this, L.t("Falta a voz deste idioma. Instala-a em Definições > Texto para voz."), Toast.LENGTH_LONG).show();
                return;
            }
        }
        tts.speak(text, android.speech.tts.TextToSpeech.QUEUE_FLUSH, null, "ody");
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != 4713) return;
        String t = "";
        if (res == RESULT_OK && data != null) {
            java.util.ArrayList<String> l = data.getStringArrayListExtra(android.speech.RecognizerIntent.EXTRA_RESULTS);
            if (l != null && !l.isEmpty()) t = l.get(0);
        }
        bridge.getWebView().evaluateJavascript("window.__odyDictated&&window.__odyDictated(" + org.json.JSONObject.quote(t) + ")", null);
    }

    @Override
    public void onDestroy() {
        try { if (tts != null) tts.shutdown(); } catch (Exception ignored) { }
        super.onDestroy();
    }

    private void askBatteryOnce() {
        try {
            android.content.SharedPreferences sp = getSharedPreferences(NoteSync.PREFS, MODE_PRIVATE);
            android.os.PowerManager pm = (android.os.PowerManager) getSystemService(POWER_SERVICE);
            if (AppSettings.batterySaver(this) || sp.getBoolean("battery_asked", false) || pm.isIgnoringBatteryOptimizations(getPackageName())) return;
            sp.edit().putBoolean("battery_asked", true).apply();
            startActivity(new Intent(android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                    Uri.parse("package:" + getPackageName())));
        } catch (Exception ignored) { }
    }

    private void installNativeBridge(WebView webView) {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)
                || !WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) return;
        java.net.URI server = java.net.URI.create(NoteSync.SITE);
        String host = server.getHost();
        String scheme = server.getScheme();
        if (host == null || !("https".equals(scheme) || "http".equals(scheme))) return;
        String origin = scheme + "://" + host + (server.getPort() < 0 ? "" : ":" + server.getPort());
        java.util.Set<String> allowed = java.util.Collections.singleton(origin);
        NativeBridge nativeApi = new NativeBridge();
        WebViewCompat.addWebMessageListener(webView, "OdysseusTransport", allowed,
                (view, message, sourceOrigin, isMainFrame, reply) -> {
            if (!isMainFrame || message.getType() != androidx.webkit.WebMessageCompat.TYPE_STRING) return;
            try {
                org.json.JSONArray args = new org.json.JSONArray(message.getData());
                switch (args.getString(0)) {
                case "setTheme": nativeApi.setTheme(args.getString(1)); break;
                case "setBarColor": nativeApi.setBarColor(args.getString(1)); break;
                case "saveFile": nativeApi.saveFile(args.getString(1), args.getString(2), args.getString(3)); break;
                case "sendMail": nativeApi.sendMail(args.getString(1), args.getString(2)); break;
                case "sendWhatsApp": nativeApi.sendWhatsApp(args.getString(1)); break;
                case "shareText": nativeApi.shareText(args.getString(1), args.getString(2)); break;
                case "syncBackState": nativeApi.syncBackState(); break;
                case "streamState": nativeApi.streamState(args.getBoolean(1)); break;
                case "syncNotes": nativeApi.syncNotes(); break;
                case "openTailscale": nativeApi.openTailscale(); break;
                case "checkUpdate": nativeApi.checkUpdate(); break;
                case "healthSync": nativeApi.healthSync(); break;
                case "openSettings": nativeApi.openSettings(); break;
                case "openTranslator": nativeApi.openTranslator(); break;
                case "speak": nativeApi.speak(args.getString(1), args.getString(2)); break;
                case "dictate": nativeApi.dictate(args.getString(1)); break;
                case "setLanguage": nativeApi.setLanguage(args.getString(1)); break;
                case "stopSpeak": nativeApi.stopSpeak(); break;
                case "reload": nativeApi.reload(); break;
                case "startAgent": nativeApi.startAgent(args.getString(1)); break;
                case "stopAgent": nativeApi.stopAgent(); break;
                case "setAgentToken": nativeApi.setAgentToken(args.getString(1), args.optString(2, "")); break;
                }
            } catch (org.json.JSONException ignored) {
                // Ignore malformed messages.
            }
        });
        String script = "if(window===window.top){const api={};"
                + "'setTheme setBarColor saveFile sendMail sendWhatsApp shareText syncBackState streamState syncNotes openTailscale checkUpdate healthSync openSettings openTranslator speak dictate setLanguage stopSpeak reload startAgent stopAgent setAgentToken'.split(' ').forEach(k=>api[k]=(...a)=>OdysseusTransport.postMessage(JSON.stringify([k,...a])));"
                + "api.appVersion=()=>" + org.json.JSONObject.quote(nativeApi.appVersion()) + ";"
                + "api.getUnifiedPushEndpoint=()=>" + org.json.JSONObject.quote(nativeApi.getUnifiedPushEndpoint()) + ";"
                + "window.OdysseusNative=api;}";
        WebViewCompat.addDocumentStartJavaScript(webView, script, allowed);
        webView.loadUrl(NoteSync.SITE);
    }

    private class NativeBridge {
        public void setTheme(String name) {
            AppSettings.sp(MainActivity.this).edit().putString("ui_theme", "ryoku".equals(name) ? "ryoku" : "").apply();
        }
        public void setBarColor(String css) {
            final Integer c = parseCssColor(css);
            if (c == null) return;
            runOnUiThread(() -> {
                applyBarColor(c);
                WebView wv = bridge.getWebView();
                if (wv != null) wv.setBackgroundColor(c);
            });
        }

        public void saveFile(String base64, String name, String mime) {
            try {
                saveBytes(Base64.decode(base64, Base64.DEFAULT), name, mime);
            } catch (Exception e) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, L.t("Não foi possível guardar: ") + e.getMessage(), Toast.LENGTH_LONG).show());
            }
        }

        // Enviar uma mensagem escrita no chat: abre o seletor de apps do Android (como a app do Claude).
        public void sendMail(String subject, String body) {
            runOnUiThread(() -> {
                try {
                    Intent i = new Intent(Intent.ACTION_SENDTO, Uri.parse("mailto:"));
                    i.putExtra(Intent.EXTRA_SUBJECT, subject == null ? "" : subject);
                    i.putExtra(Intent.EXTRA_TEXT, body == null ? "" : body);
                    startActivity(Intent.createChooser(i, L.t("Enviar email com…")));
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, L.t("Não encontrei uma app de email"), Toast.LENGTH_SHORT).show();
                }
            });
        }

        public void sendWhatsApp(String text) {
            runOnUiThread(() -> {
                try {
                    String[] pkgs = {"com.whatsapp", "com.whatsapp.w4b"};
                    java.util.List<Intent> targets = new java.util.ArrayList<>();
                    for (String pk : pkgs) {
                        try {
                            getPackageManager().getPackageInfo(pk, 0);
                            Intent t = new Intent(Intent.ACTION_SEND);
                            t.setType("text/plain"); t.setPackage(pk);
                            t.putExtra(Intent.EXTRA_TEXT, text == null ? "" : text);
                            targets.add(t);
                        } catch (Exception ignored) { }
                    }
                    if (targets.isEmpty()) {
                        Toast.makeText(MainActivity.this, L.t("WhatsApp não instalado neste dispositivo"), Toast.LENGTH_SHORT).show();
                    } else if (targets.size() == 1) {
                        startActivity(targets.get(0));
                    } else {
                        Intent chooser = Intent.createChooser(targets.remove(0), L.t("Enviar com o WhatsApp…"));
                        chooser.putExtra(Intent.EXTRA_INITIAL_INTENTS, targets.toArray(new Intent[0]));
                        startActivity(chooser);
                    }
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, L.t("Não consegui abrir o WhatsApp"), Toast.LENGTH_SHORT).show();
                }
            });
        }

        public void shareText(String subject, String text) {
            runOnUiThread(() -> {
                try {
                    Intent i = new Intent(Intent.ACTION_SEND);
                    i.setType("text/plain");
                    if (subject != null && !subject.isEmpty()) i.putExtra(Intent.EXTRA_SUBJECT, subject);
                    i.putExtra(Intent.EXTRA_TEXT, text == null ? "" : text);
                    startActivity(Intent.createChooser(i, L.t("Partilhar com…")));
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, L.t("Não consegui partilhar"), Toast.LENGTH_SHORT).show();
                }
            });
        }

        public void syncBackState() {
            runOnUiThread(MainActivity.this::refreshBackCallback);
        }

        public String getUnifiedPushEndpoint() {
            return AppSettings.sp(MainActivity.this).getString("unifiedpush_endpoint", "");
        }

        public void streamState(boolean active) {
            webStreamActive = active;
        }

        public void syncNotes() {
            NoteSync.syncNow(MainActivity.this);
        }

        public void openTailscale() {
            runOnUiThread(() -> {
                Intent i = getPackageManager().getLaunchIntentForPackage(TAILSCALE_PKG);
                if (i == null) {
                    i = new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + TAILSCALE_PKG));
                }
                try {
                    startActivity(i);
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, L.t("Tailscale não encontrado"), Toast.LENGTH_SHORT).show();
                }
            });
        }

        public void checkUpdate() {
            runOnUiThread(() -> updater.check(true));
        }

        public String appVersion() {
            return String.valueOf(updater.installedCode());
        }

        public void healthSync() {
            runOnUiThread(() -> {
                if (!HealthSync.supported()) { new android.app.AlertDialog.Builder(MainActivity.this).setMessage(L.t("Precisa do Android 14 ou superior.")).setPositiveButton("OK", null).show(); return; }
                if (!HealthSync.hasPerm(MainActivity.this)) { startActivity(new Intent(MainActivity.this, SettingsActivity.class)); return; }
                android.widget.Toast.makeText(MainActivity.this, "…", android.widget.Toast.LENGTH_SHORT).show();
                Bg.run(() -> {
                    String r;
                    try { HealthSync.sync(getApplicationContext()); r = HealthSync.result; } catch (Throwable t) { r = String.valueOf(t); }
                    final String rr = r;
                    runOnUiThread(() -> new android.app.AlertDialog.Builder(MainActivity.this).setMessage(rr.startsWith("Enviado ao Gym: ") ? L.t("Enviado ao Gym: ") + rr.substring(16) : L.t(rr)).setPositiveButton("OK", null).show());
                });
            });
        }

        public void openSettings() {
            runOnUiThread(() -> startActivity(new Intent(MainActivity.this, SettingsActivity.class)));
        }

        public void openTranslator() {
            runOnUiThread(() -> startActivity(new Intent(MainActivity.this, TranslateActivity.class)));
        }

        public void speak(String text, String lang) {
            runOnUiThread(() -> speakText(text, lang));
        }

        public void dictate(String lang) {
            runOnUiThread(() -> {
                Intent r = new Intent(android.speech.RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                        .putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE_MODEL, android.speech.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                if (lang != null && !lang.isEmpty()) r.putExtra(android.speech.RecognizerIntent.EXTRA_LANGUAGE, lang);
                try { startActivityForResult(r, 4713); }
                catch (Exception e) {
                    String lg = lang == null ? "" : lang.split("[-_]")[0];
                    Voice.listen(MainActivity.this, lg, txt -> bridge.getWebView().evaluateJavascript(
                            "window.__odyDictated&&window.__odyDictated(" + org.json.JSONObject.quote(txt) + ")", null));
                }
            });
        }

        public void setLanguage(String l) {
            L.set(l);
        }

        public void stopSpeak() {
            runOnUiThread(() -> { try { if (tts != null) tts.stop(); } catch (Exception ignored) { } });
        }

        public void reload() {
            runOnUiThread(() -> bridge.getWebView().loadUrl(bridge.getServerUrl()));
        }

        public void startAgent(String goal) {
            runOnUiThread(() -> startActivity(
                    new Intent(MainActivity.this, AgentPromptActivity.class).putExtra("goal", goal)));
        }

        public void stopAgent() {
            AgentService.stopAgent(MainActivity.this);
        }

        public void setAgentToken(String token, String headerName) {
            android.content.SharedPreferences.Editor ed = AppSettings.sp(MainActivity.this).edit();
            if (token != null) ed.putString("agent_token", token.trim());
            if (headerName != null && !headerName.trim().isEmpty()) {
                ed.putString("agent_auth_header", headerName.trim());
            }
            ed.apply();
        }
    }
}
