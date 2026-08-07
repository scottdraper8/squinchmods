package org.squinchmods.investigate.rtf.placement;

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

import net.minecraft.world.level.ChunkPos;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;

public final class RtfPlacementTelemetryProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-placement-telemetry", "1", PlacementTelemetryProbe::new);
    }

    private static final class PlacementTelemetryProbe implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final Set<String> featureIds;
        private final List<Band> bands;
        private final int topK;

        private PlacementTelemetryProbe(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "rtf-placement-telemetry");
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
            Set<Long> chunks = snapshot.ready().stream()
                .map(ready -> ChunkPos.asLong(ready.coordinate().x(), ready.coordinate().z()))
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
            Map<String, Aggregate> features = new TreeMap<>();
            PlacementTelemetry.stats().forEach((key, stats) -> {
                if (chunks.contains(key.chunk())
                        && (this.featureIds.isEmpty() || this.featureIds.contains(key.featureId()))) {
                    features.computeIfAbsent(key.featureId(), ignored -> new Aggregate()).add(stats);
                }
            });
            JsonObject featureResults = new JsonObject();
            features.forEach((id, aggregate) -> featureResults.add(id, aggregate.toJson(this.bands, this.topK)));
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
        private final Map<Integer, Long> heights = new TreeMap<>();
        private final Map<Integer, Long> biomePassHeights = new TreeMap<>();
        private final Map<Integer, Long> writeHeights = new TreeMap<>();
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
            mergeAdders(this.heights, stats.heightByY);
            mergeAdders(this.biomePassHeights, stats.biomePassByY);
            mergeAdders(this.writeHeights, stats.blockWriteByY);
            mergeAdders(this.biomes, stats.passedBiomes);
            mergeAdders(this.blocks, stats.writtenBlocks);
        }

        private JsonObject toJson(List<Band> bands, int topK) {
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
            result.add("height_histogram", integerCounts(this.heights));
            result.add("biome_pass_height_histogram", integerCounts(this.biomePassHeights));
            result.add("block_write_height_histogram", integerCounts(this.writeHeights));
            result.add("height_bands", bandCounts(this.heights, bands));
            result.add("biome_pass_bands", bandCounts(this.biomePassHeights, bands));
            result.add("block_write_bands", bandCounts(this.writeHeights, bands));
            result.add("top_passed_biomes", stringCounts(MinecraftProbeHelpers.topK(this.biomes, topK)));
            result.add("top_written_blocks", stringCounts(MinecraftProbeHelpers.topK(this.blocks, topK)));
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
