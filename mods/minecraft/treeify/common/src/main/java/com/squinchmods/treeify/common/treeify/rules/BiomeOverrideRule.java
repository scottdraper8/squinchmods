package com.squinchmods.treeify.common.treeify.rules;

import java.util.*;

public class BiomeOverrideRule {

    private final Set<String> disabledFeatures = new HashSet<>();
    private final Set<String> addedFeatures = new HashSet<>();
    private final Map<String, Float> densityOverrides = new HashMap<>();
    private final Map<String, Integer> heightOverrides = new HashMap<>();

    public BiomeOverrideRule() {
    }

    public boolean isUsingDefaultValues() {
        return disabledFeatures.isEmpty() &&
               addedFeatures.isEmpty() &&
               densityOverrides.isEmpty() &&
               heightOverrides.isEmpty();
    }

    public Set<String> getDisabledFeatures() {
        return disabledFeatures;
    }

    public Set<String> getAddedFeatures() {
        return addedFeatures;
    }

    public Map<String, Float> getDensityOverrides() {
        return densityOverrides;
    }

    public Map<String, Integer> getHeightOverrides() {
        return heightOverrides;
    }
    
    public void disableFeature(String featureId) {
        this.disabledFeatures.add(featureId);
        this.addedFeatures.remove(featureId);
    }

    public void enableFeature(String featureId) {
        this.disabledFeatures.remove(featureId);
        // "Added" means it wasn't there naturally but we want it.
        // If it was already there and just disabled, we remove from disabled.
    }
    
    public void addFeature(String featureId) {
        this.addedFeatures.add(featureId);
        this.disabledFeatures.remove(featureId);
    }
    
    public void setDensityOverride(String featureId, float multiplier) {
        this.densityOverrides.put(featureId, multiplier);
    }

    public void setHeightOverride(String featureId, int delta) {
        this.heightOverrides.put(featureId, delta);
    }
}
