package org.squinchmods.investigate.ftf;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.QuartPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Climate;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;

public final class FtfSpatialCoherenceProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:ftf-spatial-coherence", "1", SpatialCoherence::new);
        ProbeRegistry.register("squinch:ftf-spatial-coherence-underground", "1", SpatialCoherence::new);
    }

    private static final class SpatialCoherence implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final int scanLineCount;
        private final int verticalColumnCount;
        private final int horizontalY;
        private final int minY;
        private final int maxY;

        private SpatialCoherence(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "ftf-spatial-coherence");
            this.scanLineCount = config.has("scan_line_count")
                ? config.get("scan_line_count").getAsInt() : 8;
            this.verticalColumnCount = config.has("vertical_column_count")
                ? config.get("vertical_column_count").getAsInt() : 16;
            this.horizontalY = config.has("horizontal_y")
                ? config.get("horizontal_y").getAsInt()
                : config.has("surface_y") ? config.get("surface_y").getAsInt() : 72;
            this.minY = config.has("min_y")
                ? config.get("min_y").getAsInt() : -64;
            this.maxY = config.has("max_y")
                ? config.get("max_y").getAsInt() : 256;
            if (this.scanLineCount < 1 || this.scanLineCount > 64
                || this.verticalColumnCount < 1 || this.verticalColumnCount > 256) {
                throw new IllegalArgumentException("scan_line_count or vertical_column_count out of range");
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

            int worldMinY = Math.max(level.getMinBuildHeight(), this.minY);
            int worldMaxY = Math.min(level.getMaxBuildHeight() - 1, this.maxY);

            int minChunkX = Integer.MAX_VALUE, maxChunkX = Integer.MIN_VALUE;
            int minChunkZ = Integer.MAX_VALUE, maxChunkZ = Integer.MIN_VALUE;
            for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                int cx = ready.coordinate().x();
                int cz = ready.coordinate().z();
                if (cx < minChunkX) minChunkX = cx;
                if (cx > maxChunkX) maxChunkX = cx;
                if (cz < minChunkZ) minChunkZ = cz;
                if (cz > maxChunkZ) maxChunkZ = cz;
            }

            int minBlockX = minChunkX * 16;
            int maxBlockX = maxChunkX * 16 + 15;
            int minBlockZ = minChunkZ * 16;
            int maxBlockZ = maxChunkZ * 16 + 15;
            int minQuartX = QuartPos.fromBlock(minBlockX);
            int maxQuartX = QuartPos.fromBlock(maxBlockX);
            int minQuartZ = QuartPos.fromBlock(minBlockZ);
            int maxQuartZ = QuartPos.fromBlock(maxBlockZ);
            int minQuartY = QuartPos.fromBlock(worldMinY);
            int maxQuartY = QuartPos.fromBlock(worldMaxY);
            int horizontalQuartY = QuartPos.fromBlock(this.horizontalY);

            int xSpan = maxQuartX - minQuartX + 1;
            int zSpan = maxQuartZ - minQuartZ + 1;

            RunLengthAccumulator horizontalXRuns = new RunLengthAccumulator();
            RunLengthAccumulator horizontalZRuns = new RunLengthAccumulator();
            RunLengthAccumulator verticalRuns = new RunLengthAccumulator();

            GradientAccumulator tempGradientX = new GradientAccumulator();
            GradientAccumulator moistGradientX = new GradientAccumulator();
            GradientAccumulator tempGradientZ = new GradientAccumulator();
            GradientAccumulator moistGradientZ = new GradientAccumulator();
            GradientAccumulator tempGradientY = new GradientAccumulator();
            GradientAccumulator moistGradientY = new GradientAccumulator();

            long horizontalSampled = 0;
            long verticalSampled = 0;

            int effectiveHLines = Math.min(this.scanLineCount, zSpan);
            int zStep = Math.max(1, zSpan / effectiveHLines);
            for (int lineIdx = 0; lineIdx < effectiveHLines; lineIdx++) {
                int fixedQuartZ = minQuartZ + lineIdx * zStep;
                String prevBiome = null;
                int runLength = 0;
                float prevTemp = Float.NaN;
                float prevMoist = Float.NaN;

                for (int quartX = minQuartX; quartX <= maxQuartX; quartX++) {
                    int chunkX = QuartPos.toBlock(quartX) >> 4;
                    int chunkZ = QuartPos.toBlock(fixedQuartZ) >> 4;
                    FinishedChunkSelection.ReadyChunk chunk = findChunk(snapshot, chunkX, chunkZ);
                    if (chunk == null) continue;

                    String biome = MinecraftProbeHelpers.biomeId(
                        chunk.chunk().getNoiseBiome(quartX, horizontalQuartY, fixedQuartZ)
                    );
                    horizontalSampled++;

                    Climate.TargetPoint target = sampler.sample(quartX, horizontalQuartY, fixedQuartZ);
                    float temp = Climate.unquantizeCoord(target.temperature());
                    float moist = Climate.unquantizeCoord(target.humidity());

                    if (!Float.isNaN(prevTemp)) {
                        tempGradientX.add(Math.abs(temp - prevTemp));
                        moistGradientX.add(Math.abs(moist - prevMoist));
                    }
                    prevTemp = temp;
                    prevMoist = moist;

                    if (biome.equals(prevBiome)) {
                        runLength++;
                    } else {
                        if (prevBiome != null) {
                            horizontalXRuns.add(runLength);
                        }
                        prevBiome = biome;
                        runLength = 1;
                    }
                }
                if (prevBiome != null) {
                    horizontalXRuns.add(runLength);
                }
            }

            int effectiveVLines = Math.min(this.scanLineCount, xSpan);
            int xStep = Math.max(1, xSpan / effectiveVLines);
            for (int lineIdx = 0; lineIdx < effectiveVLines; lineIdx++) {
                int fixedQuartX = minQuartX + lineIdx * xStep;
                String prevBiome = null;
                int runLength = 0;
                float prevTemp = Float.NaN;
                float prevMoist = Float.NaN;

                for (int quartZ = minQuartZ; quartZ <= maxQuartZ; quartZ++) {
                    int chunkX = QuartPos.toBlock(fixedQuartX) >> 4;
                    int chunkZ = QuartPos.toBlock(quartZ) >> 4;
                    FinishedChunkSelection.ReadyChunk chunk = findChunk(snapshot, chunkX, chunkZ);
                    if (chunk == null) continue;

                    String biome = MinecraftProbeHelpers.biomeId(
                        chunk.chunk().getNoiseBiome(fixedQuartX, horizontalQuartY, quartZ)
                    );
                    horizontalSampled++;

                    Climate.TargetPoint target = sampler.sample(fixedQuartX, horizontalQuartY, quartZ);
                    float temp = Climate.unquantizeCoord(target.temperature());
                    float moist = Climate.unquantizeCoord(target.humidity());

                    if (!Float.isNaN(prevTemp)) {
                        tempGradientZ.add(Math.abs(temp - prevTemp));
                        moistGradientZ.add(Math.abs(moist - prevMoist));
                    }
                    prevTemp = temp;
                    prevMoist = moist;

                    if (biome.equals(prevBiome)) {
                        runLength++;
                    } else {
                        if (prevBiome != null) {
                            horizontalZRuns.add(runLength);
                        }
                        prevBiome = biome;
                        runLength = 1;
                    }
                }
                if (prevBiome != null) {
                    horizontalZRuns.add(runLength);
                }
            }

            int effectiveColumns = Math.min(this.verticalColumnCount, xSpan * zSpan);
            int columnStep = Math.max(1, (xSpan * zSpan) / effectiveColumns);
            for (int colIdx = 0; colIdx < effectiveColumns; colIdx++) {
                int linearPos = colIdx * columnStep;
                int colQuartX = minQuartX + (linearPos % xSpan);
                int colQuartZ = minQuartZ + (linearPos / xSpan);
                if (colQuartZ > maxQuartZ) break;

                String prevBiome = null;
                int runLength = 0;
                float prevTemp = Float.NaN;
                float prevMoist = Float.NaN;

                for (int quartY = minQuartY; quartY <= maxQuartY; quartY++) {
                    int chunkX = QuartPos.toBlock(colQuartX) >> 4;
                    int chunkZ = QuartPos.toBlock(colQuartZ) >> 4;
                    FinishedChunkSelection.ReadyChunk chunk = findChunk(snapshot, chunkX, chunkZ);
                    if (chunk == null) continue;

                    String biome = MinecraftProbeHelpers.biomeId(
                        chunk.chunk().getNoiseBiome(colQuartX, quartY, colQuartZ)
                    );
                    verticalSampled++;

                    Climate.TargetPoint target = sampler.sample(colQuartX, quartY, colQuartZ);
                    float temp = Climate.unquantizeCoord(target.temperature());
                    float moist = Climate.unquantizeCoord(target.humidity());

                    if (!Float.isNaN(prevTemp)) {
                        tempGradientY.add(Math.abs(temp - prevTemp));
                        moistGradientY.add(Math.abs(moist - prevMoist));
                    }
                    prevTemp = temp;
                    prevMoist = moist;

                    if (biome.equals(prevBiome)) {
                        runLength++;
                    } else {
                        if (prevBiome != null) {
                            verticalRuns.add(runLength);
                        }
                        prevBiome = biome;
                        runLength = 1;
                    }
                }
                if (prevBiome != null) {
                    verticalRuns.add(runLength);
                }
            }

            JsonObject data = new JsonObject();
            data.addProperty("authority", "finished-chunk-spatial-coherence");
            data.addProperty("horizontal_sampled", horizontalSampled);
            data.addProperty("vertical_sampled", verticalSampled);
            data.addProperty("horizontal_y", this.horizontalY);
            data.addProperty("surface_y", this.horizontalY);
            data.addProperty("min_y", worldMinY);
            data.addProperty("max_y", worldMaxY);

            JsonObject grid = new JsonObject();
            grid.addProperty("min_block_x", minBlockX);
            grid.addProperty("max_block_x", maxBlockX);
            grid.addProperty("min_block_z", minBlockZ);
            grid.addProperty("max_block_z", maxBlockZ);
            grid.addProperty("x_scan_lines", effectiveHLines);
            grid.addProperty("z_scan_lines", effectiveVLines);
            grid.addProperty("vertical_columns", effectiveColumns);
            data.add("grid", grid);

            JsonObject runLengths = new JsonObject();
            runLengths.add("horizontal_x", horizontalXRuns.toJson());
            runLengths.add("horizontal_z", horizontalZRuns.toJson());
            runLengths.add("vertical", verticalRuns.toJson());
            data.add("biome_run_lengths", runLengths);

            JsonObject gradients = new JsonObject();
            JsonObject tempGrad = new JsonObject();
            tempGrad.add("x", tempGradientX.toJson());
            tempGrad.add("z", tempGradientZ.toJson());
            tempGrad.add("y", tempGradientY.toJson());
            gradients.add("temperature", tempGrad);
            JsonObject moistGrad = new JsonObject();
            moistGrad.add("x", moistGradientX.toJson());
            moistGrad.add("z", moistGradientZ.toJson());
            moistGrad.add("y", moistGradientY.toJson());
            gradients.add("humidity", moistGrad);
            data.add("climate_gradients", gradients);

            return this.selection.result(snapshot, data);
        }

        private static FinishedChunkSelection.ReadyChunk findChunk(
            FinishedChunkSelection.Snapshot snapshot, int chunkX, int chunkZ
        ) {
            for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                if (ready.coordinate().x() == chunkX && ready.coordinate().z() == chunkZ) {
                    return ready;
                }
            }
            return null;
        }
    }

    private static final class RunLengthAccumulator {
        private final TreeMap<Integer, Long> histogram = new TreeMap<>();
        private long count;
        private long sum;
        private int min = Integer.MAX_VALUE;
        private int max = Integer.MIN_VALUE;

        private void add(int runLength) {
            this.count++;
            this.sum += runLength;
            if (runLength < this.min) this.min = runLength;
            if (runLength > this.max) this.max = runLength;
            this.histogram.merge(runLength, 1L, Long::sum);
        }

        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("runs", this.count);
            if (this.count > 0) {
                result.addProperty("min", this.min);
                result.addProperty("max", this.max);
                result.addProperty("mean", (float) this.sum / this.count);

                long halfCount = this.count / 2;
                long cumulative = 0;
                int median = 0;
                for (var entry : this.histogram.entrySet()) {
                    cumulative += entry.getValue();
                    if (cumulative > halfCount) {
                        median = entry.getKey();
                        break;
                    }
                }
                result.addProperty("median", median);

                long singleRuns = this.histogram.getOrDefault(1, 0L);
                result.addProperty("single_quart_runs", singleRuns);
                result.addProperty("single_quart_fraction",
                    (float) singleRuns / this.count);
            }

            JsonObject hist = new JsonObject();
            for (var entry : this.histogram.entrySet()) {
                hist.addProperty(String.valueOf(entry.getKey()), entry.getValue());
            }
            result.add("histogram", hist);
            return result;
        }
    }

    private static final class GradientAccumulator {
        private long count;
        private double sum;
        private float min = Float.MAX_VALUE;
        private float max = -Float.MAX_VALUE;
        private long zeroCount;
        private long smallCount;
        private long largeCount;

        private static final float SMALL_THRESHOLD = 0.02f;
        private static final float LARGE_THRESHOLD = 0.1f;

        private void add(float absGradient) {
            this.count++;
            this.sum += absGradient;
            if (absGradient < this.min) this.min = absGradient;
            if (absGradient > this.max) this.max = absGradient;
            if (absGradient == 0.0f) this.zeroCount++;
            else if (absGradient <= SMALL_THRESHOLD) this.smallCount++;
            else if (absGradient >= LARGE_THRESHOLD) this.largeCount++;
        }

        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("samples", this.count);
            if (this.count > 0) {
                result.addProperty("min", this.min);
                result.addProperty("max", this.max);
                result.addProperty("mean", (float) (this.sum / this.count));
                result.addProperty("zero_fraction",
                    (float) this.zeroCount / this.count);
                result.addProperty("small_fraction",
                    (float) (this.zeroCount + this.smallCount) / this.count);
                result.addProperty("large_fraction",
                    (float) this.largeCount / this.count);
            }
            return result;
        }
    }
}
