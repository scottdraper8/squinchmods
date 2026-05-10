package com.squinchmods.vegetate.common.vegetate.ui.service;

import com.squinchmods.vegetate.common.vegetate.ui.model.ConfigUiCatalogSnapshot;
import com.squinchmods.vegetate.common.vegetate.ui.model.ConfigUiCategoryView;
import com.squinchmods.vegetate.common.vegetate.ui.model.ConfigUiEntryId;
import com.squinchmods.vegetate.common.vegetate.ui.model.ConfigUiEntryView;
import com.squinchmods.vegetate.common.vegetate.rules.VegetateConfigService;
import com.squinchmods.vegetate.common.vegetate.rules.VegetationFeatureRule;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.BiomeVegetationIndex;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.DiscoveredVegetationEntry;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.VegetationCategory;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.VegetationCategoryResolver;
import net.minecraft.network.chat.Component;
import java.util.*;

public final class VegetateConfigUiCatalogService implements ConfigUiCatalogService {
    private final VegetateConfigService configService;
    private final BiomeVegetationIndex index;

    public VegetateConfigUiCatalogService(VegetateConfigService configService, BiomeVegetationIndex index) {
        this.configService = Objects.requireNonNull(configService, "configService cannot be null");
        this.index = Objects.requireNonNull(index, "index cannot be null");
    }

    @Override
    public ConfigUiCatalogSnapshot getCatalogSnapshot() {
        Map<VegetationCategory, List<ConfigUiEntryView>> categorized = new EnumMap<>(VegetationCategory.class);
        Set<String> seenIds = new HashSet<>();

        for (DiscoveredVegetationEntry entry : index.getAllEntries()) {
            String id = entry.featureId().toString();
            if (VegetationCategoryResolver.isMushroomCategory(entry.category(), id)) {
                seenIds.add(id);
                addEntry(categorized, id, entry.category());
            }
        }

        for (Map.Entry<String, VegetationFeatureRule> entry : configService.getConfig().getFeatureRules().entrySet()) {
            if (seenIds.add(entry.getKey())) {
                VegetationCategory category = VegetationCategoryResolver.resolve(entry.getKey(), entry.getValue().getCategory(), null);
                if (VegetationCategoryResolver.isMushroomCategory(category, entry.getKey())) {
                    addEntry(categorized, entry.getKey(), category);
                }
            }
        }

        List<ConfigUiCategoryView> categories = new ArrayList<>();
        for (Map.Entry<VegetationCategory, List<ConfigUiEntryView>> e : categorized.entrySet()) {
            e.getValue().sort(Comparator.comparing(view -> view.id().value()));
            categories.add(new ConfigUiCategoryView(
                e.getKey().name(),
                Component.literal(formatCategoryName(e.getKey())),
                Optional.empty(),
                e.getValue()
            ));
        }

        return new ConfigUiCatalogSnapshot(
            Component.translatable("vegetate.gui.title"),
            categories,
            Optional.empty()
        );
    }

    private static void addEntry(
            Map<VegetationCategory, List<ConfigUiEntryView>> categorized,
            String featureId,
            VegetationCategory category
    ) {
        categorized.computeIfAbsent(category, k -> new ArrayList<>())
                .add(new ConfigUiEntryView(
                        new ConfigUiEntryId(featureId),
                        Component.literal(featureId),
                        Optional.empty(),
                        true
                ));
    }

    private static String formatCategoryName(VegetationCategory category) {
        return switch (category) {
            case DIRECT_HUGE_MUSHROOM -> "Huge Mushrooms";
            case MUSHROOM_PATCH -> "Mushroom Patches";
            case OPAQUE -> "Other";
        };
    }
}
