package org.squinchmods.investigate.rtf.stagewrapper.mixin;

import org.squinchmods.investigate.rtf.stagewrapper.GeneratorStageWrapperTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import net.minecraft.server.level.WorldGenRegion;
import net.minecraft.world.level.StructureManager;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.RandomState;
import raccoonman.reterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;

@Mixin(NoiseBasedChunkGenerator.class)
abstract class MixinNoiseBasedChunkGenerator {
    @Inject(method = "buildSurface", at = @At("HEAD"))
    private void squinch$observeFtfSurfaceWrapper(
        WorldGenRegion region,
        StructureManager structureManager,
        RandomState randomState,
        ChunkAccess chunk,
        CallbackInfo callback
    ) {
        if ((Object) this instanceof TerraForgedChunkGenerator) {
            GeneratorStageWrapperTelemetry.observeFtfSurfaceWrapper();
        }
    }
}
