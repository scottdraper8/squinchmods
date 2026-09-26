package org.squinchmods.investigate.ftf.placement.mixin;

import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunkSection;
import org.squinchmods.investigate.ftf.placement.PlacementTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Captures direct chunk-section writes during an active feature placement. */
@Mixin(LevelChunkSection.class)
abstract class MixinLevelChunkSection {
    @Inject(
        method = "setBlockState(IIILnet/minecraft/world/level/block/state/BlockState;Z)Lnet/minecraft/world/level/block/state/BlockState;",
        at = @At("RETURN")
    )
    private void squinch$sectionWrite(
        int x, int y, int z, BlockState state, boolean lock, CallbackInfoReturnable<BlockState> callback
    ) {
        PlacementTelemetry.blockWrite(state);
    }
}
