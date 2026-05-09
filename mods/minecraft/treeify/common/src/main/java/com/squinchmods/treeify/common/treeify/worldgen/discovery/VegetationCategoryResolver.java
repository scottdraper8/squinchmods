package com.squinchmods.treeify.common.treeify.worldgen.discovery;

import java.util.Locale;
import org.jetbrains.annotations.Nullable;

public final class VegetationCategoryResolver {

    public static VegetationCategory resolve(String featureId, @Nullable String storedCategory, @Nullable VegetationCategory discoveredCategory) {
        if (discoveredCategory != null && discoveredCategory != VegetationCategory.OPAQUE) {
            return discoveredCategory;
        }

        if (storedCategory != null && !storedCategory.isBlank()) {
            try {
                VegetationCategory category = VegetationCategory.valueOf(storedCategory.toUpperCase(Locale.ROOT));
                if (category != VegetationCategory.OPAQUE) {
                    return category;
                }
            } catch (IllegalArgumentException ignored) {
            }
        }

        String normalizedId = featureId.toLowerCase(Locale.ROOT);

        if (normalizedId.contains("mushroom") || normalizedId.contains("fungi") || normalizedId.contains("fungus")) {
            return VegetationCategory.DIRECT_HUGE_MUSHROOM;
        }

        if (normalizedId.contains("tree")
                || normalizedId.contains("trees")
                || normalizedId.contains("oak")
                || normalizedId.contains("birch")
                || normalizedId.contains("spruce")
                || normalizedId.contains("pine")
                || normalizedId.contains("jungle")
                || normalizedId.contains("mangrove")
                || normalizedId.contains("cherry")
                || normalizedId.contains("taiga")
                || normalizedId.contains("forest_vegetation")) {
            return VegetationCategory.DIRECT_TREE;
        }

        return discoveredCategory != null ? discoveredCategory : VegetationCategory.OPAQUE;
    }

    public static boolean isTreeCategory(VegetationCategory category, String featureId) {
        if (category == VegetationCategory.DIRECT_TREE
                || category == VegetationCategory.TREE_SELECTOR
                || category == VegetationCategory.MIXED_VEGETATION) {
            return true;
        }

        String normalizedId = featureId.toLowerCase(Locale.ROOT);
        return normalizedId.contains("tree")
                || normalizedId.contains("trees")
                || normalizedId.contains("oak")
                || normalizedId.contains("birch")
                || normalizedId.contains("spruce")
                || normalizedId.contains("pine")
                || normalizedId.contains("jungle")
                || normalizedId.contains("mangrove")
                || normalizedId.contains("cherry")
                || normalizedId.contains("taiga")
                || normalizedId.contains("forest_vegetation");
    }

    public static boolean isMushroomCategory(VegetationCategory category, String featureId) {
        if (category == VegetationCategory.DIRECT_HUGE_MUSHROOM || category == VegetationCategory.MUSHROOM_PATCH) {
            return true;
        }

        String normalizedId = featureId.toLowerCase(Locale.ROOT);
        return normalizedId.contains("mushroom") || normalizedId.contains("fungi") || normalizedId.contains("fungus");
    }

    private VegetationCategoryResolver() {
    }
}
