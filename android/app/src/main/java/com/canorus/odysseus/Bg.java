package com.canorus.odysseus;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Shared bounded daemon thread pool and network reachability helper.
 * Replaces unbounded `new Thread(...).start()` churn across activities, receivers, and sync tasks.
 */
final class Bg {
    private Bg() { }

    private static final AtomicInteger SEQ = new AtomicInteger(1);
    private static final ThreadPoolExecutor EXEC;

    static {
        ThreadFactory tf = r -> {
            Thread t = new Thread(r, "ody-bg-" + SEQ.getAndIncrement());
            t.setDaemon(true);
            t.setPriority(Thread.NORM_PRIORITY - 1);
            return t;
        };
        EXEC = new ThreadPoolExecutor(1, 4, 30L, TimeUnit.SECONDS, new LinkedBlockingQueue<>(64),
                tf, new ThreadPoolExecutor.DiscardOldestPolicy());
        EXEC.allowCoreThreadTimeOut(true);
    }

    static ExecutorService io() {
        return EXEC;
    }

    static void run(Runnable task) {
        EXEC.execute(task);
    }

    /** Fast local check before waking the cellular/Wi-Fi radio or hanging on VPN timeouts. */
    static boolean isOnline(Context c) {
        if (c == null) return true;
        try {
            ConnectivityManager cm = c.getSystemService(ConnectivityManager.class);
            if (cm == null) return true;
            Network net = cm.getActiveNetwork();
            if (net == null) return false;
            NetworkCapabilities caps = cm.getNetworkCapabilities(net);
            if (caps == null) return false;
            return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                    || caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN);
        } catch (Exception e) {
            return true;
        }
    }
}
