package org.squinchmods.investigate.rtf.c2me.mixin;

import java.util.List;
import java.util.Map;

import net.minecraft.world.level.levelgen.Aquifer;
import net.minecraft.world.level.levelgen.DensityFunction;
import net.minecraft.world.level.levelgen.DensityFunctions;
import net.minecraft.world.level.levelgen.NoiseChunk;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.NoiseSettings;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.blending.Blender;
import org.squinchmods.investigate.rtf.c2me.NoiseChunkLifecycleTelemetry;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(NoiseChunk.class)
abstract class MixinNoiseChunk {
    private static final String ROUTER_MAP_TARGET = "Lnet/minecraft/world/level/levelgen/NoiseRouter;mapAll(Lnet/minecraft/world/level/levelgen/DensityFunction$Visitor;)Lnet/minecraft/world/level/levelgen/NoiseRouter;";

    @Shadow @Final private List<?> interpolators;
    @Shadow @Final private List<?> cellCaches;
    @Shadow @Final private Map<DensityFunction, DensityFunction> wrapped;
    @Shadow @Final private DensityFunction initialDensityNoJaggedness;
    @Unique private int squinch$routerMapBefore;
    @Unique private int squinch$routerMapAfter;

    @Inject(method = "<init>", at = @At(value = "INVOKE", target = ROUTER_MAP_TARGET, shift = At.Shift.BEFORE))
    private void squinch$beforeRouterMap(
        int cellCountXZ,
        RandomState randomState,
        int minBlockX,
        int minBlockZ,
        NoiseSettings noiseSettings,
        DensityFunctions.BeardifierOrMarker beardifierOrMarker,
        NoiseGeneratorSettings generatorSettings,
        Aquifer.FluidPicker fluidPicker,
        Blender blender,
        CallbackInfo callback
    ) {
        this.squinch$routerMapBefore++;
    }

    @Inject(method = "<init>", at = @At(value = "INVOKE", target = ROUTER_MAP_TARGET, shift = At.Shift.AFTER))
    private void squinch$afterRouterMap(
        int cellCountXZ,
        RandomState randomState,
        int minBlockX,
        int minBlockZ,
        NoiseSettings noiseSettings,
        DensityFunctions.BeardifierOrMarker beardifierOrMarker,
        NoiseGeneratorSettings generatorSettings,
        Aquifer.FluidPicker fluidPicker,
        Blender blender,
        CallbackInfo callback
    ) {
        this.squinch$routerMapAfter++;
    }

    @Inject(method = "<init>", at = @At("RETURN"))
    private void squinch$observeLifecycle(
        int cellCountXZ,
        RandomState randomState,
        int minBlockX,
        int minBlockZ,
        NoiseSettings noiseSettings,
        DensityFunctions.BeardifierOrMarker beardifierOrMarker,
        NoiseGeneratorSettings generatorSettings,
        Aquifer.FluidPicker fluidPicker,
        Blender blender,
        CallbackInfo callback
    ) {
        NoiseChunkLifecycleTelemetry.observe(
            this.interpolators,
            this.cellCaches,
            this.wrapped,
            this.initialDensityNoJaggedness,
            this.squinch$routerMapBefore,
            this.squinch$routerMapAfter
        );
    }
}
