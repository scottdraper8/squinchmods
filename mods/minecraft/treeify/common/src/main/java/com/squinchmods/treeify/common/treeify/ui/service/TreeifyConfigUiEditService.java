package com.squinchmods.treeify.common.treeify.ui.service;

import com.squinchmods.treeify.common.treeify.ui.model.ConfigUiEntryId;
import com.squinchmods.treeify.common.treeify.rules.TreeifyConfigService;
import com.squinchmods.treeify.common.treeify.rules.VegetationFeatureRule;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.VegetationCategory;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.VegetationCategoryResolver;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.BiomeVegetationIndex;
import net.minecraft.resources.Identifier;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

public final class TreeifyConfigUiEditService implements ConfigUiEditService {
    private final TreeifyConfigService configService;
    private final BiomeVegetationIndex index;
    private final Map<String, Boolean> pendingEnabled = new HashMap<>();
    private final Map<String, Float> pendingDensity = new HashMap<>();
    private final Map<String, Integer> pendingHeight = new HashMap<>();
    
    private Boolean pendingDisableAllTrees = null;
    private Boolean pendingDisableAllMushrooms = null;
    private Float pendingGlobalTreeDensity = null;
    private Float pendingGlobalMushroomDensity = null;

    public TreeifyConfigUiEditService(TreeifyConfigService configService, BiomeVegetationIndex index) {
        this.configService = Objects.requireNonNull(configService, "configService cannot be null");
        this.index = Objects.requireNonNull(index, "index cannot be null");
    }

    @Override
    public boolean isEnabled(ConfigUiEntryId id) {
        if (isDisabledByGlobalSwitch(id)) {
            return false;
        }

        if (pendingEnabled.containsKey(id.value())) return pendingEnabled.get(id.value());
        VegetationFeatureRule rule = configService.getConfig().getFeatureRules().get(id.value());
        return rule == null || rule.isEnabled();
    }

    @Override
    public void setEnabled(ConfigUiEntryId id, boolean enabled) {
        pendingEnabled.put(id.value(), enabled);
    }

    @Override
    public float getDensityMultiplier(ConfigUiEntryId id) {
        if (pendingDensity.containsKey(id.value())) return pendingDensity.get(id.value());
        VegetationFeatureRule rule = configService.getConfig().getFeatureRules().get(id.value());
        return rule == null ? VegetationFeatureRule.DENSITY_MULTIPLIER_DEFAULT : rule.getDensityMultiplier();
    }

    @Override
    public void setDensityMultiplier(ConfigUiEntryId id, float multiplier) {
        pendingDensity.put(id.value(), multiplier);
    }

    @Override
    public int getHeightDelta(ConfigUiEntryId id) {
        if (pendingHeight.containsKey(id.value())) return pendingHeight.get(id.value());
        VegetationFeatureRule rule = configService.getConfig().getFeatureRules().get(id.value());
        return rule == null ? VegetationFeatureRule.HEIGHT_DELTA_DEFAULT : rule.getHeightDelta();
    }

    @Override
    public void setHeightDelta(ConfigUiEntryId id, int delta) {
        pendingHeight.put(id.value(), delta);
    }

    @Override
    public boolean getDisableAllTrees() {
        return pendingDisableAllTrees != null ? pendingDisableAllTrees : configService.getConfig().disableAllTrees;
    }

    @Override
    public void setDisableAllTrees(boolean value) {
        pendingDisableAllTrees = value;
    }

    @Override
    public boolean getDisableAllMushrooms() {
        return pendingDisableAllMushrooms != null ? pendingDisableAllMushrooms : configService.getConfig().disableAllMushrooms;
    }

    @Override
    public void setDisableAllMushrooms(boolean value) {
        pendingDisableAllMushrooms = value;
    }

    @Override
    public float getGlobalTreeDensityMultiplier() {
        return pendingGlobalTreeDensity != null ? pendingGlobalTreeDensity : configService.getConfig().globalTreeDensityMultiplier;
    }

