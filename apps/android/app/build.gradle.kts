plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.paparazzi)
    alias(libs.plugins.kotlin.serialization)
}

// One package for every connection method; developers may override the endpoint with
// ./gradlew assembleRelease -Pvericlue.apiBaseUrl=https://<tunnel>/  (never hard-code the tunnel)
val apiBaseUrl = (project.findProperty("vericlue.apiBaseUrl") as String?) ?: "http://localhost:8421/"
val signedMedia = (project.findProperty("vericlue.signedMedia") as String?)?.toBooleanStrict() ?: true
val demoStore = System.getenv("VERICLUE_ANDROID_KEYSTORE_PATH")
val demoStorePassword = System.getenv("VERICLUE_ANDROID_KEYSTORE_PASSWORD")
// A release build only talks HTTPS: stop it when the address is not https:// (debug may use http).
val checkReleaseApiUrl by tasks.registering {
    val url = apiBaseUrl
    doLast {
        if (!url.startsWith("https://")) {
            throw GradleException("Release cần -Pvericlue.apiBaseUrl=https://… (đang là \"$url\").")
        }
    }
}
tasks.matching { it.name == "preReleaseBuild" }.configureEach { dependsOn(checkReleaseApiUrl) }

android {
    namespace = "vn.vericlue.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "vn.vericlue.app"
        minSdk = 29 // Android 10 (ADR-0014)
        targetSdk = 35
        versionCode = 2
        versionName = "0.3.0"
        manifestPlaceholders["appLabel"] = "@string/app_name"

        buildConfigField("String", "API_BASE_URL", "\"$apiBaseUrl\"")
        buildConfigField("boolean", "SIGNED_MEDIA", signedMedia.toString())
    }

    if (!demoStore.isNullOrBlank()) {
        require(!demoStorePassword.isNullOrBlank()) { "Missing demo signing password." }
        signingConfigs.create("vericlueDemo") {
            storeFile = file(demoStore)
            storeType = "PKCS12"
            storePassword = demoStorePassword
            keyAlias = "vericlue-demo"
            keyPassword = demoStorePassword
        }
    }
    buildTypes {
        debug {
            if (!demoStore.isNullOrBlank()) signingConfig = signingConfigs.getByName("vericlueDemo")
        }
        release {
            // R8 removes unused code (most of material-icons-extended) and resources.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // Demo only: signed with the local debug key so it installs. Use a real key before any release.
            signingConfig = signingConfigs.getByName(if (demoStore.isNullOrBlank()) "debug" else "vericlueDemo")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    // One APK per CPU type (phones need only arm64-v8a) plus a universal one for convenience.
    splits {
        abi {
            isEnable = true
            reset()
            include("arm64-v8a", "armeabi-v7a", "x86_64")
            isUniversalApk = true
        }
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    debugImplementation(libs.androidx.compose.ui.tooling)

    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.view)
    implementation(libs.androidx.camera.video)
    implementation(libs.mlkit.face.detection)
    implementation(libs.mlkit.barcode.scanning)
    implementation(libs.play.services.auth.api.phone) // SMS User Consent: fills the OTP from a real SMS
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.kotlinx.coroutines.test)
}
