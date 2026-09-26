package org.squinchmods.investigate.ftf.insquare.mixin;

import java.util.Optional;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.placement.PlacementContext;
import org.squinchmods.investigate.ftf.insquare.CaveInteractionTelemetry;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(targets = "etcodehome.freeterraforged.world.worldgen.feature.placement.SurfaceFeatureRescue$Run")
abstract class MixinSurfaceFeatureRescueRun {
    @Shadow @Final private PlacedFeature feature;
    @Shadow @Final private PlacementContext context;

    @Inject(method = "rescue", at = @At("HEAD"))
    private void squinch$recordRescueEntry(
        BlockPos originalOrigin,
        CallbackInfoReturnable<Optional<BlockPos>> callback
    ) {
        CaveInteractionTelemetry.rescueEntry(this.feature, this.context, originalOrigin);
    }

    @Inject(method = "rescue", at = @At("RETURN"))
    private void squinch$recordRescueResult(
        BlockPos originalOrigin,
        CallbackInfoReturnable<Optional<BlockPos>> callback
    ) {
        CaveInteractionTelemetry.rescueResult(callback.getReturnValue());
    }

    @Inject(method = "scan", at = @At("HEAD"), remap = false)
    private void squinch$recordPhysicalScanStart(CallbackInfoReturnable<long[]> callback) {
        CaveInteractionTelemetry.scanStart();
    }

    @Inject(method = "scan", at = @At("RETURN"), remap = false)
    private void squinch$recordPhysicalScanEnd(CallbackInfoReturnable<long[]> callback) {
        CaveInteractionTelemetry.scanEnd(callback.getReturnValue());
    }

    @Inject(method = "isStillEligible", at = @At("HEAD"))
    private void squinch$recordEligibilityCheck(
        BlockPos target,
        BlockPos placement,
        CallbackInfoReturnable<Boolean> callback
    ) {
        CaveInteractionTelemetry.eligibilityCheck();
    }
}
