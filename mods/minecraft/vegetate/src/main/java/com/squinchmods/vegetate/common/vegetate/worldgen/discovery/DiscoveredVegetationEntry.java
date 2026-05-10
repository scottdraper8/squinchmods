package com.squinchmods.vegetate.common.vegetate.worldgen.discovery;

import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.GenerationStep;

import java.util.Set;

public record DiscoveredVegetationEntry(
	ResourceLocation featureId,
	VegetationCategory category,
	Set<ResourceKey<Biome>> sourceBiomes,
	GenerationStep.Decoration generationStep
)
{
}
