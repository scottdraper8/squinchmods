package com.squinchmods.treeify.forge.treeify.worldgen;

import com.mojang.serialization.Codec;
import com.squinchmods.treeify.common.Treeify;
import net.minecraft.core.Holder;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.GenerationStep;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraftforge.common.world.BiomeModifier;
import net.minecraftforge.common.world.ModifiableBiomeInfo;

import java.util.ListIterator;

/**
 * Forge Biome Modifier for Treeify.
 * Handles removal of disabled features and injection of patched features.
 */
public final class TreeifyBiomeModifier implements BiomeModifier {

    @Override
    public void modify(Holder<Biome> biome, Phase phase, ModifiableBiomeInfo.BiomeInfo.Builder builder) {
        if (phase == Phase.REMOVE) {
            this.handleVegetationPatches(biome, builder);
        }
    }

    private void handleVegetationPatches(Holder<Biome> biome, ModifiableBiomeInfo.BiomeInfo.Builder builder) {
        biome.unwrapKey().ifPresent(biomeKey -> {
            Identifier biomeId = biomeKey.location();
            var patchService = new BiomePatchService(Treeify.getConfigService());
            var features = builder.getGenerationSettings().getFeatures(GenerationStep.Decoration.VEGETAL_DECORATION);
            ListIterator<Holder<PlacedFeature>> iterator = features.listIterator();

            while (iterator.hasNext()) {
                Holder<PlacedFeature> featureHolder = iterator.next();
                BiomePatchService.PatchDecision decision = featureHolder.unwrapKey()
                        .map(featureKey -> patchService.planPatch(biomeId, featureKey.location(), featureHolder))
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
        return TreeifyForgeWorldgen.TREEIFY_BIOME_MODIFIER.get();
    }
}
