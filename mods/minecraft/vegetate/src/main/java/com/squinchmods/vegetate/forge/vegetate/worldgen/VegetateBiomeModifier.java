package com.squinchmods.vegetate.forge.vegetate.worldgen;

import com.mojang.serialization.Codec;
import com.squinchmods.vegetate.common.Vegetate;
import java.util.ListIterator;
import net.minecraft.core.Holder;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.GenerationStep;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraftforge.common.world.BiomeModifier;
import net.minecraftforge.common.world.ModifiableBiomeInfo;

public final class VegetateBiomeModifier implements BiomeModifier {

  @Override
  public void modify(
      Holder<Biome> biome, Phase phase, ModifiableBiomeInfo.BiomeInfo.Builder builder) {
    if (phase == Phase.REMOVE) {
      this.handleVegetationPatches(biome, builder);
    }
  }

  private void handleVegetationPatches(
      Holder<Biome> biome, ModifiableBiomeInfo.BiomeInfo.Builder builder) {
    biome
        .unwrapKey()
        .ifPresent(
            biomeKey -> {
              ResourceLocation biomeId = biomeKey.location();
              var patchService = new BiomePatchService(Vegetate.getConfigService());
              var features =
                  builder
                      .getGenerationSettings()
                      .getFeatures(GenerationStep.Decoration.VEGETAL_DECORATION);
              ListIterator<Holder<PlacedFeature>> iterator = features.listIterator();

              while (iterator.hasNext()) {
                Holder<PlacedFeature> featureHolder = iterator.next();
                BiomePatchService.PatchDecision decision =
                    featureHolder
                        .unwrapKey()
                        .map(
                            featureKey ->
                                patchService.planPatch(
                                    biomeId, featureKey.location(), featureHolder))
                        .orElse(BiomePatchService.PatchDecision.keep());

                if (!decision.removeOriginal()) {
                  continue;
                }

                if (decision.replacement() != null) {
                  iterator.set(decision.replacement());
                } else {
                  iterator.remove();
                }
              }
            });
  }

  @Override
  public Codec<? extends BiomeModifier> codec() {
    return VegetateForgeWorldgen.VEGETATE_BIOME_MODIFIER.get();
  }
}
