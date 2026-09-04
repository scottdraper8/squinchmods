package org.squinchmods.investigate.rtf.placement.mixin;

import java.util.stream.Stream;

import com.llamalad7.mixinextras.injector.ModifyReturnValue;
import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.levelgen.placement.PlacementContext;
import net.minecraft.world.level.levelgen.placement.RandomOffsetPlacement;
import org.squinchmods.investigate.rtf.placement.PlacementTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

@Mixin(RandomOffsetPlacement.class)
abstract class MixinRandomOffsetPlacement {
    @ModifyReturnValue(method = "getPositions", at = @At("RETURN"))
    private Stream<BlockPos> squinch$offset(
        Stream<BlockPos> original,
        PlacementContext context, RandomSource random, BlockPos origin
    ) {
        return original.peek(output -> PlacementTelemetry.randomOffset(origin, output));
    }
}
