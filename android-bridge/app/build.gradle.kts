plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.thermobaby.bridge"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.thermobaby.bridge"
        minSdk = 24          // Android 7.0+ (USB-OTG host)
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
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
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")

    // UVC camera engine with RAW frame access over USB-OTG (replica de THG Start).
    // libausbc wraps libuvc and exposes raw frame callbacks.
    implementation("com.github.jiangdongguo.AndroidUSBCamera:libausbc:3.3.3")

    // OkHttp WebSocket client to stream frames to the ThermoBaby server.
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    coroutines()
}

fun org.gradle.api.artifacts.dsl.DependencyHandler.coroutines() {
    add("implementation", "org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
