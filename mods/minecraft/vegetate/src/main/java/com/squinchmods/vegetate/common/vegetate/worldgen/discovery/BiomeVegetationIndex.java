package com.squinchmods.vegetate.common.vegetate.worldgen.discovery;

import java.util.*;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.biome.Biome;

public final class BiomeVegetationIndex {
  private final Map<ResourceLocation, DiscoveredVegetationEntry> entries = new TreeMap<>();
  private final Map<ResourceKey<Biome>, List<ResourceLocation>> biomeToFeatures = new HashMap<>();

  public void addEntry(DiscoveredVegetationEntry entry) {
    entries.put(entry.featureId(), entry);

    for (ResourceKey<Biome> biomeKey : entry.sourceBiomes()) {
      biomeToFeatures.computeIfAbsent(biomeKey, k -> new ArrayList<>()).add(entry.featureId());
    }
  }

  public Collection<DiscoveredVegetationEntry> getAllEntries() {
    return Collections.unmodifiableCollection(entries.values());
  }

  public Optional<DiscoveredVegetationEntry> getEntry(ResourceLocation id) {
    return Optional.ofNullable(entries.get(id));
  }

  public List<ResourceLocation> getFeaturesForBiome(ResourceKey<Biome> biomeKey) {
    return Collections.unmodifiableList(
        biomeToFeatures.getOrDefault(biomeKey, Collections.emptyList()));
  }

  public boolean containsFeature(ResourceLocation id) {
    return entries.containsKey(id);
  }
}
