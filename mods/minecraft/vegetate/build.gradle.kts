import net.ltgt.gradle.errorprone.errorprone

plugins {
    id("net.neoforged.moddev.legacyforge") version "2.0.140"
    id("com.diffplug.spotless") version "7.0.4"
    id("net.ltgt.errorprone") version "5.1.0"
}

group = "com.squinchmods.vegetate"
version = "0.1.0+forge-1.20.1"

java {
    toolchain.languageVersion = JavaLanguageVersion.of(17)
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

legacyForge {
    enable {
        forgeVersion = "1.20.1-47.4.0"
    }
    mixin {
        add(sourceSets.main.get(), "vegetate.refmap.json")
        config("vegetate-common.mixins.json")
        config("vegetate-forge.mixins.json")
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
        register("vegetate") {
            sourceSet(sourceSets.main.get())
        }
    }
}

repositories {
    mavenCentral()
    exclusiveContent {
        forRepository {
            maven("https://repo.spongepowered.org/repository/maven-public") { name = "Sponge" }
        }
        filter { includeGroupAndSubgroups("org.spongepowered") }
    }
    exclusiveContent {
        forRepositories(
            maven("https://maven.parchmentmc.org") { name = "ParchmentMC" },
            maven("https://maven.neoforged.net/releases") { name = "NeoForge" },
        )
        filter { includeGroup("org.parchmentmc.data") }
    }
    maven("https://maven.isxander.dev/releases")
    maven("https://maven.isxander.dev/snapshots")
}

configurations {
    create("guavaForJavacBootclasspath") {
        isCanBeConsumed = false
        isCanBeResolved = true
    }
}

dependencies {
    compileOnly("org.jetbrains:annotations:24.1.0")
    compileOnly("org.spongepowered:mixin:0.8.5")
    annotationProcessor("org.spongepowered:mixin:0.8.5-SNAPSHOT:processor")

    "io.github.llamalad7:mixinextras-common:0.4.1".let {
        compileOnly(it)
        annotationProcessor(it)
    }
    "io.github.llamalad7:mixinextras-forge:0.4.1".let {
        implementation(it)
        jarJar(it)
    }

    modImplementation("dev.isxander:yet-another-config-lib:3.6.6+1.20.1-forge")

    errorprone("com.google.errorprone:error_prone_core:2.39.0")
    errorprone("com.uber.nullaway:nullaway:0.12.7")

    add("guavaForJavacBootclasspath", "com.google.guava:guava:33.3.1-jre") {
        isTransitive = false
    }
    add("guavaForJavacBootclasspath", "com.google.guava:failureaccess:1.0.2") {
        isTransitive = false
    }
}

// Align Guava on compilation graphs and prepend Guava (+ failureaccess) to the *javac JVM* bootclasspath so
// Error Prone sees Guava 33 APIs before Minecraft's older Guava on the worker classpath.
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

val expandProps = mapOf(
    "javaVersion" to "17",
    "modId" to "vegetate",
    "modName" to "Vegetate",
    "modVersion" to project.version.toString(),
    "modGroup" to "com.squinchmods.vegetate",
    "modAuthor" to "SquinchMods",
    "modDescription" to "Mushroom vegetation control mod for Minecraft.",
    "modLicense" to "CC-BY-NC-ND-4.0",
    "minecraftVersion" to "1.20.1",
    "minMinecraftVersion" to "1.20",
    "forgeVersion" to "47.4.0",
    "yaclVersion" to "3.6.6+1.20.1",
)

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
    options.compilerArgs.add("-Xlint:deprecation")
    options.errorprone {
        disableWarningsInGeneratedCode.set(true)
        option("NullAway:AnnotatedPackages", "com.squinchmods.vegetate")
        error("NullAway")
    }
}

tasks {
    processResources {
        inputs.properties(expandProps)
        filesMatching(listOf("META-INF/mods.toml")) {
            expand(expandProps)
        }
        filesMatching(listOf("pack.mcmeta", "*.mixins.json")) {
            expand(expandProps.mapValues { (_, v) -> v.replace("\n", "\\\\n") })
        }
    }

    jar {
        finalizedBy("reobfJar")
        manifest {
            attributes(
                mapOf("MixinConfigs" to "vegetate-common.mixins.json,vegetate-forge.mixins.json")
            )
        }
    }
}
