package org.squinchmods.investigate.rtf.insquare.mixin;

import org.squinchmods.investigate.rtf.insquare.CaveInteractionTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(targets = "raccoonman.reterraforged.world.worldgen.feature.placement.SurfaceFeatureRescue$BandBudget")
abstract class MixinSurfaceFeatureRescueBandBudget {
    @Inject(method = "shouldSearch", at = @At("RETURN"), remap = false)
    private void squinch$recordBudgetDecision(CallbackInfoReturnable<Boolean> callback) {
        CaveInteractionTelemetry.budgetDecision(callback.getReturnValue());
    }
}
