package com.squinchmods.treeify.common.treeify.worldgen.discovery;

import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.biome.Biome;

import java.util.*;

public final class BiomeVegetationIndex
{
	private final Map<Identifier, DiscoveredVegetationEntry> entries = new TreeMap<>();
	private final Map<ResourceKey<Biome>, List<Identifier>> biomeToFeatures = new HashMap<>();

	public void addEntry(DiscoveredVegetationEntry entry)
	{
		entries.put(entry.featureId(), entry);

		for (ResourceKey<Biome> biomeKey : entry.sourceBiomes()) {
			biomeToFeatures.computeIfAbsent(biomeKey, k -> new ArrayList<>()).add(entry.featureId());
		}
	}

	public Collection<DiscoveredVegetationEntry> getAllEntries()
	{
		return Collections.unmodifiableCollection(entries.values());
	}

	public Optional<DiscoveredVegetationEntry> getEntry(Identifier id)
	{
		return Optional.ofNullable(entries.get(id));
	}

	public List<Identifier> getFeaturesForBiome(ResourceKey<Biome> biomeKey)
	{
		return Collections.unmodifiableList(biomeToFeatures.getOrDefault(biomeKey, Collections.emptyList()));
	}

	public boolean containsFeature(Identifier id)
	{
		return entries.containsKey(id);
	}
}
