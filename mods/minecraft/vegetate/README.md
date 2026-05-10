# Vegetate

Mushroom vegetation control mod for Minecraft Forge 1.20.1.

## Builds and formatting

- `./gradlew compileJava` — type-check sources.
- `./gradlew spotlessCheck` — verify formatting.
- `./gradlew spotlessApply` — apply Google Java Format (Spotless).

Pinned tool versions (confirm upgrades against Spotless docs):

- Spotless Gradle plugin **7.0.4**
- `google-java-format` **1.27.0**

Refresh hook pins:

```bash
pre-commit autoupdate
pre-commit run --all-files
```

## Static analysis

Configured in `build.gradle.kts`; runs during `./gradlew compileJava`:

- **Error Prone**: Gradle plugin `net.ltgt.errorprone` **5.1.0**;
  `error_prone_core` **2.39.0** on the Error Prone path.
- **NullAway**: `com.uber.nullaway:nullaway` **0.12.7**;
  `AnnotatedPackages` includes `com.squinchmods.vegetate` at **error**.

Minecraft/Forge pulls older Guava than Error Prone expects. This build forces
**Guava 33.3.1-jre** on compile graphs and prepends **Guava** and
**failureaccess** on the forked javac `-Xbootclasspath/a:` so the checker JVM
loads compatible classes.

```bash
./gradlew compileJava
```
