package com.canorus.odysseus;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ConcurrentHashMap;
import java.util.zip.GZIPInputStream;

/**
 * Leak-free HTTP helper with transparent GZIP compression, HTTP keep-alive connection pooling,
 * ETag / Last-Modified conditional GETs, and guaranteed socket/stream cleanup.
 */
final class Http {
    private Http() { }

    static {
        System.setProperty("http.keepAlive", "true");
        System.setProperty("http.maxConnections", "6");
    }

    static final class Resp {
        final int code;
        final byte[] bytes;
        final boolean notModified;

        Resp(int code, byte[] bytes, boolean notModified) {
            this.code = code;
            this.bytes = bytes;
            this.notModified = notModified;
        }

        String text() {
            return bytes == null ? null : new String(bytes, StandardCharsets.UTF_8);
        }
    }

    private static final class CacheEntry {
        final String etag;
        final String lastModified;
        final byte[] body;

        CacheEntry(String etag, String lastModified, byte[] body) {
            this.etag = etag;
            this.lastModified = lastModified;
            this.body = body;
        }
    }

    private static final ConcurrentHashMap<String, CacheEntry> CACHE = new ConcurrentHashMap<>();

    private static InputStream wrapStream(HttpURLConnection c, InputStream raw) throws Exception {
        if (raw == null) return null;
        String enc = c.getContentEncoding();
        if (enc != null && enc.toLowerCase(java.util.Locale.ROOT).contains("gzip")) {
            return new GZIPInputStream(raw);
        }
        return raw;
    }

    private static void drainQuietly(InputStream is) {
        if (is == null) return;
        try {
            byte[] skip = new byte[2048];
            while (is.read(skip) > 0) { /* drain so keep-alive can reuse socket */ }
        } catch (Exception ignored) {
        } finally {
            try { is.close(); } catch (Exception ignored) { }
        }
    }

    private static byte[] readAll(InputStream is) throws Exception {
        if (is == null) return new byte[0];
        try (InputStream in = is) {
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
            return bo.toByteArray();
        }
    }

    static Resp getConditional(String url, String cookie, int connectMs, int readMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setConnectTimeout(connectMs);
            c.setReadTimeout(readMs);
            c.setRequestProperty("Accept", "application/json");
            c.setRequestProperty("Accept-Encoding", "gzip");
            if (cookie != null && !cookie.isEmpty()) c.setRequestProperty("Cookie", cookie);
            String cacheKey = url + "|" + (cookie == null ? "" : Integer.toHexString(cookie.hashCode()));
            CacheEntry prev = CACHE.get(cacheKey);
            if (prev != null) {
                if (prev.etag != null) c.setRequestProperty("If-None-Match", prev.etag);
                if (prev.lastModified != null) c.setRequestProperty("If-Modified-Since", prev.lastModified);
            }
            int code = c.getResponseCode();
            if (code == HttpURLConnection.HTTP_NOT_MODIFIED && prev != null) {
                drainQuietly(c.getInputStream());
                return new Resp(200, prev.body, true);
            }
            if (code != 200) {
                drainQuietly(c.getErrorStream());
                return new Resp(code, null, false);
            }
            byte[] data = readAll(wrapStream(c, c.getInputStream()));
            String etag = c.getHeaderField("ETag");
            String lm = c.getHeaderField("Last-Modified");
            if ((etag != null || lm != null) && data.length <= 512 * 1024) {
                if (CACHE.size() > 64) CACHE.clear();
                CACHE.put(cacheKey, new CacheEntry(etag, lm, data));
            }
            return new Resp(200, data, false);
        } catch (Exception e) {
            try { drainQuietly(c.getErrorStream()); } catch (Exception ignored) { }
            c.disconnect();
            throw e;
        }
    }

    static String getString(String url, String cookie) throws Exception {
        Resp r = getConditional(url, cookie, 10000, 20000);
        return r.code == 200 ? r.text() : null;
    }

    static byte[] getBytesNoCache(String url, int connectMs, int readMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setConnectTimeout(connectMs);
            c.setReadTimeout(readMs);
            c.setUseCaches(false);
            c.setRequestProperty("Accept-Encoding", "gzip");
            int code = c.getResponseCode();
            if (code != 200) {
                drainQuietly(c.getErrorStream());
                throw new Exception("HTTP " + code);
            }
            return readAll(wrapStream(c, c.getInputStream()));
        } catch (Exception e) {
            c.disconnect();
            throw e;
        }
    }

    static int headOrGetCode(String url, String cookie, int timeoutMs) {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(url).openConnection();
            c.setConnectTimeout(timeoutMs);
            c.setReadTimeout(timeoutMs);
            if (cookie != null && !cookie.isEmpty()) c.setRequestProperty("Cookie", cookie);
            int code = c.getResponseCode();
            drainQuietly(code < 400 ? c.getInputStream() : c.getErrorStream());
            return code;
        } catch (Exception e) {
            if (c != null) c.disconnect();
            return -1;
        }
    }

    static Resp request(String method, String url, String cookie, String contentType, String body, int connectMs, int readMs) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        try {
            c.setRequestMethod(method);
            c.setConnectTimeout(connectMs);
            c.setReadTimeout(readMs);
            c.setRequestProperty("Accept-Encoding", "gzip");
            if (cookie != null && !cookie.isEmpty()) c.setRequestProperty("Cookie", cookie);
            if (contentType != null && !contentType.isEmpty()) c.setRequestProperty("Content-Type", contentType);
            if (body != null) {
                c.setDoOutput(true);
                byte[] payload = body.getBytes(StandardCharsets.UTF_8);
                try (OutputStream os = c.getOutputStream()) {
                    os.write(payload);
                }
            }
            int code = c.getResponseCode();
            InputStream raw = code < 400 ? c.getInputStream() : c.getErrorStream();
            byte[] resp = readAll(wrapStream(c, raw));
            return new Resp(code, resp, false);
        } catch (Exception e) {
            try { drainQuietly(c.getErrorStream()); } catch (Exception ignored) { }
            c.disconnect();
            throw e;
        }
    }
}
