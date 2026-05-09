package com.squinchmods.treeify.common.treeify.worldgen.clone;

import net.minecraft.core.Holder;
import net.minecraft.resources.Identifier;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.placement.PlacementModifier;

import java.util.List;

/**
 * Factory for cloning {@link PlacedFeature} instances with modified placement.
 */
public final class PlacedFeatureCloneFactory {

    /**
     * Clones a {@link PlacedFeature} and replaces its placement modifiers.
     *
     * @param originalId   The ID of the original feature.
     * @param original     The original {@link PlacedFeature}.
     * @param newModifiers The new list of {@link PlacementModifier}s.
     * @return A new {@link PlacedFeature} instance.
     */
    public static PlacedFeature clone(
            Identifier originalId,
            PlacedFeature original,
            List<PlacementModifier> newModifiers
    ) {
        Holder<ConfiguredFeature<?, ?>> feature = original.feature();
        PlacedFeature clone = new PlacedFeature(feature, List.copyOf(newModifiers));
        ProvenanceTracker.record(clone, originalId);
        return clone;
    }

    private PlacedFeatureCloneFactory() {
    }
}
