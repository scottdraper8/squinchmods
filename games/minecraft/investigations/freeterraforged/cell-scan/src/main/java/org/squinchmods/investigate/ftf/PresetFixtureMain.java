package org.squinchmods.investigate.ftf;

import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

import com.google.gson.JsonElement;
import com.google.gson.JsonParser;
import com.mojang.serialization.JsonOps;

import net.fabricmc.fabric.api.datagen.v1.DataGeneratorEntrypoint;
import net.fabricmc.fabric.api.datagen.v1.FabricDataGenerator;
import net.minecraft.core.HolderLookup;
import net.minecraft.data.DataGenerator;
import etcodehome.freeterraforged.data.worldgen.Datapacks;
import etcodehome.freeterraforged.data.worldgen.preset.settings.Preset;

public final class PresetFixtureMain implements DataGeneratorEntrypoint {
    @Override
    public void onInitializeDataGenerator(FabricDataGenerator fabricDataGenerator) {
        try {
            Path presetPath = requiredPath("squinch.fixture.preset");
            Path canonicalPresetPath = requiredPath("squinch.fixture.canonical-preset");
            Path outputPath = requiredPath("squinch.fixture.output");
            if (Files.exists(outputPath)) {
                throw new IllegalArgumentException("fixture output already exists: " + outputPath);
            }
            Preset preset;
            try (Reader reader = Files.newBufferedReader(presetPath, StandardCharsets.UTF_8)) {
                preset = Preset.DIRECT_CODEC.parse(JsonOps.INSTANCE, JsonParser.parseReader(reader))
                    .getOrThrow(message -> new IllegalArgumentException("invalid FTF preset: " + message));
            }
            JsonElement canonicalPreset = Preset.DIRECT_CODEC.encodeStart(JsonOps.INSTANCE, preset)
                .getOrThrow(message -> new IllegalArgumentException("could not encode FTF preset: " + message));
            Files.writeString(canonicalPresetPath, canonicalPreset.toString(), StandardCharsets.UTF_8);
            HolderLookup.Provider registries = fabricDataGenerator.getRegistries().join();
            Path dataRoot = outputPath.resolveSibling(outputPath.getFileName() + "-work");
            DataGenerator generator = Datapacks.makePreset(
                preset, registries, dataRoot, outputPath, "Squinch generated FTF fixture"
            );
            generator.run();
        } catch (Exception exception) {
            throw new IllegalStateException("complete preset fixture generation failed", exception);
        }
    }

    private static Path requiredPath(String property) {
        String value = System.getProperty(property);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("missing system property " + property);
        }
        return Path.of(value).toAbsolutePath().normalize();
    }
}
