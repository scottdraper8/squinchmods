package org.squinchmods.investigate.ftf.monument.mixin;

import java.util.concurrent.atomic.AtomicInteger;

import com.google.gson.JsonObject;

import net.minecraft.core.BlockPos;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.StructureManager;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.structure.BoundingBox;
import net.minecraft.world.level.levelgen.structure.StructurePiece;
import net.minecraft.world.level.levelgen.structure.structures.OceanMonumentPieces;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import etcodehome.freeterraforged.data.worldgen.preset.settings.Preset;
import etcodehome.freeterraforged.world.worldgen.FTFRandomState;
import org.squinchmods.investigate.ftf.monument.OceanMonumentDiagnosticsProbePack;

@Mixin(OceanMonumentPieces.MonumentBuilding.class)
public class MixinOceanMonumentBuildingDiagnostics {
    @Unique
    private static final AtomicInteger ftf$observationCount = new AtomicInteger();

    @Inject(method = "postProcess", at = @At("TAIL"))
    private void ftf$recordMonumentState(
        WorldGenLevel level,
        StructureManager structureManager,
        ChunkGenerator chunkGenerator,
        RandomSource randomSource,
        BoundingBox chunkBox,
        ChunkPos chunkPos,
        BlockPos blockPos,
        CallbackInfo callback
    ) {
        if (ftf$observationCount.getAndIncrement() >= 128) {
            return;
        }

        RandomState randomState = level.getLevel().getChunkSource().randomState();
        int presetSeaLevel = Integer.MIN_VALUE;
        if ((Object) randomState instanceof FTFRandomState ftfRandomState) {
            Preset preset = ftfRandomState.preset();
            if (preset != null) {
                presetSeaLevel = preset.world().properties.seaLevel;
            }
        }

        BoundingBox pieceBox = ((StructurePiece) (Object) this).getBoundingBox();
        JsonObject observation = new JsonObject();
        observation.addProperty("level_sea_level", level.getSeaLevel());
        observation.addProperty("preset_sea_level", presetSeaLevel);
        observation.addProperty("chunk_x", chunkPos.x);
        observation.addProperty("chunk_z", chunkPos.z);
        observation.addProperty("piece_min_y", pieceBox.minY());
        observation.addProperty("piece_max_y", pieceBox.maxY());
        observation.addProperty("piece_min_x", pieceBox.minX());
        observation.addProperty("piece_max_x", pieceBox.maxX());
        observation.addProperty("piece_min_z", pieceBox.minZ());
        observation.addProperty("piece_max_z", pieceBox.maxZ());
        OceanMonumentDiagnosticsProbePack.OBSERVATIONS.add(observation);
    }
}
