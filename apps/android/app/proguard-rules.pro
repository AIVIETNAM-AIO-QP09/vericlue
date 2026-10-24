# kotlinx.serialization: keep generated serializers of the API models
# (the library ships most rules; these cover our @Serializable classes explicitly).
-keepattributes *Annotation*, InnerClasses
-keep,includedescriptorclasses class vn.vericlue.app.**$$serializer { *; }
-keepclassmembers class vn.vericlue.app.** {
    *** Companion;
}
-keepclasseswithmembers class vn.vericlue.app.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# OkHttp optional platform classes
-dontwarn org.bouncycastle.**
-dontwarn org.conscrypt.**
-dontwarn org.openjsse.**
