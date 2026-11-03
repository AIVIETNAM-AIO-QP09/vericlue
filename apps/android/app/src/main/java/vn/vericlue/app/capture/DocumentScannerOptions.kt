package vn.vericlue.app.capture

import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions

/** Preserve document colours/portrait; no gallery import, filters, stain or finger removal. */
fun cardDocumentScannerOptions(): GmsDocumentScannerOptions = GmsDocumentScannerOptions.Builder()
    .setGalleryImportAllowed(false)
    .setPageLimit(1)
    .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_JPEG)
    .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_BASE)
    .build()
