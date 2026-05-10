package com.squinchmods.vegetate.common.vegetate.rules;

import com.squinchmods.vegetate.common.vegetate.rules.serialization.VegetateConfigSerializer;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public class VegetateConfigService {

    private static final Logger LOGGER = LoggerFactory.getLogger("VegetateConfigService");
    private static final Path CONFIG_PATH = Path.of("config", "vegetate.json");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    private VegetateConfig config = new VegetateConfig();

    public VegetateConfigService() {
    }

    public void create() {
        if (Files.exists(CONFIG_PATH)) {
            return;
        }
        this.save();
    }

    public void load() {
        if (!Files.exists(CONFIG_PATH)) {
            return;
        }

        try {
            LOGGER.info("Loading Vegetate config from {}", CONFIG_PATH);
            String jsonString = Files.readString(CONFIG_PATH);
            JsonObject json = GSON.fromJson(jsonString, JsonObject.class);
            VegetateConfigSerializer.deserialize(json, this.config);
        } catch (IOException e) {
            LOGGER.error("Failed to load Vegetate config", e);
        }
    }

    public void save() {
        try {
            LOGGER.info("Saving Vegetate config to {}", CONFIG_PATH);
            Files.createDirectories(CONFIG_PATH.getParent());
            JsonObject json = VegetateConfigSerializer.serialize(this.config, true);
            Files.writeString(CONFIG_PATH, GSON.toJson(json));
        } catch (IOException e) {
            LOGGER.error("Failed to save Vegetate config", e);
        }
    }

    public VegetateConfig getConfig() {
        return config;
    }

    public boolean isFeatureEnabled(String featureId) {
        VegetationFeatureRule rule = config.getFeatureRules().get(featureId);

        if (rule != null && config.disableAllMushrooms && rule.isMushroom()) {
            return false;
        }

        if (rule != null) {
            return rule.isEnabled();
        }

        return true;
    }
}
