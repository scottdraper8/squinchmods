package org.squinchmods.investigate.rtf.insquare.mixin;

import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.placement.BiomeFilter;
import net.minecraft.world.level.levelgen.placement.PlacementContext;
import org.squinchmods.investigate.rtf.insquare.CaveInteractionTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(BiomeFilter.class)
abstract class MixinBiomeFilter {
    @Inject(method = "shouldPlace", at = @At("RETURN"))
    private void squinch$recordRescuedBiomeResult(
        PlacementContext context,
        RandomSource random,
        BlockPos position,
        CallbackInfoReturnable<Boolean> callback
    ) {
        CaveInteractionTelemetry.rescuedBiomeResult(position, callback.getReturnValue());
    }
}
