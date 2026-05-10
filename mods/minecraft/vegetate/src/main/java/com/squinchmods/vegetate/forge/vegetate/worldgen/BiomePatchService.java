package com.squinchmods.vegetate.forge.vegetate.worldgen;

import com.squinchmods.vegetate.common.vegetate.rules.VegetateConfigService;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.VegetationCategory;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.VegetationCategoryResolver;
import com.squinchmods.vegetate.common.vegetate.worldgen.discovery.VegetationFeatureClassifier;
import java.util.List;
import net.minecraft.core.Holder;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.WeightedPlacedFeature;
import net.minecraft.world.level.levelgen.feature.configurations.RandomFeatureConfiguration;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import org.jetbrains.annotations.Nullable;

public class BiomePatchService {

  private final VegetateConfigService configService;

  public BiomePatchService(VegetateConfigService configService) {
    this.configService = configService;
  }

  public PatchDecision planPatch(
      ResourceLocation biomeId, ResourceLocation featureId, Holder<PlacedFeature> original) {
    if (!configService.isFeatureEnabled(featureId.toString())) {
      return PatchDecision.remove();
    }

    PlacedFeature prunedFeature = tryPrunePlacedFeature(original.value());
    if (prunedFeature == null) {
      return PatchDecision.remove();
    }
    if (!prunedFeature.equals(original.value())) {
      return PatchDecision.replace(Holder.direct(prunedFeature));
    }

    return PatchDecision.keep();
  }

  private @Nullable PlacedFeature tryPrunePlacedFeature(PlacedFeature original) {
    if (!configService.getConfig().disableAllMushrooms) {
      return original;
    }

    if (isMushroomFeature(original)) {
      return null;
    }

    if (original.feature().value().feature() == Feature.RANDOM_SELECTOR) {
      return pruneMushroomsFromRandomSelector(original);
    }

    return original;
  }

  @SuppressWarnings("unchecked")
  private @Nullable PlacedFeature pruneMushroomsFromRandomSelector(PlacedFeature original) {
    RandomFeatureConfiguration config =
        (RandomFeatureConfiguration) original.feature().value().config();

    List<WeightedPlacedFeature> filtered =
        config.features.stream().filter(w -> !isMushroomFeature(w.feature.value())).toList();

    if (filtered.size() == config.features.size()) {
      return original;
    }

    Holder<PlacedFeature> defaultFeature = config.defaultFeature;
    if (isMushroomFeature(defaultFeature.value())) {
      if (filtered.isEmpty()) {
        return null;
      }
      // Promote the last remaining entry to default and remove it from the weighted list
      // to avoid it being double-counted.
      WeightedPlacedFeature promoted = filtered.get(filtered.size() - 1);
      filtered = filtered.subList(0, filtered.size() - 1);
      defaultFeature = promoted.feature;
    }

    ConfiguredFeature<?, ?> newCf =
        new ConfiguredFeature<>(
            Feature.RANDOM_SELECTOR, new RandomFeatureConfiguration(filtered, defaultFeature));
    return new PlacedFeature(Holder.direct(newCf), original.placement());
  }

  private boolean isMushroomFeature(PlacedFeature placedFeature) {
    ConfiguredFeature<?, ?> cf = placedFeature.feature().value();
    VegetationCategory category = VegetationFeatureClassifier.classify(placedFeature).category();
    return VegetationCategoryResolver.isMushroomCategory(category, cf.feature().toString());
  }

  public record PatchDecision(boolean removeOriginal, @Nullable Holder<PlacedFeature> replacement) {
    public static PatchDecision keep() {
      return new PatchDecision(false, null);
    }

    public static PatchDecision remove() {
      return new PatchDecision(true, null);
    }

    public static PatchDecision replace(Holder<PlacedFeature> replacement) {
      return new PatchDecision(true, replacement);
    }
  }
}
