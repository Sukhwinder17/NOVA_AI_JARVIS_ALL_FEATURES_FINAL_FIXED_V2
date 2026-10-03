package com.nova.phone;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.SystemClock;

import org.json.JSONArray;
import org.json.JSONObject;

public final class NovaSmsScheduler {
    private static final String PREFS = "nova_scheduled_sms";
    private static final String KEY_ITEMS = "items";

    private NovaSmsScheduler() {}

    public static boolean canScheduleExact(Context context) {
        if (Build.VERSION.SDK_INT < 31) return true;
        AlarmManager alarms = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        return alarms != null && alarms.canScheduleExactAlarms();
    }

    public static void schedule(Context context, String requestId, String recipient,
                                  String message, long triggerAtMillis, long delayMs) {
        if (!canScheduleExact(context)) {
            throw new SecurityException("SCHEDULE_EXACT_ALARM access is not enabled.");
        }

        try {
            JSONArray items = readItems(context);
            JSONArray updated = new JSONArray();

            for (int i = 0; i < items.length(); i++) {
                JSONObject old = items.optJSONObject(i);
                if (old != null && requestId.equals(old.optString("request_id"))) continue;
                if (old != null) updated.put(old);
            }

            JSONObject item = new JSONObject();
            item.put("request_id", requestId);
            item.put("recipient", recipient);
            item.put("message", message);
            item.put("trigger_at", triggerAtMillis);
            updated.put(item);

            writeItems(context, updated);

            // Use elapsed realtime for the initial schedule. This is immune to
            // laptop/phone wall-clock differences, so an SMS cannot fire early
            // because the two devices have different clocks.
            if (delayMs > 0L) {
                armAfterDelay(context, requestId, delayMs);
            } else {
                armAtWallClock(context, requestId, triggerAtMillis);
            }
        } catch (SecurityException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("Could not save SMS schedule.", e);
        }
    }

    public static void remove(Context context, String requestId) {
        if (requestId == null || requestId.isEmpty()) return;

        try {
            JSONArray items = readItems(context);
            JSONArray updated = new JSONArray();

            for (int i = 0; i < items.length(); i++) {
                JSONObject old = items.optJSONObject(i);
                if (old != null && requestId.equals(old.optString("request_id"))) continue;
                if (old != null) updated.put(old);
            }

            writeItems(context, updated);
        } catch (Exception ignored) {
        }

        cancelAlarm(context, requestId);
    }

    public static void rescheduleAll(Context context) {
        if (!canScheduleExact(context)) return;

        try {
            JSONArray items = readItems(context);
            long now = System.currentTimeMillis();

            for (int i = 0; i < items.length(); i++) {
                JSONObject item = items.optJSONObject(i);
                if (item == null) continue;

                String id = item.optString("request_id", "");
                long trigger = item.optLong("trigger_at", 0L);
                if (id.isEmpty()) continue;

                // An old one-shot schedule must never be fired after reboot.
                if (trigger <= now) {
                    remove(context, id);
                    continue;
                }
                armAtWallClock(context, id, trigger);
            }
        } catch (Exception ignored) {
        }
    }

    private static PendingIntent pendingIntent(Context context, String requestId) {
        Intent intent = new Intent(context, NovaScheduledSmsReceiver.class);
        intent.setAction(NovaScheduledSmsReceiver.ACTION_SCHEDULED_SMS);
        intent.setData(Uri.parse("novasms:" + requestId));
        intent.putExtra(NovaScheduledSmsReceiver.EXTRA_REQUEST_ID, requestId);

        return PendingIntent.getBroadcast(
                context,
                requestCode(requestId),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
    }

    private static void armAfterDelay(Context context, String requestId, long delayMs) {
        AlarmManager alarms = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarms == null) throw new IllegalStateException("AlarmManager unavailable.");

        alarms.setExactAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + delayMs,
                pendingIntent(context, requestId)
        );
    }

    private static void armAtWallClock(Context context, String requestId, long triggerAtMillis) {
        AlarmManager alarms = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarms == null) throw new IllegalStateException("AlarmManager unavailable.");

        alarms.setExactAndAllowWhileIdle(
                AlarmManager.RTC_WAKEUP,
                triggerAtMillis,
                pendingIntent(context, requestId)
        );
    }

    private static void cancelAlarm(Context context, String requestId) {
        AlarmManager alarms = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (alarms == null) return;

        Intent intent = new Intent(context, NovaScheduledSmsReceiver.class);
        intent.setAction(NovaScheduledSmsReceiver.ACTION_SCHEDULED_SMS);
        intent.setData(Uri.parse("novasms:" + requestId));

        PendingIntent pending = PendingIntent.getBroadcast(
                context,
                requestCode(requestId),
                intent,
                PendingIntent.FLAG_NO_CREATE | PendingIntent.FLAG_IMMUTABLE
        );

        if (pending != null) alarms.cancel(pending);
    }

    private static int requestCode(String value) {
        return value == null ? 1 : (value.hashCode() & 0x7fffffff);
    }

    private static JSONArray readItems(Context context) {
        String raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_ITEMS, "[]");

        try {
            return new JSONArray(raw);
        } catch (Exception e) {
            return new JSONArray();
        }
    }

    private static void writeItems(Context context, JSONArray items) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_ITEMS, items.toString())
                .apply();
    }
}
