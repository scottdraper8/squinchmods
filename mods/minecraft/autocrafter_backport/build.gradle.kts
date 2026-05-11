import net.ltgt.gradle.errorprone.errorprone

plugins {
    id("net.neoforged.moddev.legacyforge") version "2.0.140"
    id("com.diffplug.spotless") version "7.0.4"
    id("net.ltgt.errorprone") version "5.1.0"
}

group = "com.squinchmods.autocrafter_backport"
version = "1.0.0+forge-1.20.1"

java {
    toolchain.languageVersion = JavaLanguageVersion.of(17)
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

legacyForge {
    enable {
        forgeVersion = "1.20.1-47.4.0"
    }
    parchment {
        mappingsVersion = "2023.09.03"
        minecraftVersion = "1.20.1"
    }
    runs {
        register("client") {
            client()
            ideName = "Forge Client"
        }
        register("server") {
            server()
            ideName = "Forge Server"
        }
    }
    mods {
        register("autocrafter_backport") {
            sourceSet(sourceSets.main.get())
        }
    }
}

repositories {
    mavenCentral()
    exclusiveContent {
        forRepository {
            maven("https://maven.minecraftforge.net") { name = "Forge" }
        }
        filter { includeGroupAndSubgroups("net.minecraftforge") }
    }
}

configurations {
    create("guavaForJavacBootclasspath") {
        isCanBeConsumed = false
        isCanBeResolved = true
    }
}

dependencies {
    compileOnly("org.jetbrains:annotations:24.1.0")
    compileOnly("com.google.code.findbugs:jsr305:3.0.2")

    errorprone("com.google.errorprone:error_prone_core:2.39.0")
    errorprone("com.uber.nullaway:nullaway:0.12.7")

    add("guavaForJavacBootclasspath", "com.google.guava:guava:33.3.1-jre") {
        isTransitive = false
    }
    add("guavaForJavacBootclasspath", "com.google.guava:failureaccess:1.0.2") {
        isTransitive = false
    }
}

listOf(
    "compileClasspath",
    "annotationProcessor",
    "runtimeClasspath",
    "testCompileClasspath",
    "testAnnotationProcessor",
    "testRuntimeClasspath",
).forEach { name ->
    configurations.findByName(name)?.resolutionStrategy?.force("com.google.guava:guava:33.3.1-jre")
}

spotless {
    java {
        target("src/**/*.java")
        googleJavaFormat("1.27.0")
        formatAnnotations()
    }
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
    options.isFork = true
    val bootclasspath =
        configurations.named("guavaForJavacBootclasspath").get().files
            .sortedBy { it.name }
            .joinToString(":") { it.absolutePath.replace('\\', '/') }
    options.forkOptions.jvmArgs =
        (options.forkOptions.jvmArgs ?: emptyList()) + "-Xbootclasspath/a:$bootclasspath"
    options.compilerArgs.addAll(listOf("-Xlint:deprecation", "-Werror"))
    options.errorprone {
        disableWarningsInGeneratedCode.set(true)
        option("NullAway:AnnotatedPackages", "com.squinchmods.autocrafterbackport")
        error("NullAway")
    }
}
