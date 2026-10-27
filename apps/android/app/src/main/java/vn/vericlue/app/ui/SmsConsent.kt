package vn.vericlue.app.ui

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import androidx.core.content.IntentCompat
import androidx.core.os.BundleCompat
import com.google.android.gms.auth.api.phone.SmsRetriever
import com.google.android.gms.common.api.CommonStatusCodes
import com.google.android.gms.common.api.Status
import vn.vericlue.app.flow.OtpRules

/**
 * Fills the OTP from a real SMS with the SMS User Consent API: the system asks the user once to let
 * the app read that one message; no SMS permission. Without Play services, or with the simulated SMS
 * of the demo channel, nothing arrives and the user types the code.
 */
@Composable
fun SmsCodeListener(enabled: Boolean, onCode: (String) -> Unit) {
    val context = LocalContext.current
    val latest = rememberUpdatedState(onCode)
    val consent = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            OtpRules.codeIn(result.data?.getStringExtra(SmsRetriever.EXTRA_SMS_MESSAGE))?.let { latest.value(it) }
        }
    }
    DisposableEffect(enabled) {
        if (!enabled) return@DisposableEffect onDispose {}
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context, intent: Intent) {
                if (intent.action != SmsRetriever.SMS_RETRIEVED_ACTION) return
                val extras = intent.extras ?: return
                val status = BundleCompat.getParcelable(extras, SmsRetriever.EXTRA_STATUS, Status::class.java)
                if (status?.statusCode != CommonStatusCodes.SUCCESS) return
                val ask = IntentCompat.getParcelableExtra(intent, SmsRetriever.EXTRA_CONSENT_INTENT, Intent::class.java) ?: return
                // Only launch Play services' own consent screen, never an intent redirected elsewhere.
                val target = ask.resolveActivity(ctx.packageManager)?.packageName
                if (target != "com.google.android.gms" || ask.flags and GRANT_FLAGS != 0) return
                runCatching { consent.launch(ask) }
            }
        }
        runCatching { SmsRetriever.getClient(context).startSmsUserConsent(null) }
        ContextCompat.registerReceiver(
            context,
            receiver,
            IntentFilter(SmsRetriever.SMS_RETRIEVED_ACTION),
            SmsRetriever.SEND_PERMISSION,
            null,
            ContextCompat.RECEIVER_EXPORTED,
        )
        onDispose { runCatching { context.unregisterReceiver(receiver) } }
    }
}

private const val GRANT_FLAGS = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
