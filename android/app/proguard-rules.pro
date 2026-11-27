# Keep JavaScript bridges exposed to WebView
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
-keep class com.canorus.odysseus.MainActivity$NativeBridge { *; }

# Keep WorkManager Workers & Android components
-keep class * extends androidx.work.Worker {
    public <init>(android.content.Context, androidx.work.WorkerParameters);
}
-keep class com.canorus.odysseus.** extends android.app.Activity
-keep class com.canorus.odysseus.** extends android.app.Service
-keep class com.canorus.odysseus.** extends android.content.BroadcastReceiver

# Keep Capacitor plugins & bridge classes
-keep class com.getcapacitor.** { *; }
-keep @com.getcapacitor.annotation.CapacitorPlugin class * { *; }
# Métodos nativos implementados em Rust (libodysseus_voice.so): nomes JNI têm de ficar intactos.
-keepclasseswithmembernames,includedescriptorclasses class com.canorus.odysseus.** { native <methods>; }
# A política em Rust devolve os nomes das constantes (ALLOW, PAYMENT…), lidos com valueOf().
-keepclassmembers enum com.canorus.odysseus.AgentPolicy$* { *; }
