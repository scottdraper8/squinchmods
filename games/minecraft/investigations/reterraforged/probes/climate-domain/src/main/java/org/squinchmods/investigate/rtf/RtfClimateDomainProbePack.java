package org.squinchmods.investigate.rtf;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.TreeMap;

import com.google.gson.JsonObject;

import net.minecraft.core.QuartPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Climate;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;

public final class RtfClimateDomainProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-climate-domain", "1", ClimateDomain::new);
    }

    private static final int BIN_WIDTH_QUANT = 50;

    private static final class ClimateDomain implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final int sampleMinX;
        private final int sampleMaxX;
        private final int sampleMinZ;
        private final int sampleMaxZ;
        private final int sampleStepBlocks;
        private final int surfaceY;
        private final int[] convergenceRadii;

        private ClimateDomain(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "rtf-climate-domain");
            this.sampleMinX = config.has("sample_min_x")
                ? config.get("sample_min_x").getAsInt() : -5000;
            this.sampleMaxX = config.has("sample_max_x")
                ? config.get("sample_max_x").getAsInt() : 5000;
            this.sampleMinZ = config.has("sample_min_z")
                ? config.get("sample_min_z").getAsInt() : -5000;
            this.sampleMaxZ = config.has("sample_max_z")
                ? config.get("sample_max_z").getAsInt() : 5000;
            this.sampleStepBlocks = config.has("sample_step_blocks")
                ? config.get("sample_step_blocks").getAsInt() : 4;
            this.surfaceY = config.has("surface_y")
                ? config.get("surface_y").getAsInt() : 62;
            if (config.has("convergence_radii")) {
                var arr = config.getAsJsonArray("convergence_radii");
                this.convergenceRadii = new int[arr.size()];
                for (int i = 0; i < arr.size(); i++) {
                    this.convergenceRadii[i] = arr.get(i).getAsInt();
                }
            } else {
                this.convergenceRadii = new int[]{500, 1000, 2500, 5000};
            }
            if (this.sampleStepBlocks < 1 || this.sampleStepBlocks > 64) {
                throw new IllegalArgumentException("sample_step_blocks out of range [1, 64]");
            }
            long gridWidth = (long) this.sampleMaxX - this.sampleMinX;
            long gridHeight = (long) this.sampleMaxZ - this.sampleMinZ;
            long expectedSamples = (gridWidth / this.sampleStepBlocks + 1)
                * (gridHeight / this.sampleStepBlocks + 1);
            if (expectedSamples > 100_000_000L) {
                throw new IllegalArgumentException(
                    "grid would produce " + expectedSamples + " samples; max 100M"
                );
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
            int quartY = QuartPos.fromBlock(this.surfaceY);

            AxisAccumulator temperature = new AxisAccumulator();
            AxisAccumulator humidity = new AxisAccumulator();
            AxisAccumulator continentalness = new AxisAccumulator();
            AxisAccumulator erosion = new AxisAccumulator();
            AxisAccumulator weirdness = new AxisAccumulator();
            AxisAccumulator depth = new AxisAccumulator();

            int centerX = (this.sampleMinX + this.sampleMaxX) / 2;
            int centerZ = (this.sampleMinZ + this.sampleMaxZ) / 2;
            int radiusCount = this.convergenceRadii.length;
            long[][] convMins = new long[radiusCount][6];
            long[][] convMaxs = new long[radiusCount][6];
            for (int r = 0; r < radiusCount; r++) {
                for (int a = 0; a < 6; a++) {
                    convMins[r][a] = Long.MAX_VALUE;
                    convMaxs[r][a] = Long.MIN_VALUE;
                }
            }

            long totalSampled = 0;

            for (int blockX = this.sampleMinX; blockX <= this.sampleMaxX;
                 blockX += this.sampleStepBlocks) {
                for (int blockZ = this.sampleMinZ; blockZ <= this.sampleMaxZ;
                     blockZ += this.sampleStepBlocks) {
                    int quartX = QuartPos.fromBlock(blockX);
                    int quartZ = QuartPos.fromBlock(blockZ);
                    Climate.TargetPoint target = sampler.sample(quartX, quartY, quartZ);
                    totalSampled++;

                    long t = target.temperature();
                    long h = target.humidity();
                    long c = target.continentalness();
                    long e = target.erosion();
                    long w = target.weirdness();
                    long d = target.depth();

                    temperature.add(t);
                    humidity.add(h);
                    continentalness.add(c);
                    erosion.add(e);
                    weirdness.add(w);
                    depth.add(d);

                    int dist = Math.max(
                        Math.abs(blockX - centerX), Math.abs(blockZ - centerZ)
                    );
                    for (int r = 0; r < radiusCount; r++) {
                        if (dist <= this.convergenceRadii[r]) {
                            long[] vals = {t, h, c, e, w, d};
                            for (int a = 0; a < 6; a++) {
                                if (vals[a] < convMins[r][a]) convMins[r][a] = vals[a];
                                if (vals[a] > convMaxs[r][a]) convMaxs[r][a] = vals[a];
                            }
                        }
                    }
                }
            }

            JsonObject data = new JsonObject();
            data.addProperty("authority", "climate-sampler-evaluation");
            data.addProperty("sample_count", totalSampled);

            JsonObject grid = new JsonObject();
            grid.addProperty("min_x", this.sampleMinX);
            grid.addProperty("max_x", this.sampleMaxX);
            grid.addProperty("min_z", this.sampleMinZ);
            grid.addProperty("max_z", this.sampleMaxZ);
            grid.addProperty("step_blocks", this.sampleStepBlocks);
            grid.addProperty("surface_y", this.surfaceY);
            data.add("grid", grid);

            JsonObject axes = new JsonObject();
            axes.add("temperature", temperature.toJson());
            axes.add("humidity", humidity.toJson());
            axes.add("continentalness", continentalness.toJson());
            axes.add("erosion", erosion.toJson());
            axes.add("weirdness", weirdness.toJson());
            axes.add("depth", depth.toJson());
            data.add("axes", axes);

            String[] axisNames = {
                "temperature", "humidity", "continentalness",
                "erosion", "weirdness", "depth"
            };
            JsonObject convergence = new JsonObject();
            for (int r = 0; r < radiusCount; r++) {
                int radius = this.convergenceRadii[r];
                JsonObject radiusObj = new JsonObject();
                for (int a = 0; a < 6; a++) {
                    if (convMins[r][a] == Long.MAX_VALUE) {
                        continue;
                    }
                    JsonObject axisConv = new JsonObject();
                    axisConv.addProperty("min", Climate.unquantizeCoord(convMins[r][a]));
                    axisConv.addProperty("max", Climate.unquantizeCoord(convMaxs[r][a]));
                    radiusObj.add(axisNames[a], axisConv);
                }
                convergence.add("radius_" + radius, radiusObj);
            }
            data.add("convergence", convergence);

            return this.selection.result(snapshot, data);
        }
    }

    private static final class AxisAccumulator {
        private long min = Long.MAX_VALUE;
        private long max = Long.MIN_VALUE;
        private double sum;
        private long count;
        private final TreeMap<Integer, Long> histogram = new TreeMap<>();

        private void add(long quantizedValue) {
            if (quantizedValue < this.min) this.min = quantizedValue;
            if (quantizedValue > this.max) this.max = quantizedValue;
            this.sum += quantizedValue;
            this.count++;
            int bin = Math.floorDiv((int) quantizedValue, BIN_WIDTH_QUANT);
            this.histogram.merge(bin, 1L, Long::sum);
        }

        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("min", Climate.unquantizeCoord(this.min));
            result.addProperty("max", Climate.unquantizeCoord(this.max));
            if (this.count > 0) {
                result.addProperty("mean", (float) (this.sum / this.count / 10000.0));
            }
            result.addProperty("count", this.count);
            result.addProperty("distinct_bins", this.histogram.size());

            if (this.count > 0) {
                long[] targets = {
                    Math.max(1, (long) (this.count * 0.05)),
                    Math.max(1, (long) (this.count * 0.25)),
                    Math.max(1, (long) (this.count * 0.50)),
                    Math.max(1, (long) (this.count * 0.75)),
                    Math.max(1, (long) (this.count * 0.95))
                };
                String[] names = {"p5", "p25", "p50", "p75", "p95"};
                int next = 0;
                long cumulative = 0;
                for (var entry : this.histogram.entrySet()) {
                    cumulative += entry.getValue();
                    while (next < targets.length && cumulative >= targets[next]) {
                        float center = binCenter(entry.getKey());
                        result.addProperty(names[next], center);
                        next++;
                    }
                    if (next >= targets.length) break;
                }
            }

            JsonObject hist = new JsonObject();
            for (var entry : this.histogram.entrySet()) {
                hist.addProperty(
                    String.format("%.4f", binCenter(entry.getKey())),
                    entry.getValue()
                );
            }
            result.add("histogram", hist);

            return result;
        }

        private static float binCenter(int bin) {
            return (bin * BIN_WIDTH_QUANT + BIN_WIDTH_QUANT / 2) / 10000.0f;
        }
    }
}
