package org.squinchmods.investigate.rtf;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.BlockPos;
import net.minecraft.core.SectionPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.FullChunkStatus;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkGenerator;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.structure.BoundingBox;
import net.minecraft.world.level.levelgen.structure.PoolElementStructurePiece;
import net.minecraft.world.level.levelgen.structure.Structure;
import net.minecraft.world.level.levelgen.structure.StructurePiece;
import net.minecraft.world.level.levelgen.structure.StructureStart;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import raccoonman.reterraforged.world.worldgen.GeneratorContext;
import raccoonman.reterraforged.world.worldgen.RTFRandomState;
import raccoonman.reterraforged.world.worldgen.cell.Cell;
import raccoonman.reterraforged.world.worldgen.densityfunction.tile.Tile;

/**
 * Compares the finished OCEAN_FLOOR height to the generator's structure-free base-column prediction
 * around every real piece. NoiseBasedChunkGenerator#getBaseHeight constructs its column with a
 * Beardifier marker rather than a StructureManager, so the base side excludes structure terrain
 * adaptation while retaining the active generator, seed, preset, and coordinates.
 */
final class StructureTerrainDeformationProbe implements ProbeExecution {
    private final FinishedChunkSelection selection;
    private final String structureIdRaw;
    private final ResourceLocation structureId;
    private final int halo;
    private final int sampleStep;
    private final int exampleLimit;
    private final long maxColumns;

    StructureTerrainDeformationProbe(ProbeRequest request) {
        JsonObject config = request.config();
        this.selection = new FinishedChunkSelection(config, "structure-terrain-deformation");
        this.structureIdRaw = config.has("structure_id")
            ? config.get("structure_id").getAsString()
            : "minecraft:trail_ruins";
        ResourceLocation parsed = ResourceLocation.tryParse(this.structureIdRaw);
        if (parsed == null) {
            throw new IllegalArgumentException("structure_id is not a valid identifier: " + this.structureIdRaw);
        }
        this.structureId = parsed;
        this.halo = config.has("halo") ? config.get("halo").getAsInt() : 6;
        this.sampleStep = config.has("sample_step") ? config.get("sample_step").getAsInt() : 1;
        this.exampleLimit = config.has("example_limit") ? config.get("example_limit").getAsInt() : 40;
        this.maxColumns = config.has("max_columns") ? config.get("max_columns").getAsLong() : 100_000L;
        if (
            this.halo < 0 || this.halo > 32
            || this.sampleStep < 1 || this.sampleStep > 16
            || this.exampleLimit < 0 || this.exampleLimit > 1024
            || this.maxColumns < 1
        ) {
            throw new IllegalArgumentException(
                "halo must be 0..32, sample_step 1..16, example_limit 0..1024, and max_columns positive"
            );
        }
    }

