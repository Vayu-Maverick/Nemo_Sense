plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.netra.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.netra.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        // ============================================================
        // GEMINI API KEY CONFIGURATION
        // ============================================================
        // Replace "YOUR_GEMINI_API_KEY" with your actual Gemini API key.
        // Get your key at: https://aistudio.google.com/app/apikey
        // For production, use local.properties or environment variables
        // instead of hardcoding the key here.
        // ============================================================
        buildConfigField("String", "GEMINI_API_KEY", "\"YOUR_GEMINI_API_KEY\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }

    kotlinOptions {
        jvmTarget = "1.8"
    }

    buildFeatures {
        buildConfig = true
        viewBinding = true
    }
}

dependencies {
    // AndroidX core libraries
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")

    // Google Generative AI (Gemini) SDK
    implementation("com.google.ai.client.generativeai:generativeai:0.9.0")

    // Google Play Services - Location (Fused Location Provider)
    implementation("com.google.android.gms:play-services-location:21.0.1")

    // OkHttp for Nominatim geocoding and OSRM routing API calls
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // Kotlin Coroutines for async operations
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
}
