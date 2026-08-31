package org.squinchmods.investigate.rtf.insquare.mixin;

import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import org.squinchmods.investigate.rtf.insquare.CaveInteractionTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(ConfiguredFeature.class)
abstract class MixinConfiguredFeature {
    @Inject(method = "place", at = @At("HEAD"))
    private void squinch$recordRescuedPlacementStart(
        WorldGenLevel level,
        ChunkGenerator generator,
        RandomSource random,
        BlockPos position,
        CallbackInfoReturnable<Boolean> callback
    ) {
        CaveInteractionTelemetry.rescuedConfiguredFeatureStart(position);
    }

    @Inject(method = "place", at = @At("RETURN"))
    private void squinch$recordRescuedPlacementEnd(
        WorldGenLevel level,
        ChunkGenerator generator,
        RandomSource random,
        BlockPos position,
        CallbackInfoReturnable<Boolean> callback
    ) {
        CaveInteractionTelemetry.rescuedConfiguredFeatureEnd(callback.getReturnValue());
    }
}
