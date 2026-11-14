package org.odysseuskit.app;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.media.ExifInterface;
import android.net.Uri;
import android.util.Base64;

import androidx.core.content.FileProvider;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** Tirar foto (câmara do sistema), reduzir para JPEG e enviar ao servidor. */
final class Cam {
    private Cam() {}

    static File newFile(Context c) {
        File d = new File(c.getCacheDir(), "cam");
        d.mkdirs();
        File[] old = d.listFiles();
        if (old != null) for (File f : old) if (System.currentTimeMillis() - f.lastModified() > 3600_000L) f.delete();
        return new File(d, "p" + System.currentTimeMillis() + ".jpg");
    }

    static Uri uri(Context c, File f) {
        return FileProvider.getUriForFile(c, c.getPackageName() + ".fileprovider", f);
    }

    /** Lê a foto, roda conforme o EXIF, limita o lado maior a 1600 px e devolve base64 JPEG. */
    static String toB64(File f) throws Exception {
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(f.getAbsolutePath(), o);
        int s = 1;
        while (Math.max(o.outWidth, o.outHeight) / s > 3200) s *= 2;
        o = new BitmapFactory.Options();
        o.inSampleSize = s;
        Bitmap b = BitmapFactory.decodeFile(f.getAbsolutePath(), o);
        if (b == null) throw new Exception(Tr.t("foto inválida"));
        int rot = 0;
        try {
            int ori = new ExifInterface(f.getAbsolutePath()).getAttributeInt(ExifInterface.TAG_ORIENTATION, 1);
            rot = ori == 6 ? 90 : ori == 3 ? 180 : ori == 8 ? 270 : 0;
        } catch (Exception ignored) {}
        float sc = Math.min(1f, 1600f / Math.max(b.getWidth(), b.getHeight()));
        Matrix m = new Matrix();
        if (sc < 1f) m.postScale(sc, sc);
        if (rot != 0) m.postRotate(rot);
        Bitmap r = Bitmap.createBitmap(b, 0, 0, b.getWidth(), b.getHeight(), m, true);
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        r.compress(Bitmap.CompressFormat.JPEG, 85, bo);
        return Base64.encodeToString(bo.toByteArray(), Base64.NO_WRAP);
    }

    /** POST JSON; devolve o corpo da resposta (mesmo em erro HTTP). */
    static String post(String url, String cookie, String json, int readMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(readMs);
        c.setRequestMethod("POST");
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json");
        if (cookie != null) c.setRequestProperty("Cookie", cookie);
        try (OutputStream os = c.getOutputStream()) { os.write(json.getBytes("UTF-8")); }
        int code = c.getResponseCode();
        InputStream is = code < 400 ? c.getInputStream() : c.getErrorStream();
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[4096]; int n;
        while (is != null && (n = is.read(buf)) > 0) bo.write(buf, 0, n);
        String body = bo.toString("UTF-8");
        if (code >= 400 && !body.startsWith("{")) throw new Exception("HTTP " + code);
        return body;
    }
}
