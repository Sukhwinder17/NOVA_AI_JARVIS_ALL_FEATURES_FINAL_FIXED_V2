package com.nova.phone;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.Manifest;
import android.content.pm.PackageManager;
import android.widget.Button;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final int REQUEST_SEND_SMS = 2001;
    private TextView status;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        status = findViewById(R.id.status);
        Button settings = findViewById(R.id.settings);
        settings.setOnClickListener(v ->
                startActivity(new Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS")));
        updateStatus();
        requestSmsPermissionIfNeeded();
    }

    private void requestSmsPermissionIfNeeded() {
        if (android.os.Build.VERSION.SDK_INT >= 23
                && checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.SEND_SMS}, REQUEST_SEND_SMS);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_SEND_SMS) updateStatus();
    }

    @Override
    protected void onResume() {
        super.onResume();
        updateStatus();
    }

    private void updateStatus() {
        boolean enabled = NovaNotificationListener.isEnabled(this);
        boolean smsGranted = android.os.Build.VERSION.SDK_INT < 23
                || checkSelfPermission(Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED;
        String notificationText = enabled
                ? "✅ Notification access is enabled."
                : "⚠️ Notification access is disabled.";
        String smsText = smsGranted
                ? "✅ Automatic SMS sending is enabled."
                : "⚠️ Automatic SMS sending needs SMS permission.";
        String actionText = enabled
                ? "Messages can now be forwarded to NOVA."
                : "Tap the button and enable NOVA Notification Listener.";
        status.setText(notificationText + "\n" + smsText + "\n" + actionText);
    }
}
