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
import etcodehome.freeterraforged.data.worldgen.preset.settings.Presets;

public final class PresetExportMain implements DataGeneratorEntrypoint {
    @Override
    public void onInitializeDataGenerator(FabricDataGenerator fabricDataGenerator) {
        try {
            Path presetPath = requiredPath("squinch.preset.input");
            Path canonicalPresetPath = requiredPath("squinch.preset.canonical");
            Path outputPath = requiredPath("squinch.generated-datapack");
            if (Files.exists(outputPath)) {
                throw new IllegalArgumentException("generated datapack output already exists: " + outputPath);
            }
            Preset preset;
            try (Reader reader = Files.newBufferedReader(presetPath, StandardCharsets.UTF_8)) {
                var input = JsonParser.parseReader(reader).getAsJsonObject();
                if (input.has("squinch_builtin_preset")) {
                    if (input.size() != 1 || !"modern-default".equals(input.get("squinch_builtin_preset").getAsString())) {
                        throw new IllegalArgumentException("unsupported or mixed builtin preset selection");
                    }
                    preset = Presets.modernDefaultWithRivers();
                } else {
                    preset = Preset.DIRECT_CODEC.parse(JsonOps.INSTANCE, input)
                        .getOrThrow(message -> new IllegalArgumentException("invalid FTF preset: " + message));
                }
            }
            JsonElement canonicalPreset = Preset.DIRECT_CODEC.encodeStart(JsonOps.INSTANCE, preset)
                .getOrThrow(message -> new IllegalArgumentException("could not encode FTF preset: " + message));
            Files.writeString(canonicalPresetPath, canonicalPreset.toString(), StandardCharsets.UTF_8);
            HolderLookup.Provider registries = fabricDataGenerator.getRegistries().join();
            Path dataRoot = outputPath.resolveSibling(outputPath.getFileName() + "-work");
            DataGenerator generator = Datapacks.makePreset(
                preset, registries, dataRoot, outputPath, "Squinch generated FTF preset datapack"
            );
            generator.run();
        } catch (Exception exception) {
            throw new IllegalStateException("FTF preset export failed", exception);
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
