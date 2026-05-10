package com.squinchmods.vegetate.common.vegetate.worldgen.discovery;

import com.squinchmods.vegetate.common.registry.VegetateRegistryManagerProvider;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.GenerationStep;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;

import java.util.*;

public final class VegetationWorldgenDataProvider
{
	public static BiomeVegetationIndex discover()
	{
		BiomeVegetationIndex index = new BiomeVegetationIndex();
		var registryManager = VegetateRegistryManagerProvider.getOrLoadCatalogRegistryManager();

		if (registryManager == null) {
			return index;
		}

		var biomeRegistry = registryManager.lookupOrThrow(Registries.BIOME);
		var decorationStep = GenerationStep.Decoration.VEGETAL_DECORATION;

		Map<ResourceLocation, Set<ResourceKey<Biome>>> featureToBiomes = new HashMap<>();

		biomeRegistry.listElements().forEach(biomeHolder -> {
			ResourceKey<Biome> biomeKey = biomeHolder.key();
			Biome biome = biomeHolder.value();

			var featureSteps = biome.getGenerationSettings().features();
			int stepOrdinal = decorationStep.ordinal();

			if (stepOrdinal < featureSteps.size()) {
				for (Holder<PlacedFeature> placedFeatureHolder : featureSteps.get(stepOrdinal)) {
					placedFeatureHolder.unwrapKey().ifPresent(placedFeatureKey -> {
						ResourceLocation featureId = placedFeatureKey.location();
						featureToBiomes.computeIfAbsent(featureId, k -> new HashSet<>()).add(biomeKey);
					});
				}
			}
		});

		var placedFeatureRegistry = registryManager.lookupOrThrow(Registries.PLACED_FEATURE);

		featureToBiomes.forEach((featureId, biomes) -> {
			placedFeatureRegistry.get(ResourceKey.create(Registries.PLACED_FEATURE, featureId)).ifPresent(placedFeatureHolder -> {
				PlacedFeature placedFeature = placedFeatureHolder.value();
				var classification = VegetationFeatureClassifier.classify(placedFeature);
				VegetationCategory category = VegetationCategoryResolver.resolve(
					featureId.toString(), null, classification.category()
				);

				if (VegetationCategoryResolver.isMushroomCategory(category, featureId.toString())) {
					index.addEntry(new DiscoveredVegetationEntry(
						featureId,
						category,
						biomes,
						decorationStep
					));
				}
			});
		});

		return index;
	}
}
