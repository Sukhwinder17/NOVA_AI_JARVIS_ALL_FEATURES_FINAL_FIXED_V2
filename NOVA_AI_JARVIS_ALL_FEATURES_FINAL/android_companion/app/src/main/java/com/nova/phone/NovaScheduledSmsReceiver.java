package com.nova.phone;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.telephony.SmsManager;

import java.util.ArrayList;

import android.net.Uri;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Stores schedules on the phone and sends the real SMS when AlarmManager fires.
 * No laptop/ADB connection is needed at send time and no Messages UI is opened.
 */
public class NovaScheduledSmsReceiver extends BroadcastReceiver {
    public static final String ACTION_SCHEDULE_SMS = "com.nova.phone.SCHEDULE_SMS";
    public static final String ACTION_SCHEDULED_SMS = "com.nova.phone.SCHEDULED_SMS";
    public static final String EXTRA_REQUEST_ID = "request_id";
    public static final String EXTRA_RECIPIENT = "recipient";
    public static final String EXTRA_MESSAGE = "message";

    private static final String ACTION_SENT = "com.nova.phone.SMS_SENT";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();

        if (ACTION_SCHEDULE_SMS.equals(action)) {
            handleScheduleCommand(context, intent);
            return;
        }

        if (!ACTION_SCHEDULED_SMS.equals(action)) return;

        String requestId = intent.getStringExtra(EXTRA_REQUEST_ID);
        if (requestId == null || requestId.trim().isEmpty()) return;

        String[] data = lookup(context, requestId);
        if (data == null) return;

        // Safety guard: if the alarm wakes the process early, do NOT send yet.
        // Re-arm for the remaining time. This guarantees the SMS cannot be sent
        // before the requested wall-clock time.
        long scheduledAt;
        try {
            scheduledAt = Long.parseLong(data[2]);
        } catch (Exception e) {
            scheduledAt = 0L;
        }

        long now = System.currentTimeMillis();
        if (scheduledAt > now + 1000L) {
            NovaSmsScheduler.rescheduleExisting(context, requestId, scheduledAt);
            return;
        }

        // If the target is more than a small tolerance in the future, do not
        // send early. The scheduler will re-arm the alarm for the remaining time.
        if (scheduledAt > now) {
            NovaSmsScheduler.rescheduleExisting(context, requestId, scheduledAt);
            return;
        }

        // Remove the one-shot schedule immediately before sending so it cannot fire twice.
        NovaSmsScheduler.remove(context, requestId);

        if (android.os.Build.VERSION.SDK_INT >= 23
                && context.checkSelfPermission(android.Manifest.permission.SEND_SMS)
                    != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            return;
        }

        try {
            SmsManager manager = getSmsManager(context);
            if (manager == null) return;

            ArrayList<String> parts = manager.divideMessage(data[1]);

            if (parts.size() <= 1) {
                PendingIntent sent = sentIntent(context, requestId, 0, 1);
                manager.sendTextMessage(data[0], null, data[1], sent, null);
            } else {
                ArrayList<PendingIntent> sentIntents = new ArrayList<>();
                for (int i = 0; i < parts.size(); i++) {
                    sentIntents.add(sentIntent(context, requestId, i, parts.size()));
                }
                manager.sendMultipartTextMessage(data[0], null, parts, sentIntents, null);
            }
        } catch (Exception ignored) {
            // The PendingIntent callback reports carrier-level send results
            // when Android can deliver it.
        }
    }

    private SmsManager getSmsManager(Context context) {
        try {
            if (android.os.Build.VERSION.SDK_INT >= 22) {
                int subId = android.telephony.SubscriptionManager.getDefaultSmsSubscriptionId();
                if (subId != android.telephony.SubscriptionManager.INVALID_SUBSCRIPTION_ID) {
                    return SmsManager.getSmsManagerForSubscriptionId(subId);
                }
            }
            return SmsManager.getDefault();
        } catch (Exception e) {
            try {
                return SmsManager.getDefault();
            } catch (Exception ignored) {
                return null;
            }
        }
    }

    private PendingIntent sentIntent(Context context, String requestId, int part, int total) {
        Intent callback = new Intent(context, NovaSmsStatusReceiver.class);
        callback.setAction(ACTION_SENT);
        callback.setData(Uri.parse("nova-scheduled-result:" + requestId + ":" + part));
        callback.putExtra("request_id", requestId);
        callback.putExtra("part", part);
        callback.putExtra("total", total);

        int code = (requestId + ":scheduled:" + part).hashCode() & 0x7fffffff;
        return PendingIntent.getBroadcast(
                context,
                code,
                callback,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
    }

    private void handleScheduleCommand(Context context, Intent intent) {
        String requestId = intent.getStringExtra(EXTRA_REQUEST_ID);
        String recipient = intent.getStringExtra(EXTRA_RECIPIENT);
        String message = intent.getStringExtra(EXTRA_MESSAGE);
        long delayMs = intent.getLongExtra("delay_ms", -1L);
        long triggerAt = intent.getLongExtra("trigger_at", 0L);

        if (delayMs > 0L) {
            triggerAt = System.currentTimeMillis() + delayMs;
        } else if (triggerAt <= System.currentTimeMillis()) {
            triggerAt = System.currentTimeMillis() + 3000L;
        }

        if (requestId == null || requestId.trim().isEmpty()
                || recipient == null || recipient.trim().isEmpty()
                || message == null || message.trim().isEmpty()) {
            setResultCode(2);
            return;
        }

        try {
            NovaSmsScheduler.schedule(
                    context,
                    requestId.trim(),
                    recipient.trim(),
                    message,
                    triggerAt,
                    delayMs
            );
            setResultCode(Activity.RESULT_OK);
        } catch (SecurityException e) {
            setResultCode(3);
        } catch (Exception e) {
            setResultCode(5);
        }
    }

    private String[] lookup(Context context, String requestId) {
        String raw = context.getSharedPreferences("nova_scheduled_sms", Context.MODE_PRIVATE)
                .getString("items", "[]");

        try {
            JSONArray items = new JSONArray(raw);
            for (int i = 0; i < items.length(); i++) {
                JSONObject item = items.optJSONObject(i);
                if (item == null) continue;
                if (!requestId.equals(item.optString("request_id"))) continue;

                return new String[]{
                        item.optString("recipient", ""),
                        item.optString("message", ""),
                        item.optString("trigger_at", "0")
                };
            }
        } catch (Exception ignored) {
        }

        return null;
    }
}
