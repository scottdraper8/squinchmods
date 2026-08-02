package org.squinchmods.investigate.rtf.cave.mixin;

import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.placement.CountPlacement;
import org.squinchmods.investigate.rtf.cave.CavePlacementTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(CountPlacement.class)
abstract class MixinCountPlacement {
    @Inject(method = "count", at = @At("RETURN"))
    private void squinch$count(
        RandomSource random, BlockPos origin, CallbackInfoReturnable<Integer> callback
    ) {
        CavePlacementTelemetry.countCandidate(callback.getReturnValue());
    }
}
