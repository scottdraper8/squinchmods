package org.squinchmods.investigate.rtf.enclosure.mixin;

import net.minecraft.core.BlockPos;
import org.squinchmods.investigate.rtf.enclosure.UndergroundFeatureEnclosureTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(targets = "raccoonman.reterraforged.world.worldgen.feature.placement.UndergroundFeatureEnclosure$Guard")
abstract class MixinUndergroundFeatureEnclosureGuard {
    @Inject(method = "isProtected", at = @At("RETURN"))
    private void squinch$recordEnclosureDecision(
        BlockPos placement,
        CallbackInfoReturnable<Boolean> callback
    ) {
        UndergroundFeatureEnclosureTelemetry.record(placement, callback.getReturnValue());
    }
}
