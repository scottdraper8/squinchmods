package com.squinchmods.vegetate.common.vegetate.worldgen.discovery;

import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;

public final class VegetationFeatureClassifier {
  public static ClassificationResult classify(PlacedFeature placedFeature) {
    ConfiguredFeature<?, ?> configuredFeature = placedFeature.feature().value();
    Feature<?> feature = configuredFeature.feature();

    if (feature == Feature.HUGE_RED_MUSHROOM || feature == Feature.HUGE_BROWN_MUSHROOM) {
      return new ClassificationResult(VegetationCategory.DIRECT_HUGE_MUSHROOM);
    }

    return new ClassificationResult(VegetationCategory.OPAQUE);
  }

  public record ClassificationResult(VegetationCategory category) {}
}