    @Override
    public void setGlobalTreeDensityMultiplier(float value) {
        pendingGlobalTreeDensity = value;
    }

    @Override
    public float getGlobalMushroomDensityMultiplier() {
        return pendingGlobalMushroomDensity != null ? pendingGlobalMushroomDensity : configService.getConfig().globalMushroomDensityMultiplier;
    }

    @Override
    public void setGlobalMushroomDensityMultiplier(float value) {
        pendingGlobalMushroomDensity = value;
    }

    @Override
    public boolean hasUnsavedChanges(ConfigUiEntryId id) {
        return pendingEnabled.containsKey(id.value()) || pendingDensity.containsKey(id.value()) || pendingHeight.containsKey(id.value());
    }

    @Override
    public void reset(ConfigUiEntryId id) {
        pendingEnabled.remove(id.value());
        pendingDensity.remove(id.value());
        pendingHeight.remove(id.value());
    }

    @Override
    public void resetAll() {
        pendingEnabled.clear();
        pendingDensity.clear();
        pendingHeight.clear();
        pendingDisableAllTrees = null;
        pendingDisableAllMushrooms = null;
        pendingGlobalTreeDensity = null;
        pendingGlobalMushroomDensity = null;
    }

    private VegetationFeatureRule getOrCreateRule(String id) {
        return configService.getConfig().getFeatureRules().computeIfAbsent(id, k -> {
            var discovered = index.getEntry(Identifier.tryParse(k));
            if (discovered.isPresent()) {
                var e = discovered.get();
                return new VegetationFeatureRule(
                    e.category().name(),
                    e.support() != com.squinchmods.treeify.common.treeify.ui.model.ConfigUiEntrySupport.UNSUPPORTED,
                    e.support() == com.squinchmods.treeify.common.treeify.ui.model.ConfigUiEntrySupport.FULL
                );
            }
            return new VegetationFeatureRule("unknown", true, true);
        });
    }

    private boolean isDisabledByGlobalSwitch(ConfigUiEntryId id) {
        var discovered = index.getEntry(Identifier.tryParse(id.value()));
        VegetationFeatureRule rule = configService.getConfig().getFeatureRules().get(id.value());
        VegetationCategory category = VegetationCategoryResolver.resolve(
                id.value(),
                rule == null ? null : rule.getCategory(),
                discovered.map(entry -> entry.category()).orElse(null)
        );

        boolean disableTrees = getDisableAllTrees();
        boolean disableMushrooms = getDisableAllMushrooms();

        return (disableTrees && VegetationCategoryResolver.isTreeCategory(category, id.value()))
                || (disableMushrooms && VegetationCategoryResolver.isMushroomCategory(category, id.value()));
    }

    public void applyToConfig() {
        if (pendingDisableAllTrees != null) configService.getConfig().disableAllTrees = pendingDisableAllTrees;
        if (pendingDisableAllMushrooms != null) configService.getConfig().disableAllMushrooms = pendingDisableAllMushrooms;
        if (pendingGlobalTreeDensity != null) configService.getConfig().globalTreeDensityMultiplier = pendingGlobalTreeDensity;
        if (pendingGlobalMushroomDensity != null) configService.getConfig().globalMushroomDensityMultiplier = pendingGlobalMushroomDensity;

        for (Map.Entry<String, Boolean> entry : pendingEnabled.entrySet()) {
            getOrCreateRule(entry.getKey()).setEnabled(entry.getValue());
        }
        for (Map.Entry<String, Float> entry : pendingDensity.entrySet()) {
            getOrCreateRule(entry.getKey()).setDensityMultiplier(entry.getValue());
        }
        for (Map.Entry<String, Integer> entry : pendingHeight.entrySet()) {
            getOrCreateRule(entry.getKey()).setHeightDelta(entry.getValue());
        }

        resetAll();
    }
}
