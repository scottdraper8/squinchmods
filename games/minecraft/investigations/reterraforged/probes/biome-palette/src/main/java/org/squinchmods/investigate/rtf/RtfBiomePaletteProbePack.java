package org.squinchmods.investigate.rtf;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import net.minecraft.core.BlockPos;
import net.minecraft.core.QuartPos;
import net.minecraft.server.level.ServerLevel;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;

/** Parameterized successor to the hardcoded RealChunkBiomeProfileScanner. */
public final class RtfBiomePaletteProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-biome-palette", "1", BiomePalette::new);
    }

    private static final class BiomePalette implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final Integer requestedMinY;
        private final Integer requestedMaxY;
        private final int horizontalQuartStep;
        private final int verticalQuartStep;
        private final int topK;
        private final int exampleLimit;
        private final List<Band> bands;

        private BiomePalette(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "rtf-biome-palette");
            this.requestedMinY = config.has("min_y") ? config.get("min_y").getAsInt() : null;
            this.requestedMaxY = config.has("max_y") ? config.get("max_y").getAsInt() : null;
            this.horizontalQuartStep = config.has("horizontal_quart_step")
                ? config.get("horizontal_quart_step").getAsInt()
                : 1;
            this.verticalQuartStep = config.has("vertical_quart_step")
                ? config.get("vertical_quart_step").getAsInt()
                : 1;
            this.topK = config.has("top_k") ? config.get("top_k").getAsInt() : 20;
            this.exampleLimit = config.has("example_limit")
                ? config.get("example_limit").getAsInt()
                : 20;
            if (
                this.horizontalQuartStep < 1 || this.horizontalQuartStep > 4
                || 4 % this.horizontalQuartStep != 0
                || this.verticalQuartStep < 1 || this.verticalQuartStep > 64
                || this.topK < 0 || this.exampleLimit < 0 || this.exampleLimit > 1024
            ) {
                throw new IllegalArgumentException(
                    "quart steps are out of range or top_k/example_limit is negative"
                );
            }
            this.bands = bands(config);
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
            if (snapshot == null) {
                return null;
            }
            int minY = Math.max(
                level.getMinBuildHeight(),
                this.requestedMinY == null ? level.getMinBuildHeight() : this.requestedMinY
            );
            int maxY = Math.min(
                level.getMaxBuildHeight() - 1,
                this.requestedMaxY == null ? level.getMaxBuildHeight() - 1 : this.requestedMaxY
            );
            if (minY > maxY) {
                throw new IllegalArgumentException("requested vertical bounds do not intersect the world");
            }
            int minQuartY = QuartPos.fromBlock(minY);
            int maxQuartY = QuartPos.fromBlock(maxY);
            Map<String, BiomeStats> stats = new LinkedHashMap<>();
            JsonArray airExamples = new JsonArray();
            long sampled = 0;
            long air = 0;
            long columns = 0;
            BlockPos.MutableBlockPos cursor = new BlockPos.MutableBlockPos();
            for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                int chunkQuartX = ready.coordinate().x() * 4;
                int chunkQuartZ = ready.coordinate().z() * 4;
                for (int localQuartX = 0; localQuartX < 4; localQuartX += this.horizontalQuartStep) {
                    for (int localQuartZ = 0; localQuartZ < 4; localQuartZ += this.horizontalQuartStep) {
                        columns++;
                        int quartX = chunkQuartX + localQuartX;
                        int quartZ = chunkQuartZ + localQuartZ;
                        int blockX = QuartPos.toBlock(quartX) + 2;
                        int blockZ = QuartPos.toBlock(quartZ) + 2;
                        for (int quartY = minQuartY; quartY <= maxQuartY; quartY += this.verticalQuartStep) {
                            int blockY = Math.min(maxY, QuartPos.toBlock(quartY) + 2);
                            String biome = MinecraftProbeHelpers.biomeId(
                                ready.chunk().getNoiseBiome(quartX, quartY, quartZ)
                            );
                            BiomeStats biomeStats = stats.computeIfAbsent(biome, ignored -> new BiomeStats());
                            biomeStats.samples++;
                            biomeStats.minY = Math.min(biomeStats.minY, blockY);
                            biomeStats.maxY = Math.max(biomeStats.maxY, blockY);
                            for (Band band : this.bands) {
                                if (band.includes(blockY)) {
                                    biomeStats.bands.merge(band.id(), 1L, Long::sum);
                                }
                            }
                            sampled++;
                            if (ready.chunk().getBlockState(cursor.set(blockX, blockY, blockZ)).isAir()) {
                                biomeStats.airSamples++;
                                air++;
                                if (airExamples.size() < this.exampleLimit) {
                                    JsonObject example = new JsonObject();
                                    example.addProperty("x", blockX);
                                    example.addProperty("y", blockY);
                                    example.addProperty("z", blockZ);
                                    example.addProperty("biome_id", biome);
                                    airExamples.add(example);
                                }
                            }
                        }
                    }
                }
            }
            Map<String, Long> totals = new LinkedHashMap<>();
            stats.forEach((id, value) -> totals.put(id, value.samples));
            JsonObject details = new JsonObject();
            for (String id : MinecraftProbeHelpers.topK(totals, this.topK).keySet()) {
                details.add(id, stats.get(id).toJson());
            }
            JsonObject data = new JsonObject();
            data.addProperty("authority", "finished-chunk-biome-palette");
            data.addProperty("min_y", minY);
            data.addProperty("max_y", maxY);
            data.addProperty("columns", columns);
            data.addProperty("sampled_quart_cells", sampled);
            data.addProperty("air_quart_centers", air);
            data.addProperty("horizontal_quart_step", this.horizontalQuartStep);
            data.addProperty("vertical_quart_step", this.verticalQuartStep);
            data.add("biomes", details);
            data.add("air_examples", airExamples);
            data.add("bands", bandsJson(this.bands));
            return this.selection.result(snapshot, data);
        }
    }

    private static List<Band> bands(JsonObject config) {
        if (!config.has("bands")) {
            return List.of();
        }
        List<Band> result = new ArrayList<>();
        for (JsonElement element : config.getAsJsonArray("bands")) {
            JsonObject value = element.getAsJsonObject();
            String id = value.get("id").getAsString();
            int minY = value.get("min_y").getAsInt();
            int maxY = value.get("max_y").getAsInt();
            if (id.isBlank() || minY > maxY) {
                throw new IllegalArgumentException("band id must be nonempty and min_y <= max_y");
            }
            result.add(new Band(id, minY, maxY));
        }
        return List.copyOf(result);
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

    private record Band(String id, int minY, int maxY) {
        private boolean includes(int y) {
            return y >= this.minY && y <= this.maxY;
        }
    }

    private static final class BiomeStats {
        private long samples;
        private long airSamples;
        private int minY = Integer.MAX_VALUE;
        private int maxY = Integer.MIN_VALUE;
        private final Map<String, Long> bands = new LinkedHashMap<>();

        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("samples", this.samples);
            result.addProperty("air_samples", this.airSamples);
            result.addProperty("min_y", this.minY);
            result.addProperty("max_y", this.maxY);
            JsonObject bandCounts = new JsonObject();
            this.bands.forEach(bandCounts::addProperty);
            result.add("bands", bandCounts);
            return result;
        }
    }
}
