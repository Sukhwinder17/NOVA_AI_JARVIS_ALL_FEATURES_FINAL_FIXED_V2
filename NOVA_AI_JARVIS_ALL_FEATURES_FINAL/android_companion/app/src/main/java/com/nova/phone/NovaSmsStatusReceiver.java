package com.nova.phone;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.telephony.SmsManager;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Sends the asynchronous SmsManager result back to NOVA over the ADB reverse
 * tunnel. This lets the desktop app distinguish "request accepted" from
 * "actually sent by telephony".
 */
public class NovaSmsStatusReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        final String action = intent.getAction();
        final String requestId = intent.getStringExtra("request_id");
        final int part = intent.getIntExtra("part", 0);
        final int total = intent.getIntExtra("total", 1);
        final int resultCode = getResultCode();
        final boolean noDefault = intent.getBooleanExtra("noDefault", false);

        final String status;
        if (ACTION_SENT.equals(action)) {
            status = resultCode == Activity.RESULT_OK ? "sent" : "failed";
        } else if (ACTION_DELIVERED.equals(action)) {
            status = resultCode == Activity.RESULT_OK ? "delivered" : "delivery_failed";
        } else {
            return;
        }

        final String resultName = resultName(resultCode, noDefault);
        new Thread(() -> postStatus(requestId, status, resultName, resultCode, noDefault, part, total)).start();
    }

    private static final String ACTION_SENT = "com.nova.phone.SMS_SENT";
    private static final String ACTION_DELIVERED = "com.nova.phone.SMS_DELIVERED";

    private String resultName(int resultCode, boolean noDefault) {
        if (resultCode == Activity.RESULT_OK) return "OK";
        if (noDefault) return "NO_DEFAULT_SMS_SUBSCRIPTION";
        if (resultCode == SmsManager.RESULT_ERROR_GENERIC_FAILURE) return "GENERIC_FAILURE";
        if (resultCode == SmsManager.RESULT_ERROR_NO_SERVICE) return "NO_SERVICE";
        if (resultCode == SmsManager.RESULT_ERROR_NULL_PDU) return "NULL_PDU";
        if (resultCode == SmsManager.RESULT_ERROR_RADIO_OFF) return "RADIO_OFF";
        return "RESULT_" + resultCode;
    }

    private void postStatus(
            String requestId,
            String status,
            String resultName,
            int resultCode,
            boolean noDefault,
            int part,
            int total
    ) {
        HttpURLConnection conn = null;
        try {
            JSONObject obj = new JSONObject();
            obj.put("request_id", requestId);
            obj.put("status", status);
            obj.put("result", resultName);
            obj.put("result_code", resultCode);
            obj.put("no_default_sms_subscription", noDefault);
            obj.put("part", part);
            obj.put("total", total);

            URL url = new URL("http://127.0.0.1:8765/sms_status");
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
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
