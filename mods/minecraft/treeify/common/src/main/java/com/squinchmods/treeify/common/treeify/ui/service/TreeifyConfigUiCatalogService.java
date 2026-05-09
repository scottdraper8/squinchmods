package com.squinchmods.treeify.common.treeify.ui.service;

import com.squinchmods.treeify.common.treeify.ui.model.*;
import com.squinchmods.treeify.common.treeify.rules.TreeifyConfigService;
import com.squinchmods.treeify.common.treeify.rules.VegetationFeatureRule;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.BiomeVegetationIndex;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.DiscoveredVegetationEntry;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.VegetationCategory;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.VegetationCategoryResolver;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import java.util.*;

public final class TreeifyConfigUiCatalogService implements ConfigUiCatalogService {
    private final TreeifyConfigService configService;
    private final BiomeVegetationIndex index;

    public TreeifyConfigUiCatalogService(TreeifyConfigService configService, BiomeVegetationIndex index) {
        this.configService = Objects.requireNonNull(configService, "configService cannot be null");
        this.index = Objects.requireNonNull(index, "index cannot be null");
    }

    @Override
    public ConfigUiCatalogSnapshot getCatalogSnapshot() {
        Map<VegetationCategory, List<ConfigUiEntryView>> categorized = new EnumMap<>(VegetationCategory.class);
        Set<String> seenIds = new HashSet<>();

        for (DiscoveredVegetationEntry entry : index.getAllEntries()) {
            seenIds.add(entry.featureId().toString());
            addEntry(categorized, entry.featureId().toString(), entry.category(), entry.support());
        }

        for (Map.Entry<String, VegetationFeatureRule> entry : configService.getConfig().getFeatureRules().entrySet()) {
            if (seenIds.add(entry.getKey())) {
                VegetationCategory category = VegetationCategoryResolver.resolve(entry.getKey(), entry.getValue().getCategory(), null);
                addEntry(categorized, entry.getKey(), category, supportFromRule(entry.getValue()));
            }
        }

        List<ConfigUiCategoryView> categories = new ArrayList<>();
        for (Map.Entry<VegetationCategory, List<ConfigUiEntryView>> e : categorized.entrySet()) {
            e.getValue().sort(Comparator.comparing(view -> view.id().value()));
            categories.add(new ConfigUiCategoryView(
                e.getKey().name(),
                Component.literal(e.getKey().name()),
                Optional.empty(),
                e.getValue()
            ));
        }

        return new ConfigUiCatalogSnapshot(
            Component.translatable("gui.treeify.config.title"),
            categories,
            Optional.empty()
        );
    }

    private static void addEntry(
            Map<VegetationCategory, List<ConfigUiEntryView>> categorized,
            String featureId,
            VegetationCategory category,
            ConfigUiEntrySupport support
    ) {
        categorized.computeIfAbsent(category, k -> new ArrayList<>())
                .add(new ConfigUiEntryView(
                        new ConfigUiEntryId(featureId),
                        Component.literal(featureId),
                        Optional.empty(),
                        true,
                        support,
                        Optional.empty()
                ));
    }

    private static ConfigUiEntrySupport supportFromRule(VegetationFeatureRule rule) {
        if (rule.supportsDensity() && rule.supportsHeight()) {
            return ConfigUiEntrySupport.FULL;
        }

        if (rule.supportsDensity() || rule.supportsHeight()) {
            return ConfigUiEntrySupport.PARTIAL;
        }

        return ConfigUiEntrySupport.UNSUPPORTED;
    }
}
