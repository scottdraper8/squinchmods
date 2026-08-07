package org.squinchmods.investigate.rtf;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.Holder;
import net.minecraft.core.QuartPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.chunk.LevelChunk;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;

public final class RtfClimateInspectorProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-climate-inspector", "1", ClimateInspector::new);
    }

    private static final class ClimateInspector implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final List<int[]> points;
        private final int horizontalQuartStep;
        private final int verticalQuartStep;
        private final boolean useGrid;

        private ClimateInspector(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "rtf-climate-inspector");
            this.horizontalQuartStep = config.has("horizontal_quart_step")
                ? config.get("horizontal_quart_step").getAsInt()
                : 4;
            this.verticalQuartStep = config.has("vertical_quart_step")
                ? config.get("vertical_quart_step").getAsInt()
                : 4;
            if (config.has("points")) {
                this.useGrid = false;
                this.points = new ArrayList<>();
                for (var element : config.getAsJsonArray("points")) {
                    JsonArray point = element.getAsJsonArray();
                    if (point.size() != 3) {
                        throw new IllegalArgumentException("each point must have exactly 3 coordinates [x, y, z]");
                    }
                    this.points.add(new int[]{
                        point.get(0).getAsInt(),
                        point.get(1).getAsInt(),
                        point.get(2).getAsInt()
                    });
                }
                if (this.points.isEmpty()) {
                    throw new IllegalArgumentException("points array must not be empty");
                }
            } else {
                this.useGrid = true;
                this.points = List.of();
            }
            if (this.horizontalQuartStep < 1 || this.horizontalQuartStep > 16
                || this.verticalQuartStep < 1 || this.verticalQuartStep > 64) {
                throw new IllegalArgumentException("quart steps are out of range");
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
            if (snapshot == null) {
                return null;
            }
            Climate.Sampler sampler = level.getChunkSource().randomState().sampler();
            BiomeSource biomeSource = level.getChunkSource().getGenerator().getBiomeSource();
            int minY = level.getMinBuildHeight();
            int maxY = level.getMaxBuildHeight() - 1;
            JsonArray samples = new JsonArray();
            long inspected = 0;
            long divergences = 0;
            Map<String, Long> finishedBiomeCounts = new LinkedHashMap<>();
            Map<String, Long> directBiomeCounts = new LinkedHashMap<>();
            Map<String, Long> divergenceBiomePairs = new LinkedHashMap<>();

            if (this.useGrid) {
                for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                    int chunkQuartX = ready.coordinate().x() * 4;
                    int chunkQuartZ = ready.coordinate().z() * 4;
                    int minQuartY = QuartPos.fromBlock(minY);
                    int maxQuartY = QuartPos.fromBlock(maxY);
                    for (int lqx = 0; lqx < 4; lqx += this.horizontalQuartStep) {
                        for (int lqz = 0; lqz < 4; lqz += this.horizontalQuartStep) {
                            int quartX = chunkQuartX + lqx;
                            int quartZ = chunkQuartZ + lqz;
                            for (int quartY = minQuartY; quartY <= maxQuartY; quartY += this.verticalQuartStep) {
                                inspected++;
                                SampleResult result = sampleAt(
                                    sampler, biomeSource, ready.chunk(), quartX, quartY, quartZ
                                );
                                finishedBiomeCounts.merge(result.finishedBiome, 1L, Long::sum);
                                directBiomeCounts.merge(result.directBiome, 1L, Long::sum);
                                if (!result.finishedBiome.equals(result.directBiome)) {
                                    divergences++;
                                    String pair = result.finishedBiome + " -> " + result.directBiome;
                                    divergenceBiomePairs.merge(pair, 1L, Long::sum);
                                }
                                if (samples.size() < 500) {
                                    samples.add(result.toJson(quartX, quartY, quartZ));
                                }
                            }
                        }
                    }
                }
            } else {
                for (int[] point : this.points) {
                    int blockX = point[0];
                    int blockY = point[1];
                    int blockZ = point[2];
                    int quartX = QuartPos.fromBlock(blockX);
                    int quartY = QuartPos.fromBlock(blockY);
                    int quartZ = QuartPos.fromBlock(blockZ);
                    int chunkX = Math.floorDiv(blockX, 16);
                    int chunkZ = Math.floorDiv(blockZ, 16);
                    LevelChunk chunk = null;
                    for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                        if (ready.coordinate().x() == chunkX && ready.coordinate().z() == chunkZ) {
                            chunk = ready.chunk();
                            break;
                        }
                    }
                    if (chunk == null) {
                        continue;
                    }
                    inspected++;
                    SampleResult result = sampleAt(sampler, biomeSource, chunk, quartX, quartY, quartZ);
                    finishedBiomeCounts.merge(result.finishedBiome, 1L, Long::sum);
                    directBiomeCounts.merge(result.directBiome, 1L, Long::sum);
                    if (!result.finishedBiome.equals(result.directBiome)) {
                        divergences++;
                        String pair = result.finishedBiome + " -> " + result.directBiome;
                        divergenceBiomePairs.merge(pair, 1L, Long::sum);
                    }
                    samples.add(result.toJson(quartX, quartY, quartZ));
                }
            }

            JsonObject data = new JsonObject();
            data.addProperty("authority_biome", "finished-chunk");
            data.addProperty("authority_climate", "re-sampled-climate-sampler");
            data.addProperty("authority_direct_biome", "direct-biome-source-query");
            data.addProperty("inspected", inspected);
            data.addProperty("divergences", divergences);
            data.add("samples", samples);
            JsonObject finishedCounts = new JsonObject();
            finishedBiomeCounts.forEach(finishedCounts::addProperty);
            data.add("finished_biome_counts", finishedCounts);
            JsonObject directCounts = new JsonObject();
            directBiomeCounts.forEach(directCounts::addProperty);
            data.add("direct_biome_counts", directCounts);
            if (divergences > 0) {
                JsonObject divPairs = new JsonObject();
                divergenceBiomePairs.forEach(divPairs::addProperty);
                data.add("divergence_pairs", divPairs);
            }
            return this.selection.result(snapshot, data);
        }

        private static SampleResult sampleAt(
            Climate.Sampler sampler,
            BiomeSource biomeSource,
            LevelChunk chunk,
            int quartX, int quartY, int quartZ
        ) {
            Climate.TargetPoint target = sampler.sample(quartX, quartY, quartZ);
            String finishedBiome = MinecraftProbeHelpers.biomeId(
                chunk.getNoiseBiome(quartX, quartY, quartZ)
            );
            Holder<Biome> directResult = biomeSource.getNoiseBiome(quartX, quartY, quartZ, sampler);
            String directBiome = MinecraftProbeHelpers.biomeId(directResult);
            return new SampleResult(
                finishedBiome, directBiome,
                Climate.unquantizeCoord(target.temperature()),
                Climate.unquantizeCoord(target.humidity()),
                Climate.unquantizeCoord(target.continentalness()),
                Climate.unquantizeCoord(target.erosion()),
                Climate.unquantizeCoord(target.depth()),
                Climate.unquantizeCoord(target.weirdness())
            );
        }
    }

    private record SampleResult(
        String finishedBiome, String directBiome,
        float temperature, float humidity, float continentalness,
        float erosion, float depth, float weirdness
    ) {
        private JsonObject toJson(int quartX, int quartY, int quartZ) {
            JsonObject result = new JsonObject();
            result.addProperty("quart_x", quartX);
            result.addProperty("quart_y", quartY);
            result.addProperty("quart_z", quartZ);
            result.addProperty("block_x", QuartPos.toBlock(quartX) + 2);
            result.addProperty("block_y", QuartPos.toBlock(quartY) + 2);
            result.addProperty("block_z", QuartPos.toBlock(quartZ) + 2);
            result.addProperty("finished_biome", this.finishedBiome);
            result.addProperty("direct_biome", this.directBiome);
            result.addProperty("biomes_agree", this.finishedBiome.equals(this.directBiome));
            JsonObject climate = new JsonObject();
            climate.addProperty("temperature", this.temperature);
            climate.addProperty("humidity", this.humidity);
            climate.addProperty("continentalness", this.continentalness);
            climate.addProperty("erosion", this.erosion);
            climate.addProperty("depth", this.depth);
            climate.addProperty("weirdness", this.weirdness);
            result.add("climate", climate);
            return result;
        }
    }
}
