package org.squinchmods.investigate.rtf.insquare.mixin;

import java.util.stream.Stream;

import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.placement.InSquarePlacement;
import net.minecraft.world.level.levelgen.placement.PlacementContext;
import org.squinchmods.investigate.rtf.insquare.CaveInteractionTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(value = InSquarePlacement.class, priority = 2000)
abstract class MixinInSquarePlacement {
    @Inject(method = "getPositions", at = @At("HEAD"))
    private void squinch$recordInSquareCall(
        PlacementContext context,
        RandomSource random,
        BlockPos origin,
        CallbackInfoReturnable<Stream<BlockPos>> callback
    ) {
        CaveInteractionTelemetry.inSquareCall(context, origin);
    }

    @Inject(method = "getPositions", at = @At("RETURN"), cancellable = true)
    private void squinch$recordInSquareOutput(
        PlacementContext context,
        RandomSource random,
        BlockPos origin,
        CallbackInfoReturnable<Stream<BlockPos>> callback
    ) {
        callback.setReturnValue(
            callback.getReturnValue().peek(
                output -> CaveInteractionTelemetry.inSquareOutput(context, origin, output)
            )
        );
    }
}
