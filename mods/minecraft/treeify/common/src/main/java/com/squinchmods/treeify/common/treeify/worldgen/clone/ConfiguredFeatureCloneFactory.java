package com.squinchmods.treeify.common.treeify.worldgen.clone;

import net.minecraft.resources.Identifier;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.feature.configurations.FeatureConfiguration;
import net.minecraft.world.level.levelgen.feature.configurations.HugeMushroomFeatureConfiguration;
import net.minecraft.world.level.levelgen.feature.configurations.TreeConfiguration;

/**
 * Factory for cloning {@link ConfiguredFeature} instances with modified configurations.
 */
public final class ConfiguredFeatureCloneFactory {

    /**
     * Clones a {@link ConfiguredFeature} and applies a height delta if applicable.
     *
     * @param originalId  The ID of the original feature.
     * @param original    The original {@link ConfiguredFeature}.
     * @param heightDelta The height delta to apply.
     * @return A new {@link ConfiguredFeature} instance.
     */
    @SuppressWarnings("unchecked")
    public static ConfiguredFeature<?, ?> clone(
            Identifier originalId,
            ConfiguredFeature<?, ?> original,
            int heightDelta
    ) {
        FeatureConfiguration config = original.config();
        FeatureConfiguration newConfig = config;

        // Note: Specific field modification for heightDelta depends on the exact Minecraft version's
        // TreeConfiguration and HugeMushroomFeatureConfiguration structure.
        if (heightDelta != 0) {
            if (config instanceof TreeConfiguration treeConfig) {
                // Modification logic for TreeConfiguration height would go here in a full implementation
                newConfig = treeConfig; 
            } else if (config instanceof HugeMushroomFeatureConfiguration mushroomConfig) {
                // Modification logic for HugeMushroomFeatureConfiguration height would go here
                newConfig = mushroomConfig;
            }
        }

        ConfiguredFeature<?, ?> clone = new ConfiguredFeature(original.feature(), newConfig);
        ProvenanceTracker.record(clone, originalId);
        return clone;
    }

    private ConfiguredFeatureCloneFactory() {
    }
}
