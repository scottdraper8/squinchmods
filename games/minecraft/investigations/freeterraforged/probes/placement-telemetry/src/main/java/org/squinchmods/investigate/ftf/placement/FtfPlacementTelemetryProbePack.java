package org.squinchmods.investigate.ftf.placement;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.atomic.LongAdder;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkAccess;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;

public final class FtfPlacementTelemetryProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:ftf-placement-telemetry", "1", PlacementTelemetryProbe::new);
    }

    private static final class PlacementTelemetryProbe implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final Set<String> featureIds;
        private final List<Band> bands;
        private final int topK;

        private PlacementTelemetryProbe(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "ftf-placement-telemetry");
            this.featureIds = Set.copyOf(strings(config, "feature_ids"));
            this.bands = bands(config);
            this.topK = config.has("top_k") ? config.get("top_k").getAsInt() : 20;
            if (this.topK < 0) {
                throw new IllegalArgumentException("top_k must be nonnegative");
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(server.overworld());
            if (snapshot == null) {
                return null;
            }
            Map<Long, ChunkAccess> selectedChunks = snapshot.ready().stream().collect(
                java.util.stream.Collectors.toUnmodifiableMap(
                    ready -> ChunkPos.asLong(ready.coordinate().x(), ready.coordinate().z()),
                    FinishedChunkSelection.ReadyChunk::chunk
                )
            );
            Set<Long> chunks = selectedChunks.keySet();
            Map<String, Aggregate> features = new TreeMap<>();
            PlacementTelemetry.stats().forEach((key, stats) -> {
                if (chunks.contains(key.chunk())
                        && (this.featureIds.isEmpty() || this.featureIds.contains(key.featureId()))) {
                    features.computeIfAbsent(key.featureId(), ignored -> new Aggregate()).add(stats);
                }
            });
            JsonObject featureResults = new JsonObject();
            features.forEach((id, aggregate) -> featureResults.add(
                id, aggregate.toJson(this.bands, this.topK, selectedChunks)
            ));
            JsonObject data = new JsonObject();
            data.addProperty("measurement_phase", "placement");
            data.addProperty("terminal_authority", "finished-chunk");
            data.addProperty("selected_chunk_count", chunks.size());
            data.addProperty("observed_feature_count", features.size());
            data.add("configured_bands", bandsJson(this.bands));
            data.add("features", featureResults);
            return this.selection.result(snapshot, data);
        }
    }

    private static final class Aggregate {
        private long invocations;
        private long successfulInvocations;
        private long cpuNanos;
        private long countPlacementCalls;
        private long countCandidates;
        private long heightCandidates;
        private long biomeChecks;
        private long biomePasses;
        private long blockWrites;
        private long descendantInvocations;
        private long successfulDescendantInvocations;
        private long randomOffsetOutputs;
        private long randomOffsetOutsideOriginChunk;
        private long randomOffsetOutsideRootChunk;
        private long worldGenWrites;
        private final Map<Integer, Long> heights = new TreeMap<>();
        private final Map<Integer, Long> biomePassHeights = new TreeMap<>();
        private final Map<Integer, Long> writeHeights = new TreeMap<>();
        private final Map<Integer, Long> descendantSuccessRelativeX = new TreeMap<>();
        private final Map<Integer, Long> descendantSuccessRelativeZ = new TreeMap<>();
        private final Map<Integer, Long> randomOffsetDeltaX = new TreeMap<>();
        private final Map<Integer, Long> randomOffsetDeltaZ = new TreeMap<>();
        private final Map<Integer, Long> randomOffsetOutputRelativeX = new TreeMap<>();
        private final Map<Integer, Long> randomOffsetOutputRelativeZ = new TreeMap<>();
        private final Map<Integer, Long> blockWriteRelativeX = new TreeMap<>();
        private final Map<Integer, Long> blockWriteRelativeZ = new TreeMap<>();
        private final Map<Integer, Long> worldGenWriteRelativeX = new TreeMap<>();
        private final Map<Integer, Long> worldGenWriteRelativeZ = new TreeMap<>();
        private final Map<Long, String> worldGenWrittenPositions = new LinkedHashMap<>();
        private final Map<String, Long> biomes = new LinkedHashMap<>();
        private final Map<String, Long> blocks = new LinkedHashMap<>();

        private void add(PlacementTelemetry.Stats stats) {
            this.invocations += stats.invocations.sum();
            this.successfulInvocations += stats.successfulInvocations.sum();
            this.cpuNanos += stats.cpuNanos.sum();
            this.countPlacementCalls += stats.countPlacementCalls.sum();
            this.countCandidates += stats.countCandidates.sum();
            this.heightCandidates += stats.heightCandidates.sum();
            this.biomeChecks += stats.biomeChecks.sum();
            this.biomePasses += stats.biomePasses.sum();
            this.blockWrites += stats.blockWrites.sum();
            this.descendantInvocations += stats.descendantInvocations.sum();
            this.successfulDescendantInvocations += stats.successfulDescendantInvocations.sum();
            this.randomOffsetOutputs += stats.randomOffsetOutputs.sum();
            this.randomOffsetOutsideOriginChunk += stats.randomOffsetOutsideOriginChunk.sum();
            this.randomOffsetOutsideRootChunk += stats.randomOffsetOutsideRootChunk.sum();
            this.worldGenWrites += stats.worldGenWrites.sum();
            mergeAdders(this.heights, stats.heightByY);
            mergeAdders(this.biomePassHeights, stats.biomePassByY);
            mergeAdders(this.writeHeights, stats.blockWriteByY);
            mergeAdders(this.descendantSuccessRelativeX, stats.descendantSuccessRelativeX);
            mergeAdders(this.descendantSuccessRelativeZ, stats.descendantSuccessRelativeZ);
            mergeAdders(this.randomOffsetDeltaX, stats.randomOffsetDeltaX);
            mergeAdders(this.randomOffsetDeltaZ, stats.randomOffsetDeltaZ);
            mergeAdders(this.randomOffsetOutputRelativeX, stats.randomOffsetOutputRelativeX);
            mergeAdders(this.randomOffsetOutputRelativeZ, stats.randomOffsetOutputRelativeZ);
            mergeAdders(this.blockWriteRelativeX, stats.blockWriteRelativeX);
            mergeAdders(this.blockWriteRelativeZ, stats.blockWriteRelativeZ);
            mergeAdders(this.worldGenWriteRelativeX, stats.worldGenWriteRelativeX);
            mergeAdders(this.worldGenWriteRelativeZ, stats.worldGenWriteRelativeZ);
            stats.worldGenWrittenPositions.forEach((position, block) ->
                this.worldGenWrittenPositions.merge(
                    position, block, (first, second) -> first.equals(second) ? first : ""
                )
            );
            mergeAdders(this.biomes, stats.passedBiomes);
            mergeAdders(this.blocks, stats.writtenBlocks);
        }

        private JsonObject toJson(List<Band> bands, int topK, Map<Long, ChunkAccess> selectedChunks) {
            JsonObject result = new JsonObject();
            result.addProperty("invocations", this.invocations);
            result.addProperty("successful_invocations", this.successfulInvocations);
            result.addProperty("feature_cpu_nanos", this.cpuNanos);
            result.addProperty("count_placement_calls", this.countPlacementCalls);
            result.addProperty("count_candidates", this.countCandidates);
            result.addProperty("height_candidates", this.heightCandidates);
            result.addProperty("biome_checks", this.biomeChecks);
            result.addProperty("biome_passes", this.biomePasses);
            result.addProperty("block_writes", this.blockWrites);
            result.addProperty("descendant_invocations", this.descendantInvocations);
            result.addProperty("successful_descendant_invocations", this.successfulDescendantInvocations);
            result.addProperty("random_offset_outputs", this.randomOffsetOutputs);
            result.addProperty("random_offset_outside_origin_chunk", this.randomOffsetOutsideOriginChunk);
            result.addProperty("random_offset_outside_root_chunk", this.randomOffsetOutsideRootChunk);
            result.addProperty("worldgen_writes", this.worldGenWrites);
            result.add("height_histogram", integerCounts(this.heights));
            result.add("biome_pass_height_histogram", integerCounts(this.biomePassHeights));
            result.add("block_write_height_histogram", integerCounts(this.writeHeights));
            result.add("descendant_success_relative_x", integerCounts(this.descendantSuccessRelativeX));
            result.add("descendant_success_relative_z", integerCounts(this.descendantSuccessRelativeZ));
            result.add("random_offset_delta_x", integerCounts(this.randomOffsetDeltaX));
            result.add("random_offset_delta_z", integerCounts(this.randomOffsetDeltaZ));
            result.add("random_offset_output_relative_x", integerCounts(this.randomOffsetOutputRelativeX));
            result.add("random_offset_output_relative_z", integerCounts(this.randomOffsetOutputRelativeZ));
            result.add("block_write_relative_x", integerCounts(this.blockWriteRelativeX));
            result.add("block_write_relative_z", integerCounts(this.blockWriteRelativeZ));
            result.add("worldgen_write_relative_x", integerCounts(this.worldGenWriteRelativeX));
            result.add("worldgen_write_relative_z", integerCounts(this.worldGenWriteRelativeZ));
            result.add("worldgen_write_retention", retention(selectedChunks));
            result.add("height_bands", bandCounts(this.heights, bands));
            result.add("biome_pass_bands", bandCounts(this.biomePassHeights, bands));
            result.add("block_write_bands", bandCounts(this.writeHeights, bands));
            result.add("top_passed_biomes", stringCounts(MinecraftProbeHelpers.topK(this.biomes, topK)));
            result.add("top_written_blocks", stringCounts(MinecraftProbeHelpers.topK(this.blocks, topK)));
            return result;
        }

        private JsonObject retention(Map<Long, ChunkAccess> selectedChunks) {
            long checked = 0;
            long retained = 0;
            long changed = 0;
            long conflicts = 0;
            long outsideSelection = 0;
            Map<Integer, Long> changedLocalX = new TreeMap<>();
            Map<Integer, Long> changedLocalZ = new TreeMap<>();
            Map<Integer, Long> retainedLocalX = new TreeMap<>();
            Map<Integer, Long> retainedLocalZ = new TreeMap<>();
            for (Map.Entry<Long, String> entry : this.worldGenWrittenPositions.entrySet()) {
                if (entry.getValue().isEmpty()) {
                    conflicts++;
                    continue;
                }
                BlockPos position = BlockPos.of(entry.getKey());
                ChunkAccess chunk = selectedChunks.get(new ChunkPos(position).toLong());
                if (chunk == null) {
                    outsideSelection++;
                    continue;
                }
                checked++;
                boolean same = entry.getValue().equals(
                    MinecraftProbeHelpers.blockId(chunk.getBlockState(position))
                );
                Map<Integer, Long> xCounts = same ? retainedLocalX : changedLocalX;
                Map<Integer, Long> zCounts = same ? retainedLocalZ : changedLocalZ;
                xCounts.merge(Math.floorMod(position.getX(), 16), 1L, Long::sum);
                zCounts.merge(Math.floorMod(position.getZ(), 16), 1L, Long::sum);
                if (same) {
                    retained++;
                } else {
                    changed++;
                }
            }
            JsonObject result = new JsonObject();
            result.addProperty("unique_positions", this.worldGenWrittenPositions.size());
            result.addProperty("checked_positions", checked);
            result.addProperty("retained_positions", retained);
            result.addProperty("changed_positions", changed);
            result.addProperty("conflicting_writes", conflicts);
            result.addProperty("outside_selection", outsideSelection);
            result.add("changed_local_x", integerCounts(changedLocalX));
            result.add("changed_local_z", integerCounts(changedLocalZ));
            result.add("retained_local_x", integerCounts(retainedLocalX));
            result.add("retained_local_z", integerCounts(retainedLocalZ));
            return result;
        }
    }

    private static <K> void mergeAdders(Map<K, Long> target, Map<K, LongAdder> source) {
        source.forEach((key, value) -> target.merge(key, value.sum(), Long::sum));
    }

    private static List<String> strings(JsonObject config, String key) {
        if (!config.has(key)) {
            return List.of();
        }
        List<String> result = new ArrayList<>();
        for (JsonElement element : config.getAsJsonArray(key)) {
            result.add(element.getAsString());
        }
        return result;
    }

    private static List<Band> bands(JsonObject config) {
        if (!config.has("bands")) {
            return List.of();
        }
        List<Band> result = new ArrayList<>();
        for (JsonElement element : config.getAsJsonArray("bands")) {
            JsonObject value = element.getAsJsonObject();
            Band band = new Band(
                value.get("id").getAsString(),
                value.get("min_y").getAsInt(),
                value.get("max_y").getAsInt()
            );
            if (band.id().isBlank() || band.minY() > band.maxY()) {
                throw new IllegalArgumentException("band id must be nonempty and min_y <= max_y");
            }
            result.add(band);
        }
        return List.copyOf(result);
    }

    private static JsonObject bandCounts(Map<Integer, Long> histogram, List<Band> bands) {
        JsonObject result = new JsonObject();
        for (Band band : bands) {
            long count = histogram.entrySet().stream()
                .filter(entry -> band.includes(entry.getKey()))
                .mapToLong(Map.Entry::getValue)
                .sum();
            result.addProperty(band.id(), count);
        }
        return result;
    }

    private static JsonArray bandsJson(List<Band> bands) {
        JsonArray result = new JsonArray();
        for (Band band : bands) {
            JsonObject value = new JsonObject();
            value.addProperty("id", band.id());
            value.addProperty("min_y", band.minY());
            value.addProperty("max_y", band.maxY());
            result.add(value);
        }
        return result;
    }

    private static JsonObject integerCounts(Map<Integer, Long> values) {
        JsonObject result = new JsonObject();
        values.forEach((key, value) -> result.addProperty(Integer.toString(key), value));
        return result;
    }

    private static JsonObject stringCounts(Map<String, Long> values) {
        JsonObject result = new JsonObject();
        values.forEach(result::addProperty);
        return result;
    }

    private record Band(String id, int minY, int maxY) {
        private boolean includes(int y) {
            return y >= this.minY && y <= this.maxY;
        }
    }
}
