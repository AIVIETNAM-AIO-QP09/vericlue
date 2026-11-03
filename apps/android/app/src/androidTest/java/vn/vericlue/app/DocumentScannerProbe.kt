package vn.vericlue.app

import android.app.Instrumentation
import android.content.Intent
import android.os.Bundle
import android.graphics.Bitmap
import android.net.Uri
import android.media.ExifInterface
import com.google.android.gms.common.api.ApiException
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.io.File
import vn.vericlue.app.capture.cardDocumentScannerOptions
import vn.vericlue.app.capture.readDocumentJpeg
import vn.vericlue.app.capture.discardDocumentImage

/** Checks SDK/model availability on the real phone without launching a camera or granting consent. */
object DocumentScannerProbe {
    fun run(instrumentation: Instrumentation): Bundle {
        val output = Bundle()
        val completed = CountDownLatch(1)
        val activity = instrumentation.startActivitySync(Intent(instrumentation.targetContext, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        try {
            val context = instrumentation.targetContext
            val image = File.createTempFile("document-reader-probe-", ".jpg", context.cacheDir)
            try {
                val bitmap = Bitmap.createBitmap(320, 200, Bitmap.Config.ARGB_8888)
                bitmap.eraseColor(android.graphics.Color.BLUE)
                image.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 95, it) }
                bitmap.recycle()
                ExifInterface(image.path).apply {
                    setAttribute(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_ROTATE_180.toString())
                    saveAttributes()
                }
                check(readDocumentJpeg(context, Uri.fromFile(image)).contentEquals(image.readBytes()))
                discardDocumentImage(context, Uri.fromFile(image))
                check(!image.exists())
                val outsideCache = File.createTempFile("document-reader-probe-", ".txt", context.filesDir)
                try {
                    check(runCatching { readDocumentJpeg(context, Uri.fromFile(outsideCache)) }.isFailure)
                    discardDocumentImage(context, Uri.fromFile(outsideCache))
                    check(outsideCache.exists())
                } finally { outsideCache.delete() }
                output.putBoolean("image_reader_passed", true)
            } finally { image.delete() }
            instrumentation.runOnMainSync {
                GmsDocumentScanning.getClient(cardDocumentScannerOptions()).getStartScanIntent(activity)
                    .addOnSuccessListener {
                        output.putBoolean("scanner_ready", true)
                        completed.countDown()
                    }
                    .addOnFailureListener {
                        output.putString("failure_class", it.javaClass.simpleName)
                        if (it is ApiException) output.putInt("failure_code", it.statusCode)
                        completed.countDown()
                    }
            }
            output.putBoolean("completed", completed.await(90, TimeUnit.SECONDS))
            output.putBoolean("camera_launched", false)
        } catch (error: Exception) {
            output.putString("failure_class", error.javaClass.simpleName)
        } finally {
            instrumentation.runOnMainSync { activity.finish() }
        }
        return output
    }
}
