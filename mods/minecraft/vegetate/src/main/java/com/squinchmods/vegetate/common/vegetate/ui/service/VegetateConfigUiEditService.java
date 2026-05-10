package com.squinchmods.vegetate.common.vegetate.ui.service;

import com.squinchmods.vegetate.common.vegetate.ui.model.ConfigUiEntryId;
import com.squinchmods.vegetate.common.vegetate.rules.VegetateConfigService;
import com.squinchmods.vegetate.common.vegetate.rules.VegetationFeatureRule;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.VegetationCategory;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.VegetationCategoryResolver;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.BiomeVegetationIndex;
import net.minecraft.resources.ResourceLocation;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

public final class VegetateConfigUiEditService implements ConfigUiEditService {
    private final VegetateConfigService configService;
    private final BiomeVegetationIndex index;
    private final Map<String, Boolean> pendingEnabled = new HashMap<>();

    private Boolean pendingDisableAllMushrooms = null;

    public VegetateConfigUiEditService(VegetateConfigService configService, BiomeVegetationIndex index) {
        this.configService = Objects.requireNonNull(configService, "configService cannot be null");
        this.index = Objects.requireNonNull(index, "index cannot be null");
    }

    @Override
    public boolean isEnabled(ConfigUiEntryId id) {
        if (pendingEnabled.containsKey(id.value())) return pendingEnabled.get(id.value());
        VegetationFeatureRule rule = configService.getConfig().getFeatureRules().get(id.value());
        return rule == null || rule.isEnabled();
    }

    @Override
    public void setEnabled(ConfigUiEntryId id, boolean enabled) {
        pendingEnabled.put(id.value(), enabled);
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
    public boolean hasUnsavedChanges(ConfigUiEntryId id) {
        return pendingEnabled.containsKey(id.value());
    }

    @Override
    public void reset(ConfigUiEntryId id) {
        pendingEnabled.remove(id.value());
    }

    @Override
    public void resetAll() {
        pendingEnabled.clear();
        pendingDisableAllMushrooms = null;
    }

    private VegetationFeatureRule getOrCreateRule(String id) {
        return configService.getConfig().getFeatureRules().computeIfAbsent(id, k -> {
            var discovered = index.getEntry(ResourceLocation.tryParse(k));
            if (discovered.isPresent()) {
                var e = discovered.get();
                return new VegetationFeatureRule(e.category().name());
            }
            return new VegetationFeatureRule("unknown");
        });
    }

    public void applyToConfig() {
        if (pendingDisableAllMushrooms != null) configService.getConfig().disableAllMushrooms = pendingDisableAllMushrooms;

        for (Map.Entry<String, Boolean> entry : pendingEnabled.entrySet()) {
            getOrCreateRule(entry.getKey()).setEnabled(entry.getValue());
        }

        resetAll();
    }
}
