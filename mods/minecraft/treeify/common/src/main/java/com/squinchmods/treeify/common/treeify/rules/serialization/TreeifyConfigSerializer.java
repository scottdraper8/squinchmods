package com.squinchmods.treeify.common.treeify.rules.serialization;

import com.squinchmods.treeify.common.treeify.rules.BiomeOverrideRule;
import com.squinchmods.treeify.common.treeify.rules.TreeifyConfig;
import com.squinchmods.treeify.common.treeify.rules.VegetationFeatureRule;
import com.google.gson.*;

import java.util.Map;

public class TreeifyConfigSerializer {

    private static final String GENERAL = "general";
    private static final String DISABLE_ALL_TREES = "disable_all_trees";
    private static final String DISABLE_ALL_MUSHROOMS = "disable_all_mushrooms";
    private static final String GLOBAL_TREE_DENSITY_MULTIPLIER = "global_tree_density_multiplier";
    private static final String GLOBAL_MUSHROOM_DENSITY_MULTIPLIER = "global_mushroom_density_multiplier";

    private static final String FEATURES = "features";
    private static final String BIOMES = "biomes";

    private static final String NAME = "name";
    private static final String CATEGORY = "category";
    private static final String ENABLED = "enabled";
    private static final String SUPPORTS_DENSITY = "supports_density";
    private static final String SUPPORTS_HEIGHT = "supports_height";
    private static final String DENSITY_MULTIPLIER = "density_multiplier";
    private static final String HEIGHT_DELTA = "height_delta";

    private static final String DISABLED_FEATURES = "disabled_features";
    private static final String ADDED_FEATURES = "added_features";
    private static final String DENSITY_OVERRIDES = "density_overrides";
    private static final String HEIGHT_OVERRIDES = "height_overrides";

    public static JsonObject serialize(TreeifyConfig config, boolean saveOnlyChanged) {
        JsonObject json = new JsonObject();

        // General
        JsonObject general = new JsonObject();
        general.addProperty(DISABLE_ALL_TREES, config.disableAllTrees);
        general.addProperty(DISABLE_ALL_MUSHROOMS, config.disableAllMushrooms);
        general.addProperty(GLOBAL_TREE_DENSITY_MULTIPLIER, config.globalTreeDensityMultiplier);
        general.addProperty(GLOBAL_MUSHROOM_DENSITY_MULTIPLIER, config.globalMushroomDensityMultiplier);
        json.add(GENERAL, general);

        // Features
        JsonArray features = new JsonArray();
        for (Map.Entry<String, VegetationFeatureRule> entry : config.getFeatureRules().entrySet()) {
            if (!saveOnlyChanged || !entry.getValue().isUsingDefaultValues()) {
                JsonObject featureJson = new JsonObject();
                featureJson.addProperty(NAME, entry.getKey());
                featureJson.addProperty(CATEGORY, entry.getValue().getCategory());
                featureJson.addProperty(ENABLED, entry.getValue().isEnabled());
                featureJson.addProperty(SUPPORTS_DENSITY, entry.getValue().supportsDensity());
                featureJson.addProperty(SUPPORTS_HEIGHT, entry.getValue().supportsHeight());
                if (entry.getValue().supportsDensity()) {
                    featureJson.addProperty(DENSITY_MULTIPLIER, entry.getValue().getDensityMultiplier());
                }
                if (entry.getValue().supportsHeight()) {
                    featureJson.addProperty(HEIGHT_DELTA, entry.getValue().getHeightDelta());
                }
                features.add(featureJson);
            }
        }
        json.add(FEATURES, features);

        // Biomes
        JsonArray biomes = new JsonArray();
        for (Map.Entry<String, BiomeOverrideRule> entry : config.getBiomeOverrides().entrySet()) {
            if (!saveOnlyChanged || !entry.getValue().isUsingDefaultValues()) {
                JsonObject biomeJson = new JsonObject();
                biomeJson.addProperty(NAME, entry.getKey());

                BiomeOverrideRule rule = entry.getValue();
                
                if (!rule.getDisabledFeatures().isEmpty()) {
                    JsonArray disabled = new JsonArray();
                    rule.getDisabledFeatures().stream().sorted().forEach(disabled::add);
                    biomeJson.add(DISABLED_FEATURES, disabled);
                }

                if (!rule.getAddedFeatures().isEmpty()) {
                    JsonArray added = new JsonArray();
                    rule.getAddedFeatures().stream().sorted().forEach(added::add);
                    biomeJson.add(ADDED_FEATURES, added);
                }

                if (!rule.getDensityOverrides().isEmpty()) {
                    JsonObject density = new JsonObject();
                    rule.getDensityOverrides().entrySet().stream()
                        .sorted(Map.Entry.comparingByKey())
                        .forEach(e -> density.addProperty(e.getKey(), e.getValue()));
                    biomeJson.add(DENSITY_OVERRIDES, density);
                }

                if (!rule.getHeightOverrides().isEmpty()) {
                    JsonObject height = new JsonObject();
                    rule.getHeightOverrides().entrySet().stream()
                        .sorted(Map.Entry.comparingByKey())
                        .forEach(e -> height.addProperty(e.getKey(), e.getValue()));
                    biomeJson.add(HEIGHT_OVERRIDES, height);
                }

                biomes.add(biomeJson);
            }
        }
        json.add(BIOMES, biomes);

        return json;
    }

