package org.squinchmods.investigate.rtf;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

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
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.levelgen.structure.BoundingBox;
import net.minecraft.world.level.levelgen.structure.Structure;
import net.minecraft.world.level.levelgen.structure.StructureStart;
import net.minecraft.world.level.levelgen.structure.StructurePiece;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;

/**
 * Reads real StructureStart/StructurePiece bounds from finished chunks (never mid-generation) and
 * scans the one-block shell immediately outside each piece's real bounding box, excluding cells
 * that fall inside another piece of the same structure. A shell cell that is air or fluid is not
 * buried; whether it also has sky access distinguishes a fully open protrusion from a smaller gap.
 * Generic over structure_id so it applies to any jigsaw/buried structure, not just Trail Ruins.
 */
public final class TrailRuinsEnclosureProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-trail-ruins-enclosure", "1", EnclosureScan::new);
        ProbeRegistry.register(
            "squinch:rtf-structure-terrain-deformation",
			"7",
            StructureTerrainDeformationProbe::new
        );
    }

    private static final class EnclosureScan implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final String structureIdRaw;
        private final ResourceLocation structureId;
        private final int shellExampleLimit;
        private final long maxShellSamples;

        private EnclosureScan(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "rtf-trail-ruins-enclosure");
            this.structureIdRaw = config.has("structure_id")
                ? config.get("structure_id").getAsString()
                : "minecraft:trail_ruins";
            ResourceLocation parsed = ResourceLocation.tryParse(this.structureIdRaw);
            if (parsed == null) {
                throw new IllegalArgumentException("structure_id is not a valid identifier: " + this.structureIdRaw);
            }
            this.structureId = parsed;
            this.shellExampleLimit = config.has("shell_example_limit")
                ? config.get("shell_example_limit").getAsInt()
                : 20;
            this.maxShellSamples = config.has("max_shell_samples")
                ? config.get("max_shell_samples").getAsLong()
                : 50_000L;
            if (this.shellExampleLimit < 0 || this.shellExampleLimit > 1024 || this.maxShellSamples < 1) {
                throw new IllegalArgumentException(
                    "shell_example_limit must be 0..1024 and max_shell_samples must be positive"
                );
            }
        }

        @Override
        public ProbeResult tick(MinecraftServer server) {
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(server.overworld());
            if (snapshot == null) {
                return null;
            }
            ServerLevel level = server.overworld();
            Structure targetStructure = level.registryAccess()
                .registryOrThrow(Registries.STRUCTURE)
                .get(this.structureId);
            JsonArray structuresJson = new JsonArray();
            Set<ChunkPos> seenStarts = new HashSet<>();
            long structureCount = 0;
            if (targetStructure != null) {
                for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                    Map<Structure, StructureStart> starts = ready.chunk().getAllStarts();
                    StructureStart start = starts.get(targetStructure);
                    if (start == null || !start.isValid()) {
                        continue;
                    }
                    if (!seenStarts.add(start.getChunkPos())) {
                        continue;
                    }
                    structureCount++;
                    structuresJson.add(analyzeStructure(level, start));
                }
            }
            JsonObject data = new JsonObject();
            data.addProperty("authority", "finished-chunk-structure-starts");
            data.addProperty("structure_id", this.structureIdRaw);
            data.addProperty("structure_registered", targetStructure != null);
            data.addProperty("structure_instance_count", structureCount);
            data.add("structures", structuresJson);
            return this.selection.result(snapshot, data);
        }

        private JsonObject analyzeStructure(ServerLevel level, StructureStart start) {
            List<StructurePiece> pieces = start.getPieces();
            List<BoundingBox> boxes = new ArrayList<>(pieces.size());
            for (StructurePiece piece : pieces) {
                boxes.add(piece.getBoundingBox());
            }

            long shellExamined = 0;
            long shellOpen = 0;
            long shellSkyExposed = 0;
            long shellSkippedBoundary = 0;
            long shellOwnStructureAdjacent = 0;
            boolean capped = false;
            JsonArray openExamples = new JsonArray();
            Set<Long> visitedShell = new HashSet<>();

            scan:
            for (BoundingBox box : boxes) {
                for (BlockPos pos : shellPositions(box)) {
                    if (shellExamined + shellSkippedBoundary + shellOwnStructureAdjacent >= this.maxShellSamples) {
                        capped = true;
                        break scan;
                    }
                    if (!visitedShell.add(pos.asLong())) {
                        continue;
                    }
                    if (isInsideAny(boxes, pos)) {
                        shellOwnStructureAdjacent++;
                        continue;
                    }
                    if (level.isOutsideBuildHeight(pos)) {
                        shellSkippedBoundary++;
                        continue;
                    }
                    int chunkX = SectionPos.blockToSectionCoord(pos.getX());
                    int chunkZ = SectionPos.blockToSectionCoord(pos.getZ());
                    LevelChunk neighbor = level.getChunkSource().getChunkNow(chunkX, chunkZ);
                    if (neighbor == null || !neighbor.getFullStatus().isOrAfter(FullChunkStatus.FULL)) {
                        shellSkippedBoundary++;
                        continue;
                    }
                    shellExamined++;
                    BlockState state = neighbor.getBlockState(pos);
                    if (isOpen(state)) {
                        shellOpen++;
                        boolean sky = level.canSeeSky(pos);
                        if (sky) {
                            shellSkyExposed++;
                        }
                        if (openExamples.size() < this.shellExampleLimit) {
                            JsonObject example = new JsonObject();
                            example.addProperty("x", pos.getX());
                            example.addProperty("y", pos.getY());
                            example.addProperty("z", pos.getZ());
                            example.addProperty("block", MinecraftProbeHelpers.blockId(state));
                            example.addProperty("can_see_sky", sky);
                            openExamples.add(example);
                        }
                    }
                }
            }

            BoundingBox overall = start.getBoundingBox();
            JsonObject structureJson = new JsonObject();
            structureJson.addProperty("start_chunk_x", start.getChunkPos().x);
            structureJson.addProperty("start_chunk_z", start.getChunkPos().z);
            structureJson.addProperty("bounding_box_min_x", overall.minX());
            structureJson.addProperty("bounding_box_min_y", overall.minY());
            structureJson.addProperty("bounding_box_min_z", overall.minZ());
            structureJson.addProperty("bounding_box_max_x", overall.maxX());
            structureJson.addProperty("bounding_box_max_y", overall.maxY());
            structureJson.addProperty("bounding_box_max_z", overall.maxZ());
            structureJson.addProperty("piece_count", pieces.size());
            structureJson.addProperty("shell_examined", shellExamined);
            structureJson.addProperty("shell_skipped_boundary", shellSkippedBoundary);
            structureJson.addProperty("shell_own_structure_adjacent", shellOwnStructureAdjacent);
            structureJson.addProperty("shell_open", shellOpen);
            structureJson.addProperty("shell_sky_exposed", shellSkyExposed);
            structureJson.addProperty("shell_scan_capped", capped);
            structureJson.addProperty(
                "exposed_fraction", shellExamined > 0 ? (double) shellOpen / shellExamined : 0.0
            );
            structureJson.add("open_examples", openExamples);
            return structureJson;
        }

        private static List<BlockPos> shellPositions(BoundingBox box) {
            int minX = box.minX();
            int maxX = box.maxX();
            int minY = box.minY();
            int maxY = box.maxY();
            int minZ = box.minZ();
            int maxZ = box.maxZ();
            List<BlockPos> positions = new ArrayList<>();
            for (int y = minY; y <= maxY; y++) {
                for (int z = minZ; z <= maxZ; z++) {
                    positions.add(new BlockPos(minX - 1, y, z));
                    positions.add(new BlockPos(maxX + 1, y, z));
                }
                for (int x = minX; x <= maxX; x++) {
                    positions.add(new BlockPos(x, y, minZ - 1));
                    positions.add(new BlockPos(x, y, maxZ + 1));
                }
            }
            for (int x = minX; x <= maxX; x++) {
                for (int z = minZ; z <= maxZ; z++) {
                    positions.add(new BlockPos(x, minY - 1, z));
                    positions.add(new BlockPos(x, maxY + 1, z));
                }
            }
            return positions;
        }

        private static boolean isInsideAny(List<BoundingBox> boxes, BlockPos pos) {
            for (BoundingBox box : boxes) {
                if (box.isInside(pos)) {
                    return true;
                }
            }
            return false;
        }

        private static boolean isOpen(BlockState state) {
            return state.isAir() || !state.getFluidState().isEmpty();
        }
    }
}
