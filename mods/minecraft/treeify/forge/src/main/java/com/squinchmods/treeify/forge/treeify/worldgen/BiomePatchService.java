package com.squinchmods.treeify.forge.treeify.worldgen;

import com.squinchmods.treeify.common.treeify.rules.TreeifyConfigService;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.VegetationCategory;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.VegetationCategoryResolver;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.VegetationFeatureClassifier;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.WeightedPlacedFeature;
import net.minecraft.world.level.levelgen.feature.configurations.RandomBooleanFeatureConfiguration;
import net.minecraft.world.level.levelgen.feature.configurations.RandomFeatureConfiguration;
import net.minecraft.world.level.levelgen.feature.configurations.SimpleRandomFeatureConfiguration;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;

import java.util.ArrayList;
import java.util.List;

/**
 * Service for resolving Treeify rules and constructing patched biome features.
 */
public class BiomePatchService {

    private final TreeifyConfigService configService;

    public BiomePatchService(TreeifyConfigService configService) {
        this.configService = configService;
    }

    /**
     * Resolves whether a biome feature should be kept, removed, or replaced.
     */
    public PatchDecision planPatch(Identifier biomeId, Identifier featureId, Holder<PlacedFeature> original) {
        if (!configService.isFeatureEnabled(featureId.toString(), biomeId.toString())) {
            return PatchDecision.remove();
        }

        PlacedFeature prunedFeature = tryPrunePlacedFeature(original.value());
        if (prunedFeature == null) {
            return PatchDecision.remove();
        }

        Holder<PlacedFeature> replacement = tryCreateOverride(biomeId, featureId, original);
        if (replacement != null) {
            return PatchDecision.replace(replacement);
        }

        return PatchDecision.keep();
    }

    /**
     * Creates a patched version of a feature if it needs selector pruning or other overrides.
     * Returns null if no override is needed.
     */
    public Holder<PlacedFeature> tryCreateOverride(Identifier biomeId, Identifier featureId, Holder<PlacedFeature> original) {
        float densityMultiplier = configService.getDensityMultiplier(featureId.toString(), biomeId.toString());
        int heightDelta = configService.getHeightDelta(featureId.toString(), biomeId.toString());

        PlacedFeature prunedFeature = tryPrunePlacedFeature(original.value());
        if (prunedFeature != original.value()) {
            return Holder.direct(prunedFeature);
        }

        if (densityMultiplier == 1.0f && heightDelta == 0) {
            return null;
        }

        // Logic for creating clones using factories would go here.
        // For now, this service provides the rule-resolution boundary.
        return null;
    }

    private PlacedFeature tryPrunePlacedFeature(PlacedFeature original) {
        ConfiguredFeature<?, ?> configuredFeature = original.feature().value();
        ConfiguredFeature<?, ?> prunedConfiguredFeature = tryPruneConfiguredFeature(configuredFeature);
        if (prunedConfiguredFeature == null) {
            return null;
        }

        if (prunedConfiguredFeature == configuredFeature) {
            return original;
        }

        return new PlacedFeature(Holder.direct(prunedConfiguredFeature), List.copyOf(original.placement()));
    }

