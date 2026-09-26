package org.squinchmods.investigate;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.Heightmap;

/** Generic finished-chunk surface scanner; retained ID is squinch:finished-chunk-palette. */
final class FinishedChunkPalette implements ProbeExecution {
    private final FinishedChunkSelection selection;
    private final Heightmap.Types heightmapType;
    private final int sampleStep;
    private final int topK;
    private final int exampleLimit;
    private final List<String> blockIds;
    private final List<String> biomeIds;
    private final Integer minHeight;
    private final Integer maxHeight;

    FinishedChunkPalette(ProbeRequest request) {
        JsonObject config = request.config();
        this.selection = new FinishedChunkSelection(config, "finished-chunk-palette");
        String heightmapName = config.has("sample_heightmap")
            ? config.get("sample_heightmap").getAsString()
            : "WORLD_SURFACE";
        try {
            this.heightmapType = Heightmap.Types.valueOf(heightmapName);
        } catch (IllegalArgumentException exception) {
            throw new IllegalArgumentException(
                "sample_heightmap is not a real Heightmap.Types value: " + heightmapName,
                exception
            );
        }
        this.sampleStep = config.has("sample_step") ? config.get("sample_step").getAsInt() : 16;
        this.topK = config.has("top_k") ? config.get("top_k").getAsInt() : 10;
        this.exampleLimit = config.has("example_limit")
            ? config.get("example_limit").getAsInt()
            : 20;
        if (
            this.sampleStep < 1 || this.sampleStep > 16 || 16 % this.sampleStep != 0
            || this.topK < 0 || this.exampleLimit < 0 || this.exampleLimit > 1024
        ) {
            throw new IllegalArgumentException(
                "sample_step must divide 16; top_k and example_limit must be nonnegative"
            );
        }
        JsonObject predicates = config.has("predicates")
            ? config.getAsJsonObject("predicates")
            : new JsonObject();
        this.blockIds = strings(predicates, "block_ids");
        this.biomeIds = strings(predicates, "biome_ids");
        this.minHeight = predicates.has("min_height")
            ? predicates.get("min_height").getAsInt()
            : null;
        this.maxHeight = predicates.has("max_height")
            ? predicates.get("max_height").getAsInt()
            : null;
        if (this.minHeight != null && this.maxHeight != null && this.minHeight > this.maxHeight) {
            throw new IllegalArgumentException("predicates min_height exceeds max_height");
        }
    }

    @Override
    public ProbeResult tick(MinecraftServer server) {
        ServerLevel level = server.overworld();
        FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
        if (snapshot == null) {
            return null;
        }
        Map<String, Long> blockCounts = new LinkedHashMap<>();
        Map<String, Long> biomeCounts = new LinkedHashMap<>();
        Map<Integer, Long> heightCounts = new java.util.TreeMap<>();
        JsonArray examples = new JsonArray();
        long columns = 0;
        long matches = 0;
        int minimum = Integer.MAX_VALUE;
        int maximum = Integer.MIN_VALUE;
        int offset = this.sampleStep == 16 ? 8 : this.sampleStep / 2;
        for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
            int baseX = ready.coordinate().x() * 16;
            int baseZ = ready.coordinate().z() * 16;
            for (int localX = offset; localX < 16; localX += this.sampleStep) {
                for (int localZ = offset; localZ < 16; localZ += this.sampleStep) {
                    int x = baseX + localX;
                    int z = baseZ + localZ;
                    int height = ready.chunk().getHeight(this.heightmapType, localX, localZ);
                    BlockPos surface = new BlockPos(x, height - 1, z);
                    String block = MinecraftProbeHelpers.blockId(ready.chunk().getBlockState(surface));
                    Holder<Biome> biome = ready.chunk().getNoiseBiome(
                        Math.floorDiv(x, 4), Math.floorDiv(height - 1, 4), Math.floorDiv(z, 4)
                    );
                    String biomeId = MinecraftProbeHelpers.biomeId(biome);
                    blockCounts.merge(block, 1L, Long::sum);
                    biomeCounts.merge(biomeId, 1L, Long::sum);
                    heightCounts.merge(height, 1L, Long::sum);
                    minimum = Math.min(minimum, height);
                    maximum = Math.max(maximum, height);
                    columns++;
                    if (matches(block, biomeId, height)) {
                        matches++;
                        if (examples.size() < this.exampleLimit) {
                            JsonObject example = new JsonObject();
                            example.addProperty("x", x);
                            example.addProperty("z", z);
                            example.addProperty("height", height);
                            example.addProperty("block_id", block);
                            example.addProperty("biome_id", biomeId);
                            examples.add(example);
                        }
                    }
                }
            }
        }
        JsonObject data = new JsonObject();
        data.addProperty("authority", "finished-chunk");
        data.addProperty("sampled_chunks", snapshot.ready().size());
        data.addProperty("sampled_columns", columns);
        data.addProperty("predicate_matches", matches);
        data.addProperty("sample_heightmap", this.heightmapType.name());
        data.addProperty("sample_step", this.sampleStep);
        if (columns > 0) {
            data.addProperty("height_min", minimum);
            data.addProperty("height_max", maximum);
        }
        JsonObject blocks = counts(MinecraftProbeHelpers.topK(blockCounts, this.topK));
        JsonObject biomes = counts(MinecraftProbeHelpers.topK(biomeCounts, this.topK));
        data.add("block_histogram", blocks);
        data.add("biome_histogram", biomes);
        data.add("height_histogram", integerCounts(heightCounts));
        data.add("predicate_examples", examples);
        // Backward-compatible names from the original example probe.
        data.add("top_block_ids", blocks.deepCopy());
        data.add("top_biome_ids", biomes.deepCopy());
        return this.selection.result(snapshot, data);
    }

    private boolean matches(String block, String biome, int height) {
        return (this.blockIds.isEmpty() || this.blockIds.contains(block))
            && (this.biomeIds.isEmpty() || this.biomeIds.contains(biome))
            && (this.minHeight == null || height >= this.minHeight)
            && (this.maxHeight == null || height <= this.maxHeight);
    }

    private static List<String> strings(JsonObject object, String key) {
        if (!object.has(key)) {
            return List.of();
        }
        List<String> values = new ArrayList<>();
        for (JsonElement element : object.getAsJsonArray(key)) {
            values.add(element.getAsString());
        }
        return List.copyOf(values);
    }

    private static JsonObject counts(Map<String, Long> values) {
        JsonObject result = new JsonObject();
        values.forEach(result::addProperty);
        return result;
    }

    private static JsonObject integerCounts(Map<Integer, Long> values) {
        JsonObject result = new JsonObject();
        values.forEach((key, value) -> result.addProperty(Integer.toString(key), value));
        return result;
    }
}
