package org.squinchmods.investigate.ftf.placement.mixin;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.chunk.BulkSectionAccess;
import org.squinchmods.investigate.ftf.placement.PlacementTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(BulkSectionAccess.class)
abstract class MixinBulkSectionAccess {
    @Inject(method = "getSection", at = @At("HEAD"))
    private void squinch$sectionPosition(BlockPos position, CallbackInfoReturnable<?> callback) {
        PlacementTelemetry.sectionPosition(position);
    }
}