    @SuppressWarnings("unchecked")
    private ConfiguredFeature<?, ?> tryPruneConfiguredFeature(ConfiguredFeature<?, ?> configuredFeature) {
        Feature<?> feature = configuredFeature.feature();

        if (shouldDropLeafFeature(feature, configuredFeature)) {
            return null;
        }

        if (feature == Feature.RANDOM_SELECTOR) {
            RandomFeatureConfiguration originalConfig = (RandomFeatureConfiguration) configuredFeature.config();
            List<WeightedPlacedFeature> prunedEntries = new ArrayList<>();
            boolean changed = false;

            for (WeightedPlacedFeature entry : originalConfig.features) {
                PlacedFeature prunedChild = tryPrunePlacedFeature(entry.feature.value());
                if (prunedChild == null) {
                    changed = true;
                    continue;
                }

                if (prunedChild != entry.feature.value()) {
                    changed = true;
                    prunedEntries.add(new WeightedPlacedFeature(Holder.direct(prunedChild), entry.chance));
                } else {
                    prunedEntries.add(entry);
                }
            }

            PlacedFeature prunedDefault = tryPrunePlacedFeature(originalConfig.defaultFeature.value());
            if (prunedDefault == null && prunedEntries.isEmpty()) {
                return null;
            }

            if (prunedDefault == null) {
                changed = true;
                WeightedPlacedFeature fallbackEntry = prunedEntries.remove(prunedEntries.size() - 1);
                prunedDefault = fallbackEntry.feature.value();
            } else if (prunedDefault != originalConfig.defaultFeature.value()) {
                changed = true;
            }

            if (!changed) {
                return configuredFeature;
            }

            return new ConfiguredFeature<>(
                    (Feature<RandomFeatureConfiguration>) feature,
                    new RandomFeatureConfiguration(prunedEntries, Holder.direct(prunedDefault))
            );
        }

        if (feature == Feature.RANDOM_BOOLEAN_SELECTOR) {
            RandomBooleanFeatureConfiguration originalConfig = (RandomBooleanFeatureConfiguration) configuredFeature.config();
            PlacedFeature prunedTrue = tryPrunePlacedFeature(originalConfig.featureTrue.value());
            PlacedFeature prunedFalse = tryPrunePlacedFeature(originalConfig.featureFalse.value());

            if (prunedTrue == null && prunedFalse == null) {
                return null;
            }

            if (prunedTrue == null) {
                prunedTrue = prunedFalse;
            }

            if (prunedFalse == null) {
                prunedFalse = prunedTrue;
            }

            if (prunedTrue == originalConfig.featureTrue.value() && prunedFalse == originalConfig.featureFalse.value()) {
                return configuredFeature;
            }

            return new ConfiguredFeature<>(
                    (Feature<RandomBooleanFeatureConfiguration>) feature,
                    new RandomBooleanFeatureConfiguration(Holder.direct(prunedTrue), Holder.direct(prunedFalse))
            );
        }

        if (feature == Feature.SIMPLE_RANDOM_SELECTOR) {
            SimpleRandomFeatureConfiguration originalConfig = (SimpleRandomFeatureConfiguration) configuredFeature.config();
            List<Holder<PlacedFeature>> prunedEntries = new ArrayList<>();
            boolean changed = false;

            for (Holder<PlacedFeature> entry : originalConfig.features) {
                PlacedFeature prunedChild = tryPrunePlacedFeature(entry.value());
                if (prunedChild == null) {
                    changed = true;
                    continue;
                }

                if (prunedChild != entry.value()) {
                    changed = true;
                    prunedEntries.add(Holder.direct(prunedChild));
                } else {
                    prunedEntries.add(entry);
                }
            }

            if (prunedEntries.isEmpty()) {
                return null;
            }

            if (!changed) {
                return configuredFeature;
            }

            return new ConfiguredFeature<>(
                    (Feature<SimpleRandomFeatureConfiguration>) feature,
                    new SimpleRandomFeatureConfiguration(HolderSet.direct(prunedEntries))
            );
        }

        return configuredFeature;
    }

    private boolean shouldDropLeafFeature(Feature<?> feature, ConfiguredFeature<?, ?> configuredFeature) {
        if (!configService.getConfig().disableAllTrees && !configService.getConfig().disableAllMushrooms) {
            return false;
        }

        if (feature == Feature.RANDOM_SELECTOR || feature == Feature.RANDOM_BOOLEAN_SELECTOR) {
            return false;
        }

        VegetationCategory category = VegetationFeatureClassifier.classify(new PlacedFeature(Holder.direct(configuredFeature), List.of())).category();

        if (configService.getConfig().disableAllTrees
                && VegetationCategoryResolver.isTreeCategory(category, feature.toString())) {
            return true;
        }

        return configService.getConfig().disableAllMushrooms
                && VegetationCategoryResolver.isMushroomCategory(category, feature.toString());
    }

    public record PatchDecision(boolean removeOriginal, Holder<PlacedFeature> replacement) {
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
