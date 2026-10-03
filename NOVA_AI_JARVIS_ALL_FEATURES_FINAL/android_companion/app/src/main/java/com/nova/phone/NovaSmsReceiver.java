package com.nova.phone;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.telephony.SmsManager;

import java.util.ArrayList;

/**
 * Receives explicit commands from NOVA over ADB and sends a real SMS in the
 * background. No Messages UI is opened.
 */
public class NovaSmsReceiver extends BroadcastReceiver {
    public static final String ACTION_SEND_SMS = "com.nova.phone.SEND_SMS";
    public static final String EXTRA_RECIPIENT = "recipient";
    public static final String EXTRA_MESSAGE = "message";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!ACTION_SEND_SMS.equals(intent.getAction())) return;

        String recipient = intent.getStringExtra(EXTRA_RECIPIENT);
        String message = intent.getStringExtra(EXTRA_MESSAGE);

        if (recipient == null || recipient.trim().isEmpty() || message == null || message.trim().isEmpty()) {
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
                manager.sendTextMessage(recipient.trim(), null, message, null, null);
            } else {
                manager.sendMultipartTextMessage(recipient.trim(), null, parts, null, null);
            }
            setResultCode(0);
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
}
