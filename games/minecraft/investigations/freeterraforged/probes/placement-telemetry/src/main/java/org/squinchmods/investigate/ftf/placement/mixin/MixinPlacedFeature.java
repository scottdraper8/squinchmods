package org.squinchmods.investigate.ftf.placement.mixin;

import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.placement.PlacementContext;
import org.squinchmods.investigate.ftf.placement.PlacementTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(PlacedFeature.class)
abstract class MixinPlacedFeature {
    @Inject(method = "placeWithContext", at = @At("HEAD"))
    private void squinch$begin(
        PlacementContext context, RandomSource random, BlockPos origin,
        CallbackInfoReturnable<Boolean> callback
    ) {
        PlacementTelemetry.begin((PlacedFeature) (Object) this, context, origin);
    }

    @Inject(method = "placeWithContext", at = @At("RETURN"))
    private void squinch$end(
        PlacementContext context, RandomSource random, BlockPos origin,
        CallbackInfoReturnable<Boolean> callback
    ) {
        PlacementTelemetry.end(callback.getReturnValue());
    }
}
