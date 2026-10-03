package com.nova.phone;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Button;
import android.widget.TextView;

public class MainActivity extends Activity {
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
    }

    @Override
    protected void onResume() {
        super.onResume();
        updateStatus();
    }

    private void updateStatus() {
        boolean enabled = NovaNotificationListener.isEnabled(this);
        status.setText(enabled
                ? "✅ Notification access is enabled.\nMessages can now be forwarded to NOVA."
                : "⚠️ Notification access is disabled.\nTap the button and enable NOVA Notification Listener.");
    }
}