    public static void deserialize(JsonObject json, TreeifyConfig config) {
        if (json.has(GENERAL)) {
            JsonObject general = json.getAsJsonObject(GENERAL);
            if (general.has(DISABLE_ALL_TREES)) config.disableAllTrees = general.get(DISABLE_ALL_TREES).getAsBoolean();
            if (general.has(DISABLE_ALL_MUSHROOMS)) config.disableAllMushrooms = general.get(DISABLE_ALL_MUSHROOMS).getAsBoolean();
            if (general.has(GLOBAL_TREE_DENSITY_MULTIPLIER)) config.globalTreeDensityMultiplier = general.get(GLOBAL_TREE_DENSITY_MULTIPLIER).getAsFloat();
            if (general.has(GLOBAL_MUSHROOM_DENSITY_MULTIPLIER)) config.globalMushroomDensityMultiplier = general.get(GLOBAL_MUSHROOM_DENSITY_MULTIPLIER).getAsFloat();
        }

        if (json.has(FEATURES)) {
            JsonArray features = json.getAsJsonArray(FEATURES);
            for (JsonElement element : features) {
                JsonObject featureJson = element.getAsJsonObject();
                if (featureJson.has(NAME)) {
                    String name = featureJson.get(NAME).getAsString();
                    String category = featureJson.has(CATEGORY) ? featureJson.get(CATEGORY).getAsString() : "unknown";
                    boolean supportsDensity = !featureJson.has(SUPPORTS_DENSITY) || featureJson.get(SUPPORTS_DENSITY).getAsBoolean();
                    boolean supportsHeight = !featureJson.has(SUPPORTS_HEIGHT) || featureJson.get(SUPPORTS_HEIGHT).getAsBoolean();

                    VegetationFeatureRule rule = config.getFeatureRules().computeIfAbsent(
                            name,
                            ignored -> new VegetationFeatureRule(category, supportsDensity, supportsHeight)
                    );

                    if (featureJson.has(ENABLED)) rule.setEnabled(featureJson.get(ENABLED).getAsBoolean());
                    if (featureJson.has(DENSITY_MULTIPLIER)) rule.setDensityMultiplier(featureJson.get(DENSITY_MULTIPLIER).getAsFloat());
                    if (featureJson.has(HEIGHT_DELTA)) rule.setHeightDelta(featureJson.get(HEIGHT_DELTA).getAsInt());
                }
            }
        }

        if (json.has(BIOMES)) {
            JsonArray biomes = json.getAsJsonArray(BIOMES);
            for (JsonElement element : biomes) {
                JsonObject biomeJson = element.getAsJsonObject();
                if (biomeJson.has(NAME)) {
                    String name = biomeJson.get(NAME).getAsString();
                    BiomeOverrideRule rule = config.getBiomeOverrides().computeIfAbsent(name, k -> new BiomeOverrideRule());
                    
                    if (biomeJson.has(DISABLED_FEATURES)) {
                        biomeJson.getAsJsonArray(DISABLED_FEATURES).forEach(e -> rule.disableFeature(e.getAsString()));
                    }
                    if (biomeJson.has(ADDED_FEATURES)) {
                        biomeJson.getAsJsonArray(ADDED_FEATURES).forEach(e -> rule.addFeature(e.getAsString()));
                    }
                    if (biomeJson.has(DENSITY_OVERRIDES)) {
                        JsonObject density = biomeJson.getAsJsonObject(DENSITY_OVERRIDES);
                        density.entrySet().forEach(e -> rule.setDensityOverride(e.getKey(), e.getValue().getAsFloat()));
                    }
                    if (biomeJson.has(HEIGHT_OVERRIDES)) {
                        JsonObject height = biomeJson.getAsJsonObject(HEIGHT_OVERRIDES);
                        height.entrySet().forEach(e -> rule.setHeightOverride(e.getKey(), e.getValue().getAsInt()));
                    }
                }
            }
        }
    }
}
