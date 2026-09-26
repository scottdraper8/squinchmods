package org.squinchmods.investigate.ftf;

import java.util.Map;
import java.util.TreeMap;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.world.level.levelgen.Heightmap;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;

/** New one-off probe authored through the external-pack template, not migrated historical code. */
public final class HeightmapDeltaProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:ftf-heightmap-delta", "1", HeightmapDelta::new);
    }

    private static final class HeightmapDelta implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final Heightmap.Types left;
        private final Heightmap.Types right;
        private final int sampleStep;
        private final int absoluteThreshold;
        private final int exampleLimit;

        private HeightmapDelta(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "ftf-heightmap-delta");
            this.left = heightmap(config, "left_heightmap", "WORLD_SURFACE_WG");
            this.right = heightmap(config, "right_heightmap", "OCEAN_FLOOR_WG");
            this.sampleStep = config.has("sample_step") ? config.get("sample_step").getAsInt() : 4;
            this.absoluteThreshold = config.has("absolute_threshold")
                ? config.get("absolute_threshold").getAsInt()
                : 1;
            this.exampleLimit = config.has("example_limit")
                ? config.get("example_limit").getAsInt()
                : 20;
            if (
                this.sampleStep < 1 || this.sampleStep > 16 || 16 % this.sampleStep != 0
                || this.absoluteThreshold < 0 || this.exampleLimit < 0 || this.exampleLimit > 1024
            ) {
                throw new IllegalArgumentException(
                    "sample_step must divide 16; threshold/example_limit must be nonnegative"
                );
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(server.overworld());
            if (snapshot == null) {
                return null;
            }
            Map<Integer, Long> histogram = new TreeMap<>();
            JsonArray examples = new JsonArray();
            long samples = 0;
            long predicateMatches = 0;
            int minimum = Integer.MAX_VALUE;
            int maximum = Integer.MIN_VALUE;
            for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                for (int x = 0; x < 16; x += this.sampleStep) {
                    for (int z = 0; z < 16; z += this.sampleStep) {
                        int leftY = ready.chunk().getHeight(this.left, x, z);
                        int rightY = ready.chunk().getHeight(this.right, x, z);
                        int delta = leftY - rightY;
                        histogram.merge(delta, 1L, Long::sum);
                        minimum = Math.min(minimum, delta);
                        maximum = Math.max(maximum, delta);
                        samples++;
                        if (Math.abs(delta) >= this.absoluteThreshold) {
                            predicateMatches++;
                            if (examples.size() < this.exampleLimit) {
                                JsonObject example = new JsonObject();
                                example.addProperty("x", ready.coordinate().x() * 16 + x);
                                example.addProperty("z", ready.coordinate().z() * 16 + z);
                                example.addProperty("left_y", leftY);
                                example.addProperty("right_y", rightY);
                                example.addProperty("delta", delta);
                                examples.add(example);
                            }
                        }
                    }
                }
            }
            JsonObject histogramJson = new JsonObject();
            histogram.forEach((delta, count) -> histogramJson.addProperty(Integer.toString(delta), count));
            JsonObject data = new JsonObject();
            data.addProperty("authority", "finished-chunk-heightmaps");
            data.addProperty("left_heightmap", this.left.name());
            data.addProperty("right_heightmap", this.right.name());
            data.addProperty("sample_step", this.sampleStep);
            data.addProperty("samples", samples);
            data.addProperty("absolute_threshold", this.absoluteThreshold);
            data.addProperty("predicate_matches", predicateMatches);
            if (samples > 0) {
                data.addProperty("delta_min", minimum);
                data.addProperty("delta_max", maximum);
            }
            data.add("delta_histogram", histogramJson);
            data.add("predicate_examples", examples);
            return this.selection.result(snapshot, data);
        }
    }

    private static Heightmap.Types heightmap(JsonObject config, String key, String fallback) {
        String name = config.has(key) ? config.get(key).getAsString() : fallback;
        try {
            return Heightmap.Types.valueOf(name);
        } catch (IllegalArgumentException exception) {
            throw new IllegalArgumentException(key + " is not a real Heightmap.Types value: " + name);
        }
    }
}
