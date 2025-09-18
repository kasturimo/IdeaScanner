# Keep Google Sign-In classes
-keep class com.google.android.gms.auth.** { *; }
-keep class com.google.android.gms.common.** { *; }
-keep class com.google.android.gms.tasks.** { *; }

# Keep Play Billing classes
-keep class com.android.billingclient.api.** { *; }

# Keep Kotlin coroutines + lifecycle (if used)
-keep class kotlinx.coroutines.** { *; }
-keep class androidx.lifecycle.** { *; }

# Keep your own app classes
-keep class com.ideascanner.** { *; }

# Remove logs in release build
-assumenosideeffects class android.util.Log {
    public static *** d(...);
    public static *** v(...);
    public static *** i(...);
    public static *** w(...);
}
