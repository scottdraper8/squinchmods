package com.squinchmods.treeify.common.treeify.rules;

import com.squinchmods.treeify.common.treeify.rules.serialization.TreeifyConfigSerializer;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public class TreeifyConfigService {

    private static final Logger LOGGER = LoggerFactory.getLogger("TreeifyConfigService");
    private static final Path CONFIG_PATH = Path.of("config", "treeify.json");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    private TreeifyConfig config = new TreeifyConfig();

    public TreeifyConfigService() {
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
            LOGGER.info("Loading Treeify config from {}", CONFIG_PATH);
            String jsonString = Files.readString(CONFIG_PATH);
            JsonObject json = GSON.fromJson(jsonString, JsonObject.class);
            TreeifyConfigSerializer.deserialize(json, this.config);
        } catch (IOException e) {
            LOGGER.error("Failed to load Treeify config", e);
        }
    }

    public void save() {
        try {
            LOGGER.info("Saving Treeify config to {}", CONFIG_PATH);
            Files.createDirectories(CONFIG_PATH.getParent());
            JsonObject json = TreeifyConfigSerializer.serialize(this.config, true);
            Files.writeString(CONFIG_PATH, GSON.toJson(json));
        } catch (IOException e) {
            LOGGER.error("Failed to save Treeify config", e);
        }
    }

    public TreeifyConfig getConfig() {
        return config;
    }

    /**
     * Inheritance logic for feature enablement.
     * Precedence: Global General Kill-switch > Biome Override > Global Feature Rule.
     */
    public boolean isFeatureEnabled(String featureId, String biomeId) {
        VegetationFeatureRule globalRule = config.getFeatureRules().get(featureId);

        // 1. Global General Kill-switches
        if (globalRule != null) {
            if (config.disableAllTrees && globalRule.isTree()) return false;
            if (config.disableAllMushrooms && globalRule.isMushroom()) return false;
        }

        // 2. Biome Overrides
        BiomeOverrideRule biomeOverride = config.getBiomeOverrides().get(biomeId);
        if (biomeOverride != null) {
            if (biomeOverride.getDisabledFeatures().contains(featureId)) return false;
            if (biomeOverride.getAddedFeatures().contains(featureId)) return true;
        }

        // 3. Global Feature Rule
        if (globalRule != null) {
            return globalRule.isEnabled();
        }

        return true;
    }

    /**
     * Inheritance logic for density multiplier.
     * Result is multiplicative: global * feature * biome.
     */
    public float getDensityMultiplier(String featureId, String biomeId) {
        float multiplier = 1.0f;

        VegetationFeatureRule globalRule = config.getFeatureRules().get(featureId);

        // 1. Global General Multipliers
        if (globalRule != null) {
            if (globalRule.isTree()) multiplier *= config.globalTreeDensityMultiplier;
            if (globalRule.isMushroom()) multiplier *= config.globalMushroomDensityMultiplier;
        }

        // 2. Global Feature Multiplier
        if (globalRule != null && globalRule.supportsDensity()) {
            multiplier *= globalRule.getDensityMultiplier();
        }

        // 3. Biome Override
        BiomeOverrideRule biomeOverride = config.getBiomeOverrides().get(biomeId);
        if (biomeOverride != null && biomeOverride.getDensityOverrides().containsKey(featureId)) {
            multiplier *= biomeOverride.getDensityOverrides().get(featureId);
        }

        return multiplier;
    }

    /**
     * Inheritance logic for height delta.
     * Result is additive: feature + biome.
     */
    public int getHeightDelta(String featureId, String biomeId) {
        int delta = 0;

        VegetationFeatureRule globalRule = config.getFeatureRules().get(featureId);

        // 1. Global Feature Rule
        if (globalRule != null && globalRule.supportsHeight()) {
            delta += globalRule.getHeightDelta();
        }

        // 2. Biome Override
        BiomeOverrideRule biomeOverride = config.getBiomeOverrides().get(biomeId);
        if (biomeOverride != null && biomeOverride.getHeightOverrides().containsKey(featureId)) {
            delta += biomeOverride.getHeightOverrides().get(featureId);
        }

        return delta;
    }
}
