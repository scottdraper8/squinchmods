package com.squinchmods.vegetate.common.vegetate.worldgen.discovery;

import java.util.Locale;
import org.jetbrains.annotations.Nullable;

public final class VegetationCategoryResolver {

  public static VegetationCategory resolve(
      String featureId,
      @Nullable String storedCategory,
      @Nullable VegetationCategory discoveredCategory) {
    if (discoveredCategory != null && discoveredCategory != VegetationCategory.OPAQUE) {
      return discoveredCategory;
    }

    if (storedCategory != null && !storedCategory.isBlank()) {
      try {
        VegetationCategory category =
            VegetationCategory.valueOf(storedCategory.toUpperCase(Locale.ROOT));
        if (category != VegetationCategory.OPAQUE) {
          return category;
        }
      } catch (IllegalArgumentException ignored) {
      }
    }

    String normalizedId = featureId.toLowerCase(Locale.ROOT);

    if (normalizedId.contains("mushroom")
        || normalizedId.contains("fungi")
        || normalizedId.contains("fungus")) {
      return VegetationCategory.DIRECT_HUGE_MUSHROOM;
    }

    return discoveredCategory != null ? discoveredCategory : VegetationCategory.OPAQUE;
  }

  public static boolean isMushroomCategory(VegetationCategory category, String featureId) {
    if (category == VegetationCategory.DIRECT_HUGE_MUSHROOM
        || category == VegetationCategory.MUSHROOM_PATCH) {
      return true;
    }

    String normalizedId = featureId.toLowerCase(Locale.ROOT);
    return normalizedId.contains("mushroom")
        || normalizedId.contains("fungi")
        || normalizedId.contains("fungus");
  }

  private VegetationCategoryResolver() {}
}
