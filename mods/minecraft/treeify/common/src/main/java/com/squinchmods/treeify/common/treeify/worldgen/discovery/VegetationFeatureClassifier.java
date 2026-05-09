package com.squinchmods.treeify.common.treeify.worldgen.discovery;

import com.squinchmods.treeify.common.treeify.ui.model.ConfigUiEntrySupport;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;

public final class VegetationFeatureClassifier
{
	public static ClassificationResult classify(PlacedFeature placedFeature)
	{
		ConfiguredFeature<?, ?> configuredFeature = placedFeature.feature().value();
		Feature<?> feature = configuredFeature.feature();

		if (feature == Feature.TREE) {
			return new ClassificationResult(VegetationCategory.DIRECT_TREE, ConfigUiEntrySupport.FULL);
		}

		if (feature == Feature.RANDOM_SELECTOR) {
			return new ClassificationResult(VegetationCategory.TREE_SELECTOR, ConfigUiEntrySupport.PARTIAL);
		}

		if (feature == Feature.HUGE_RED_MUSHROOM || feature == Feature.HUGE_BROWN_MUSHROOM) {
			return new ClassificationResult(VegetationCategory.DIRECT_HUGE_MUSHROOM, ConfigUiEntrySupport.FULL);
		}


		if (feature == Feature.VEGETATION_PATCH || feature == Feature.WATERLOGGED_VEGETATION_PATCH) {
			return new ClassificationResult(VegetationCategory.MIXED_VEGETATION, ConfigUiEntrySupport.PARTIAL);
		}

		return new ClassificationResult(VegetationCategory.OPAQUE, ConfigUiEntrySupport.UNSUPPORTED);
	}

	public record ClassificationResult(VegetationCategory category, ConfigUiEntrySupport support)
	{
	}
}
