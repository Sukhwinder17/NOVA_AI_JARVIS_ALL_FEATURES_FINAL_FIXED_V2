package com.nova.phone;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.telephony.SmsManager;

import java.util.ArrayList;

/**
 * Receives explicit commands from NOVA over ADB and sends a real SMS in the
 * background. No Messages UI is opened.
 *
 * The send operation is asynchronous, so a separate PendingIntent callback
 * reports the actual telephony result to NovaSmsStatusReceiver.
 */
public class NovaSmsReceiver extends BroadcastReceiver {
    public static final String ACTION_SEND_SMS = "com.nova.phone.SEND_SMS";
    public static final String EXTRA_RECIPIENT = "recipient";
    public static final String EXTRA_MESSAGE = "message";
    public static final String EXTRA_REQUEST_ID = "request_id";

    private static final String ACTION_SENT = "com.nova.phone.SMS_SENT";
    private static final String ACTION_DELIVERED = "com.nova.phone.SMS_DELIVERED";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!ACTION_SEND_SMS.equals(intent.getAction())) return;

        String recipient = intent.getStringExtra(EXTRA_RECIPIENT);
        String message = intent.getStringExtra(EXTRA_MESSAGE);
        String requestId = intent.getStringExtra(EXTRA_REQUEST_ID);

        if (recipient == null || recipient.trim().isEmpty()
                || message == null || message.trim().isEmpty()
                || requestId == null || requestId.trim().isEmpty()) {
            setResultCode(2);
            return;
        }

        if (android.os.Build.VERSION.SDK_INT >= 23
                && context.checkSelfPermission(android.Manifest.permission.SEND_SMS)
                    != PackageManager.PERMISSION_GRANTED) {
            setResultCode(3);
            return;
        }

        try {
            SmsManager manager = SmsManager.getDefault();
            ArrayList<String> parts = manager.divideMessage(message);

            if (parts.size() <= 1) {
                PendingIntent sent = resultIntent(context, ACTION_SENT, requestId, 0, 1);
                PendingIntent delivered = resultIntent(context, ACTION_DELIVERED, requestId, 0, 1);
                manager.sendTextMessage(
                        recipient.trim(), null, message, sent, delivered
                );
            } else {
                ArrayList<PendingIntent> sentIntents = new ArrayList<>();
                ArrayList<PendingIntent> deliveredIntents = new ArrayList<>();
                for (int i = 0; i < parts.size(); i++) {
                    sentIntents.add(resultIntent(context, ACTION_SENT, requestId, i, parts.size()));
                    deliveredIntents.add(resultIntent(context, ACTION_DELIVERED, requestId, i, parts.size()));
                }
                manager.sendMultipartTextMessage(
                        recipient.trim(), null, parts, sentIntents, deliveredIntents
                );
            }

            // 0 here means the receiver accepted the request; the actual
            // carrier send result arrives later through the PendingIntent.
            setResultCode(Activity.RESULT_OK);
        } catch (SecurityException e) {
            setResultCode(3);
        } catch (IllegalArgumentException e) {
            setResultCode(2);
        } catch (UnsupportedOperationException e) {
            setResultCode(4);
        } catch (Exception e) {
            setResultCode(5);
        }
    }

    private PendingIntent resultIntent(Context context, String action, String requestId, int part, int total) {
        Intent intent = new Intent(context, NovaSmsStatusReceiver.class);
        intent.setAction(action);
        intent.putExtra("request_id", requestId);
        intent.putExtra("part", part);
        intent.putExtra("total", total);
        intent.putExtra("recipient", "");
        int requestCode = Math.abs((requestId + ":" + action + ":" + part).hashCode());
        return PendingIntent.getBroadcast(
                context,
                requestCode,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
    }
}
