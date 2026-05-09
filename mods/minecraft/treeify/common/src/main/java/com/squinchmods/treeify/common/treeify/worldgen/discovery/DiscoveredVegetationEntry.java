package com.squinchmods.treeify.common.treeify.worldgen.discovery;

import com.squinchmods.treeify.common.treeify.ui.model.ConfigUiEntrySupport;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.GenerationStep;

import java.util.Set;

public record DiscoveredVegetationEntry(
	Identifier featureId,
	VegetationCategory category,
	Set<ResourceKey<Biome>> sourceBiomes,
	GenerationStep.Decoration generationStep,
	ConfigUiEntrySupport support
)
{
}
