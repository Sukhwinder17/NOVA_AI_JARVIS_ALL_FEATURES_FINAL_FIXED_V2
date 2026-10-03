package com.nova.phone;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;

import org.json.JSONArray;
import org.json.JSONObject;

public class NovaScheduledSmsReceiver extends BroadcastReceiver {
    public static final String ACTION_SCHEDULE_SMS = "com.nova.phone.SCHEDULE_SMS";
    public static final String ACTION_SCHEDULED_SMS = "com.nova.phone.SCHEDULED_SMS";
    public static final String EXTRA_REQUEST_ID = "request_id";
    public static final String EXTRA_RECIPIENT = "recipient";
    public static final String EXTRA_MESSAGE = "message";

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

        // One-time schedule.
        NovaSmsScheduler.remove(context, requestId);

        Intent sms = new Intent(Intent.ACTION_SENDTO);
        sms.setData(Uri.parse("smsto:" + data[0]));
        sms.putExtra("sms_body", data[1]);
        sms.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);

        try {
            context.startActivity(sms);
        } catch (Exception ignored) {
            // The schedule is consumed even if Android blocks a background
            // activity launch. The user can use the companion notification
            // fallback in a later version.
        }
    }

    private void handleScheduleCommand(Context context, Intent intent) {
        String requestId = intent.getStringExtra(EXTRA_REQUEST_ID);
        String recipient = intent.getStringExtra(EXTRA_RECIPIENT);
        String message = intent.getStringExtra(EXTRA_MESSAGE);
        long delayMs = intent.getLongExtra("delay_ms", -1L);
        long triggerAt = intent.getLongExtra("trigger_at", 0L);

        // Prefer a relative delay so a small clock difference between laptop
        // and phone cannot turn a valid schedule into a rejected one.
        if (delayMs > 0L) {
            triggerAt = System.currentTimeMillis() + delayMs;
        }

        if (requestId == null || requestId.trim().isEmpty()
                || recipient == null || recipient.trim().isEmpty()
                || message == null || message.trim().isEmpty()
                || triggerAt <= System.currentTimeMillis()) {
            setResultCode(2);
            return;
        }

        try {
            NovaSmsScheduler.schedule(
                    context,
                    requestId.trim(),
                    recipient.trim(),
                    message,
                    triggerAt
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
                        item.optString("message", "")
                };
            }
        } catch (Exception ignored) {
        }

        return null;
    }
}
