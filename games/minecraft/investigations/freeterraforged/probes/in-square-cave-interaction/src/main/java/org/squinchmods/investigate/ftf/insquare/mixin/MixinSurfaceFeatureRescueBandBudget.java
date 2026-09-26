package org.squinchmods.investigate.ftf.insquare.mixin;

import org.squinchmods.investigate.ftf.insquare.CaveInteractionTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(targets = "etcodehome.freeterraforged.world.worldgen.feature.placement.SurfaceFeatureRescue$BandBudget")
abstract class MixinSurfaceFeatureRescueBandBudget {
    @Inject(method = "shouldSearch", at = @At("RETURN"), remap = false)
    private void squinch$recordBudgetDecision(CallbackInfoReturnable<Boolean> callback) {
        CaveInteractionTelemetry.budgetDecision(callback.getReturnValue());
    }
}
