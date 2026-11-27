package com.canorus.odysseus;

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

/** Tirar foto (câmara do sistema), reduzir para JPEG sem fugas de Bitmap nativo e enviar ao servidor. */
final class Cam {
    private Cam() {}

    static File newFile(Context c) {
        File d = new File(c.getCacheDir(), "cam");
        d.mkdirs();
        File[] old = d.listFiles();
        if (old != null) {
            long now = System.currentTimeMillis();
            for (File f : old) if (now - f.lastModified() > 3600_000L) f.delete();
        }
        return new File(d, "p" + System.currentTimeMillis() + ".jpg");
    }

    static Uri uri(Context c, File f) {
        return FileProvider.getUriForFile(c, c.getPackageName() + ".fileprovider", f);
    }

    /** Lê a foto, roda conforme o EXIF, limita o lado maior a 1600 px, liberta Bitmaps nativos e devolve base64 JPEG. */
    static String toB64(File f) throws Exception {
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(f.getAbsolutePath(), o);
        int s = 1;
        while (Math.max(o.outWidth, o.outHeight) / s > 3200) s *= 2;
        o = new BitmapFactory.Options();
        o.inSampleSize = s;
        Bitmap b = BitmapFactory.decodeFile(f.getAbsolutePath(), o);
        if (b == null) throw new Exception(L.t("foto inválida"));
        Bitmap r = null;
        try {
            int rot = 0;
            try {
                int ori = new ExifInterface(f.getAbsolutePath()).getAttributeInt(ExifInterface.TAG_ORIENTATION, 1);
                rot = ori == 6 ? 90 : ori == 3 ? 180 : ori == 8 ? 270 : 0;
            } catch (Exception ignored) {}
            float sc = Math.min(1f, 1600f / Math.max(b.getWidth(), b.getHeight()));
            if (sc < 1f || rot != 0) {
                Matrix m = new Matrix();
                if (sc < 1f) m.postScale(sc, sc);
                if (rot != 0) m.postRotate(rot);
                r = Bitmap.createBitmap(b, 0, 0, b.getWidth(), b.getHeight(), m, true);
                if (r != b) {
                    b.recycle();
                    b = null;
                }
            } else {
                r = b;
            }
            ByteArrayOutputStream bo = new ByteArrayOutputStream(256 * 1024);
            r.compress(Bitmap.CompressFormat.JPEG, 85, bo);
            return Base64.encodeToString(bo.toByteArray(), Base64.NO_WRAP);
        } finally {
            if (b != null && !b.isRecycled()) b.recycle();
            if (r != null && !r.isRecycled()) r.recycle();
        }
    }

    /** POST JSON; devolve o corpo da resposta (mesmo em erro HTTP) com fecho garantido do socket. */
    static String post(String url, String cookie, String json, int readMs) throws Exception {
        Http.Resp r = Http.request("POST", url, cookie, "application/json", json, 8000, readMs);
        String body = r.text() == null ? "" : r.text();
        if (r.code >= 400 && !body.startsWith("{")) throw new Exception("HTTP " + r.code);
        return body;
    }
}