    @Override
    public ProbeResult tick(MinecraftServer server) {
        ServerLevel level = server.overworld();
        FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
        if (snapshot == null) {
            return null;
        }
        Structure target = level.registryAccess().registryOrThrow(Registries.STRUCTURE).get(this.structureId);
        JsonArray structuresJson = new JsonArray();
        Set<ChunkPos> seenStarts = new HashSet<>();
        if (target != null) {
            for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                StructureStart start = ready.chunk().getAllStarts().get(target);
                if (start == null || !start.isValid() || !seenStarts.add(start.getChunkPos())) {
                    continue;
                }
                structuresJson.add(analyze(level, start));
            }
        }
        JsonObject data = new JsonObject();
        data.addProperty("authority", "finished-chunk-plus-structure-free-base-column");
        data.addProperty("structure_id", this.structureIdRaw);
        data.addProperty("structure_registered", target != null);
        data.addProperty("structure_instance_count", structuresJson.size());
        data.add("structures", structuresJson);
        return this.selection.result(snapshot, data);
    }

    private JsonObject analyze(ServerLevel level, StructureStart start) {
        List<StructurePiece> pieces = start.getPieces();
        Map<Long, ColumnSample> columns = new HashMap<>();
        long skippedBoundary = 0;
        boolean capped = false;

        scan:
        for (StructurePiece piece : pieces) {
            BoundingBox box = piece.getBoundingBox();
            for (int x = box.minX() - this.halo; x <= box.maxX() + this.halo; x += this.sampleStep) {
                for (int z = box.minZ() - this.halo; z <= box.maxZ() + this.halo; z += this.sampleStep) {
                    long key = columnKey(x, z);
                    if (columns.containsKey(key)) {
                        continue;
                    }
                    if (columns.size() >= this.maxColumns) {
                        capped = true;
                        break scan;
                    }
                    ColumnSample sample = sampleColumn(level, x, z);
                    if (sample == null) {
                        skippedBoundary++;
                    } else {
                        columns.put(key, sample);
                    }
                }
            }
        }

        JsonObject result = new JsonObject();
        BoundingBox overall = start.getBoundingBox();
        result.addProperty("start_chunk_x", start.getChunkPos().x);
        result.addProperty("start_chunk_z", start.getChunkPos().z);
        addBox(result, "bounding_box", overall);
        result.addProperty("piece_count", pieces.size());
        result.addProperty("halo", this.halo);
        result.addProperty("sample_step", this.sampleStep);
        result.addProperty("sampled_columns", columns.size());
        result.addProperty("skipped_boundary_columns", skippedBoundary);
        result.addProperty("column_scan_capped", capped);
        result.add("deformation", summarize(columns.values(), true));

        JsonArray piecesJson = new JsonArray();
        for (int index = 0; index < pieces.size(); index++) {
            piecesJson.add(analyzePiece(pieces.get(index), index, columns));
        }
        result.add("pieces", piecesJson);
        return result;
    }

    private JsonObject analyzePiece(StructurePiece piece, int index, Map<Long, ColumnSample> columns) {
        BoundingBox box = piece.getBoundingBox();
        List<ColumnSample> samples = new ArrayList<>();
        List<ColumnSample> burySupportSamples = new ArrayList<>();
        int baseMin = Integer.MAX_VALUE;
        int baseMax = Integer.MIN_VALUE;
        int burySupportBaseMin = Integer.MAX_VALUE;
        int burySupportBaseMax = Integer.MIN_VALUE;
        int burySupportRtfCellMin = Integer.MAX_VALUE;
        int burySupportRtfCellMax = Integer.MIN_VALUE;
        for (int x = box.minX() - this.halo; x <= box.maxX() + this.halo; x += this.sampleStep) {
            for (int z = box.minZ() - this.halo; z <= box.maxZ() + this.halo; z += this.sampleStep) {
                ColumnSample sample = columns.get(columnKey(x, z));
                if (sample != null) {
                    samples.add(sample);
                    baseMin = Math.min(baseMin, sample.baseHeight());
                    baseMax = Math.max(baseMax, sample.baseHeight());
                    if (isInsideBurySupport(box, x, z, this.halo)) {
                        burySupportSamples.add(sample);
                        burySupportBaseMin = Math.min(burySupportBaseMin, sample.baseHeight());
                        burySupportBaseMax = Math.max(burySupportBaseMax, sample.baseHeight());
                        if (sample.rtfCellHeight() != null) {
                            burySupportRtfCellMin = Math.min(burySupportRtfCellMin, sample.rtfCellHeight());
                            burySupportRtfCellMax = Math.max(burySupportRtfCellMax, sample.rtfCellHeight());
                        }
                    }
                }
            }
        }
        int groundDelta = 0;
        String projection = "non_pool_piece";
        if (piece instanceof PoolElementStructurePiece poolPiece) {
            groundDelta = poolPiece.getGroundLevelDelta();
            projection = poolPiece.getElement().getProjection().getName();
        }
        int groundPlane = box.minY() + groundDelta;
        JsonObject result = new JsonObject();
        result.addProperty("index", index);
        result.addProperty("class", piece.getClass().getName());
        result.addProperty("projection", projection);
        addBox(result, "bounding_box", box);
        result.addProperty("ground_level_delta", groundDelta);
        result.addProperty("ground_plane_y", groundPlane);
        if (!samples.isEmpty()) {
            result.addProperty("base_height_min", baseMin);
            result.addProperty("base_height_max", baseMax);
            result.addProperty("base_relief", baseMax - baseMin);
            result.addProperty("ground_plane_minus_base_min", groundPlane - baseMax);
            result.addProperty("ground_plane_minus_base_max", groundPlane - baseMin);
        }
        result.addProperty("bury_support_columns", burySupportSamples.size());
        if (!burySupportSamples.isEmpty()) {
            result.addProperty("bury_support_base_height_min", burySupportBaseMin);
            result.addProperty("bury_support_base_height_max", burySupportBaseMax);
            result.addProperty("bury_support_base_relief", burySupportBaseMax - burySupportBaseMin);
            result.addProperty("ground_plane_minus_bury_support_min", groundPlane - burySupportBaseMax);
            result.addProperty("ground_plane_minus_bury_support_max", groundPlane - burySupportBaseMin);
            if (burySupportRtfCellMin != Integer.MAX_VALUE) {
                result.addProperty("bury_support_rtf_cell_height_min", burySupportRtfCellMin);
                result.addProperty("bury_support_rtf_cell_height_max", burySupportRtfCellMax);
                result.addProperty("ground_plane_minus_bury_support_rtf_cell_min", groundPlane - burySupportRtfCellMax);
                result.addProperty("ground_plane_minus_bury_support_rtf_cell_max", groundPlane - burySupportRtfCellMin);
            }
        }
        result.add("bury_support_height_comparison", summarize(burySupportSamples, false));
        result.add("deformation", summarize(samples, false));
        return result;
    }

    /**
     * BURY passes horizontal distance to the piece box unchanged to a radius-six falloff. Only its
     * vertical distance is divided by two. Samples at exactly the configured radius have zero
     * contribution, so they remain useful context but are not part of the active support.
     */
    private static boolean isInsideBurySupport(BoundingBox box, int x, int z, int radius) {
        int dx = Math.max(0, Math.max(box.minX() - x, x - box.maxX()));
        int dz = Math.max(0, Math.max(box.minZ() - z, z - box.maxZ()));
        if (radius == 0) {
            return dx == 0 && dz == 0;
        }
        return dx * dx + dz * dz < radius * radius;
    }

    private ColumnSample sampleColumn(ServerLevel level, int x, int z) {
        int chunkX = SectionPos.blockToSectionCoord(x);
        int chunkZ = SectionPos.blockToSectionCoord(z);
        LevelChunk chunk = level.getChunkSource().getChunkNow(chunkX, chunkZ);
        if (chunk == null || !chunk.getFullStatus().isOrAfter(FullChunkStatus.FULL)) {
            return null;
        }
        ChunkGenerator generator = level.getChunkSource().getGenerator();
        RandomState randomState = level.getChunkSource().randomState();
        int baseHeight = generator.getBaseHeight(x, z, Heightmap.Types.OCEAN_FLOOR_WG, level, randomState);
        Integer rtfCellHeight = null;
        if ((Object) randomState instanceof RTFRandomState rtfRandomState) {
            GeneratorContext generatorContext = rtfRandomState.generatorContext();
            if (generatorContext != null) {
                int rtfChunkX = SectionPos.blockToSectionCoord(x);
                int rtfChunkZ = SectionPos.blockToSectionCoord(z);
                Tile.Chunk rtfChunk = generatorContext.cache
                    .provideAtChunk(rtfChunkX, rtfChunkZ)
                    .getChunkReader(rtfChunkX, rtfChunkZ);
                Cell cell = rtfChunk.getCell(x, z);
                rtfCellHeight = generatorContext.levels.scale(cell.height);
            }
        }
        int finalHeight = chunk.getHeight(Heightmap.Types.OCEAN_FLOOR, Math.floorMod(x, 16), Math.floorMod(z, 16));
        int solidAboveBase = 0;
        int airAboveBase = 0;
        if (finalHeight > baseHeight) {
            for (int y = baseHeight; y < finalHeight; y++) {
                BlockState state = chunk.getBlockState(new BlockPos(x, y, z));
                if (state.blocksMotion()) {
                    solidAboveBase++;
                } else {
                    airAboveBase++;
                }
            }
        }
        BlockState top = chunk.getBlockState(new BlockPos(x, finalHeight - 1, z));
        String biome = MinecraftProbeHelpers.biomeId(
            chunk.getNoiseBiome(Math.floorDiv(x, 4), Math.floorDiv(finalHeight - 1, 4), Math.floorDiv(z, 4))
        );
        return new ColumnSample(
            x,
            z,
            baseHeight,
            finalHeight,
            finalHeight - baseHeight,
            solidAboveBase,
            airAboveBase,
            MinecraftProbeHelpers.blockId(top),
            biome,
            rtfCellHeight
        );
    }

    private JsonObject summarize(Iterable<ColumnSample> samples, boolean includeDetail) {
        long count = 0;
        long positive = 0;
        long atLeast4 = 0;
        long atLeast8 = 0;
        long atLeast16 = 0;
        long atLeast32 = 0;
        long deltaSum = 0;
        long positiveSolidBlocks = 0;
        long rtfCellComparisons = 0;
        long baseMinusRtfCellSum = 0;
        int baseMinusRtfCellMin = Integer.MAX_VALUE;
        int baseMinusRtfCellMax = Integer.MIN_VALUE;
        int min = Integer.MAX_VALUE;
        int max = Integer.MIN_VALUE;
        Map<Integer, Long> histogram = new TreeMap<>();
        List<ColumnSample> ranked = new ArrayList<>();
        for (ColumnSample sample : samples) {
            int delta = sample.delta();
            count++;
            deltaSum += delta;
            min = Math.min(min, delta);
            max = Math.max(max, delta);
            histogram.merge(delta, 1L, Long::sum);
            if (delta > 0) {
                positive++;
                positiveSolidBlocks += sample.solidAboveBase();
            }
            if (delta >= 4) atLeast4++;
            if (delta >= 8) atLeast8++;
            if (delta >= 16) atLeast16++;
            if (delta >= 32) atLeast32++;
            if (sample.rtfCellHeight() != null) {
                int baseMinusRtfCell = sample.baseHeight() - sample.rtfCellHeight();
                rtfCellComparisons++;
                baseMinusRtfCellSum += baseMinusRtfCell;
                baseMinusRtfCellMin = Math.min(baseMinusRtfCellMin, baseMinusRtfCell);
                baseMinusRtfCellMax = Math.max(baseMinusRtfCellMax, baseMinusRtfCell);
            }
            ranked.add(sample);
        }
        ranked.sort(
            Comparator.comparingInt(ColumnSample::delta)
                .thenComparingInt(ColumnSample::solidAboveBase)
                .reversed()
        );

        JsonObject result = new JsonObject();
        result.addProperty("columns", count);
        result.addProperty("positive_delta_columns", positive);
        result.addProperty("delta_at_least_4", atLeast4);
        result.addProperty("delta_at_least_8", atLeast8);
        result.addProperty("delta_at_least_16", atLeast16);
        result.addProperty("delta_at_least_32", atLeast32);
        result.addProperty("positive_solid_blocks_above_base", positiveSolidBlocks);
        result.addProperty("rtf_cell_height_comparisons", rtfCellComparisons);
        if (rtfCellComparisons > 0) {
            result.addProperty("base_minus_rtf_cell_height_min", baseMinusRtfCellMin);
            result.addProperty("base_minus_rtf_cell_height_max", baseMinusRtfCellMax);
            result.addProperty("base_minus_rtf_cell_height_mean", (double) baseMinusRtfCellSum / rtfCellComparisons);
        }
        if (count > 0) {
            result.addProperty("delta_min", min);
            result.addProperty("delta_max", max);
            result.addProperty("delta_mean", (double) deltaSum / count);
        }
        if (includeDetail) {
            JsonObject histogramJson = new JsonObject();
            histogram.forEach((delta, occurrences) -> histogramJson.addProperty(Integer.toString(delta), occurrences));
            result.add("delta_histogram", histogramJson);
            JsonArray examples = new JsonArray();
            for (int i = 0; i < Math.min(this.exampleLimit, ranked.size()); i++) {
                ColumnSample sample = ranked.get(i);
                JsonObject example = new JsonObject();
                example.addProperty("x", sample.x());
                example.addProperty("z", sample.z());
                example.addProperty("base_height", sample.baseHeight());
                example.addProperty("final_height", sample.finalHeight());
                example.addProperty("delta", sample.delta());
                example.addProperty("solid_above_base", sample.solidAboveBase());
                example.addProperty("air_above_base", sample.airAboveBase());
                example.addProperty("top_block", sample.topBlock());
                example.addProperty("biome", sample.biome());
                if (sample.rtfCellHeight() != null) {
                    example.addProperty("rtf_cell_height", sample.rtfCellHeight());
                    example.addProperty("base_minus_rtf_cell_height", sample.baseHeight() - sample.rtfCellHeight());
                }
                examples.add(example);
            }
            result.add("largest_delta_examples", examples);
        }
        return result;
    }

    private static void addBox(JsonObject object, String prefix, BoundingBox box) {
        object.addProperty(prefix + "_min_x", box.minX());
        object.addProperty(prefix + "_min_y", box.minY());
        object.addProperty(prefix + "_min_z", box.minZ());
        object.addProperty(prefix + "_max_x", box.maxX());
        object.addProperty(prefix + "_max_y", box.maxY());
        object.addProperty(prefix + "_max_z", box.maxZ());
    }

    private static long columnKey(int x, int z) {
        return ((long) x << 32) ^ (z & 0xffffffffL);
    }

    private record ColumnSample(
        int x,
        int z,
        int baseHeight,
        int finalHeight,
        int delta,
        int solidAboveBase,
        int airAboveBase,
        String topBlock,
        String biome,
        Integer rtfCellHeight
    ) {
    }
}
