package org.squinchmods.investigate.ftf.placement.mixin;

import java.util.stream.Stream;

import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.placement.HeightRangePlacement;
import net.minecraft.world.level.levelgen.placement.PlacementContext;
import org.squinchmods.investigate.ftf.placement.PlacementTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(HeightRangePlacement.class)
abstract class MixinHeightRangePlacement {
    @Inject(method = "getPositions", at = @At("RETURN"), cancellable = true)
    private void squinch$heightCandidates(
        PlacementContext context, RandomSource random, BlockPos origin,
        CallbackInfoReturnable<Stream<BlockPos>> callback
    ) {
        callback.setReturnValue(
            callback.getReturnValue().peek(position -> PlacementTelemetry.heightCandidate(context, position))
        );
    }
}
