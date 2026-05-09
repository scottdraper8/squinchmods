package com.squinchmods.treeify.common.treeify.rules;

import java.util.Map;
import java.util.TreeMap;

public class TreeifyConfig {

    public boolean disableAllTrees = false;
    public boolean disableAllMushrooms = false;
    public float globalTreeDensityMultiplier = 1.0f;
    public float globalMushroomDensityMultiplier = 1.0f;

    private final Map<String, VegetationFeatureRule> featureRules = new TreeMap<>();
    private final Map<String, BiomeOverrideRule> biomeOverrides = new TreeMap<>();

    public TreeifyConfig() {
    }

    public Map<String, VegetationFeatureRule> getFeatureRules() {
        return featureRules;
    }

    public Map<String, BiomeOverrideRule> getBiomeOverrides() {
        return biomeOverrides;
    }
}
