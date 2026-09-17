package com.gramcare.mobile_app

import android.content.Intent
import android.net.Uri
import android.provider.Telephony
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Opens the emergency SMS composer in the phone's real SMS app.
 *
 * Launching an "smsto:" URI and letting Android pick the handler does not
 * work: WhatsApp registers an ACTION_SENDTO filter for the sms and smsto
 * schemes, so the emergency message can land in WhatsApp instead — where,
 * because several recipients are joined into one URI, it reads the whole
 * list as a single number and reports it is not on WhatsApp. The message
 * never leaves. That is a bad way for an emergency alert to fail.
 *
 * Naming the default SMS package removes the ambiguity. Falling back to a
 * chooser is better than falling back to whatever resolves first.
 */
class MainActivity : FlutterActivity() {

    private val channel = "com.gramcare.mobile_app/sms"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channel)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "openSmsComposer" -> {
                        val recipients = call.argument<List<String>>("recipients").orEmpty()
                        val body = call.argument<String>("body").orEmpty()
                        result.success(openSmsComposer(recipients, body))
                    }
                    "shareViaWhatsApp" -> {
                        val body = call.argument<String>("body").orEmpty()
                        result.success(shareViaWhatsApp(body))
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun openSmsComposer(recipients: List<String>, body: String): Boolean {
        if (recipients.isEmpty()) return false

        // Android's own separator for multiple SMS recipients is ";" — a
        // comma-joined list is read by some handlers as one long number.
        val uri = Uri.parse("smsto:" + recipients.joinToString(";"))
        val intent = Intent(Intent.ACTION_SENDTO, uri).apply {
            putExtra("sms_body", body)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }

        val defaultSms = Telephony.Sms.getDefaultSmsPackage(this)
        if (defaultSms != null) {
            intent.setPackage(defaultSms)
            try {
                startActivity(intent)
                return true
            } catch (_: Exception) {
                // The named package could not handle it after all; fall
                // through to the chooser rather than giving up.
                intent.setPackage(null)
            }
        }

        return try {
            startActivity(Intent.createChooser(intent, "Send emergency SMS").apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            })
            true
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Hands the emergency message to WhatsApp's own "Send to" picker.
     *
     * ACTION_SEND scoped to the WhatsApp package lets the patient pick
     * several family chats and send once, which a wa.me link cannot do — a
     * link opens a single chat. WhatsApp Business is tried second so a
     * phone with only that installed still works.
     */
    private fun shareViaWhatsApp(body: String): Boolean {
        for (pkg in listOf("com.whatsapp", "com.whatsapp.w4b")) {
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, body)
                setPackage(pkg)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            try {
                startActivity(intent)
                return true
            } catch (_: Exception) {
                // Not installed; try the next one.
            }
        }
        return false
    }
}
