package com.nova.phone;

import android.app.Notification;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class NovaNotificationListener extends NotificationListenerService {
    private static final ExecutorService EXECUTOR = Executors.newSingleThreadExecutor();

    // Message-oriented apps. Add more package names later if desired.
    private static final Set<String> MESSAGE_PACKAGES = new HashSet<>(Arrays.asList(
            "com.google.android.apps.messaging",
            "com.android.mms",
            "com.whatsapp",
            "com.whatsapp.w4b"
    ));

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        String pkg = sbn.getPackageName();
        if (!MESSAGE_PACKAGES.contains(pkg)) return;

        Notification n = sbn.getNotification();
        Bundle extras = n.extras;
        String title = extras != null ? String.valueOf(extras.getCharSequence(Notification.EXTRA_TITLE, "")) : "";
        String text = extras != null ? String.valueOf(extras.getCharSequence(Notification.EXTRA_TEXT, "")) : "";

        if (text.isEmpty()) {
            CharSequence[] lines = extras != null ? extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES) : null;
            if (lines != null && lines.length > 0) text = String.valueOf(lines[lines.length - 1]);
        }

        if (title.isEmpty() && text.isEmpty()) return;

        final String app = appName(pkg);
        final String finalTitle = title;
        final String finalText = text;
        EXECUTOR.execute(() -> postToNova(pkg, app, finalTitle, finalText));
    }

    private void postToNova(String pkg, String app, String title, String text) {
        HttpURLConnection conn = null;
        try {
            JSONObject obj = new JSONObject();
            obj.put("package", pkg);
            obj.put("app", app);
            obj.put("title", title);
            obj.put("text", text);

            URL url = new URL("http://127.0.0.1:8765/notification");
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(2000);
            conn.setReadTimeout(3000);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            byte[] body = obj.toString().getBytes(StandardCharsets.UTF_8);
            conn.setFixedLengthStreamingMode(body.length);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(body);
            }
            conn.getResponseCode();
        } catch (Exception ignored) {
            // NOVA may be closed or the ADB reverse tunnel may not be active.
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private String appName(String pkg) {
        if (pkg.contains("whatsapp")) return "WhatsApp";
        if (pkg.equals("com.google.android.apps.messaging") || pkg.equals("com.android.mms")) return "Messages";
        return pkg;
    }

    public static boolean isEnabled(Context context) {
        String flat = Settings.Secure.getString(context.getContentResolver(), "enabled_notification_listeners");
        if (flat == null) return false;
        return flat.contains(new ComponentName(context, NovaNotificationListener.class).flattenToString());
    }
}
