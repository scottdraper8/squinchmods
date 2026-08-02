package org.squinchmods.investigate.rtf.cave.mixin;

import net.minecraft.core.BlockPos;
import net.minecraft.server.level.WorldGenRegion;
import net.minecraft.world.level.block.state.BlockState;
import org.squinchmods.investigate.rtf.cave.CavePlacementTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(WorldGenRegion.class)
abstract class MixinWorldGenRegion {
    @Inject(method = "setBlock", at = @At("RETURN"))
    private void squinch$write(
        BlockPos position, BlockState state, int flags, int recursionLeft,
        CallbackInfoReturnable<Boolean> callback
    ) {
        if (callback.getReturnValue()) {
            CavePlacementTelemetry.blockWrite(position, state);
        }
    }
}
