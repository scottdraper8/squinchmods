package com.squinchmods.treeify.common.treeify.worldgen.discovery;

import com.squinchmods.treeify.common.registry.TreeifyRegistryManagerProvider;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.GenerationStep;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;

import java.util.*;

public final class VegetationWorldgenDataProvider
{
	public static BiomeVegetationIndex discover()
	{
		BiomeVegetationIndex index = new BiomeVegetationIndex();
		var registryManager = TreeifyRegistryManagerProvider.getOrLoadCatalogRegistryManager();

		if (registryManager == null) {
			return index;
		}

		var biomeRegistry = registryManager.lookupOrThrow(Registries.BIOME);
		var decorationStep = GenerationStep.Decoration.VEGETAL_DECORATION;

		Map<Identifier, Set<ResourceKey<Biome>>> featureToBiomes = new HashMap<>();

		biomeRegistry.listElements().forEach(biomeHolder -> {
			ResourceKey<Biome> biomeKey = biomeHolder.key();
			Biome biome = biomeHolder.value();

			var featureSteps = biome.getGenerationSettings().features();
			int stepOrdinal = decorationStep.ordinal();

			if (stepOrdinal < featureSteps.size()) {
				for (Holder<PlacedFeature> placedFeatureHolder : featureSteps.get(stepOrdinal)) {
					placedFeatureHolder.unwrapKey().ifPresent(placedFeatureKey -> {
						Identifier featureId = placedFeatureKey/*? if >=1.21.11 {*/.identifier()/*?} else {*//*.location()*//*?}*/;
						featureToBiomes.computeIfAbsent(featureId, k -> new HashSet<>()).add(biomeKey);
					});

				}
			}
		});

		var placedFeatureRegistry = registryManager.lookupOrThrow(Registries.PLACED_FEATURE);

		featureToBiomes.forEach((featureId, biomes) -> {
				placedFeatureRegistry.get(ResourceKey.create(Registries.PLACED_FEATURE, featureId)).ifPresent(placedFeatureHolder -> {
					PlacedFeature placedFeature = placedFeatureHolder.value();
					VegetationFeatureClassifier.ClassificationResult rawClassification = VegetationFeatureClassifier.classify(placedFeature);
                    VegetationCategory category = VegetationCategoryResolver.resolve(featureId.toString(), null, rawClassification.category());
                    var classification = new VegetationFeatureClassifier.ClassificationResult(category, rawClassification.support());

					index.addEntry(new DiscoveredVegetationEntry(
						featureId,
					classification.category(),
					biomes,
					decorationStep,
					classification.support()
				));
			});
		});

		return index;
	}
}
