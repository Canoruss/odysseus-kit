package com.canorus.odysseus;

import android.app.Activity;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.provider.OpenableColumns;
import android.util.Base64;
import android.webkit.WebView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.ArrayList;

/** "Partilhar com o Odysseus": opens a new chat with the shared text and/or files attached. */
final class Share {
    private Share() { }

    private static final long MAX_BYTES = 25L * 1024 * 1024;

    // Waits for the chat UI, starts a new chat. Used alone by the L.t("Novo chat") shortcut.
    static final String NEW_CHAT_JS =
        "(function(){var n=0;(function go(){var m=document.getElementById('message');" +
        "if(!m){if(n++<75)return setTimeout(go,200);return;}" +
        "var b=document.getElementById('sidebar-new-chat-btn')||document.getElementById('rail-new-session');" +
        "if(b)b.click();setTimeout(function(){try{m.focus();}catch(e){}},400);})();})();";

    // window.__odyShare({text, files:[{name,type,b64}]}): new chat, fill the box, attach files.
    private static final String SHARE_JS =
        "window.__odyShare=function(p){var n=0;(function go(){var m=document.getElementById('message');" +
        "if(!m){if(n++<75)return setTimeout(go,200);return;}" +
        "var b=document.getElementById('sidebar-new-chat-btn')||document.getElementById('rail-new-session');" +
        "if(b)b.click();" +
        "setTimeout(function(){" +
        " if(p.text){m.value=p.text;m.dispatchEvent(new Event('input',{bubbles:true}));}" +
        " if(p.files&&p.files.length){var dt=new DataTransfer();p.files.forEach(function(f){" +
        "  var bin=atob(f.b64),a=new Uint8Array(bin.length);for(var i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i);" +
        "  dt.items.add(new File([a],f.name,{type:f.type||'application/octet-stream'}));});" +
        "  var fi=document.getElementById('file-input');if(fi){fi.files=dt.files;fi.dispatchEvent(new Event('change',{bubbles:true}));}}" +
        " try{m.focus();}catch(e){}" +
        "},600);})();};";

    static void deliver(Activity act, WebView wv, Intent in) {
        String text = in.getStringExtra(Intent.EXTRA_TEXT);
        String subject = in.getStringExtra(Intent.EXTRA_SUBJECT);
        if (subject != null && text != null && !text.contains(subject)) text = subject + "\n" + text;
        ArrayList<Uri> uris = new ArrayList<>();
        if (Intent.ACTION_SEND_MULTIPLE.equals(in.getAction())) {
            ArrayList<Uri> l = in.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (l != null) uris.addAll(l);
        } else {
            Uri u = in.getParcelableExtra(Intent.EXTRA_STREAM);
            if (u != null) uris.add(u);
        }
        final String shareText = text;
        Bg.run(() -> {
            try {
                JSONObject p = new JSONObject();
                if (shareText != null) p.put("text", shareText);
                JSONArray files = new JSONArray();
                for (Uri u : uris) {
                    String name = displayName(act, u);
                    String type = act.getContentResolver().getType(u);
                    byte[] data = read(act, u);
                    if (data == null) {
                        toast(act, L.t("Ficheiro demasiado grande (máx. 25 MB): ") + name);
                        continue;
                    }
                    files.put(new JSONObject().put("name", name).put("type", type == null ? "" : type)
                            .put("b64", Base64.encodeToString(data, Base64.NO_WRAP)));
                }
                p.put("files", files);
                String js = SHARE_JS + "window.__odyShare(" + p + ");";
                act.runOnUiThread(() -> wv.evaluateJavascript(js, null));
            } catch (Exception e) {
                toast(act, L.t("Não foi possível partilhar: ") + e.getMessage());
            }
        });
    }

    private static String displayName(Activity act, Uri u) {
        try (Cursor c = act.getContentResolver().query(u, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst() && c.getString(0) != null) return c.getString(0);
        } catch (Exception ignored) { }
        String s = u.getLastPathSegment();
        return s == null ? L.t("ficheiro") : s;
    }

    private static byte[] read(Activity act, Uri u) throws Exception {
        try (InputStream in = act.getContentResolver().openInputStream(u)) {
            if (in == null) throw new Exception(L.t("não consegui abrir o ficheiro"));
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[64 * 1024];
            int n;
            long total = 0;
            while ((n = in.read(buf)) > 0) {
                total += n;
                if (total > MAX_BYTES) return null;
                bo.write(buf, 0, n);
            }
            return bo.toByteArray();
        }
    }

    private static void toast(Activity a, String m) {
        a.runOnUiThread(() -> Toast.makeText(a, m, Toast.LENGTH_LONG).show());
    }
}
