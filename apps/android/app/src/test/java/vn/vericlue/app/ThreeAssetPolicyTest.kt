package vn.vericlue.app

import java.io.File
import org.junit.Assert.*
import org.junit.Test
import vn.vericlue.app.ui.ThreeAssetPolicy

class ThreeAssetPolicyTest {
    @Test fun onlyBundledPageAndItsThreeResourcesAreAllowed() {
        listOf("index.html", "scene.js", "scene.css", "vendor/three.module.min.js").forEach { path ->
            val asset = requireNotNull(ThreeAssetPolicy.asset("${ThreeAssetPolicy.ORIGIN}/three/$path"))
            assertEquals("three/$path", asset.first)
            assertTrue(File("src/main/assets", asset.first).isFile)
        }
    }

    @Test fun remoteContentAndOtherLocalAssetsCannotFallThrough() {
        listOf("https://example.org/three/index.html", "http://appassets.androidplatform.net/three/index.html",
            "https://appassets.androidplatform.net.evil.test/three/index.html",
            "https://user@appassets.androidplatform.net/three/index.html",
            "https://appassets.androidplatform.net:443/three/index.html",
            "file:///android_asset/three/index.html", "content://three/index.html",
            "javascript:alert(1)", "data:text/html,hello", "not a url").forEach {
            assertNull(it, ThreeAssetPolicy.asset(it))
        }
    }

    @Test fun traversalEncodedPathsAndUnlistedFilesAreRejected() {
        listOf("/three/../licenses/lottie-android.txt", "/three/%2e%2e/secret", "/three//scene.js",
            "/three/%73cene.js", "/three/vendor/LICENSE", "/three/index.html?remote=1",
            "/three/index.html#fragment", "/three/scene.js/", "/three/Scene.js").forEach {
            assertNull(it, ThreeAssetPolicy.asset(ThreeAssetPolicy.ORIGIN + it))
        }
    }
}
