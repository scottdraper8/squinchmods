package org.squinchmods.investigate.rtf;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;

import raccoonman.reterraforged.world.worldgen.GeneratorContext;
import raccoonman.reterraforged.world.worldgen.RTFRandomState;
import raccoonman.reterraforged.world.worldgen.cell.Cell;
import raccoonman.reterraforged.world.worldgen.densityfunction.tile.Tile;

public final class RtfCellCacheProbePack implements ProbePack {
    private static final List<String> DEFAULT_FIELDS = List.of(
        "height", "height_blocks", "terrain", "terrain_category", "biome_type",
        "continent_edge", "continent_distance", "river_mask", "river_zone",
        "temperature", "moisture", "erosion", "weirdness", "water_table",
        "terrain_region_id", "biome_region_id"
    );
    private static final Set<String> FIELDS = Set.of(
        "height", "height_blocks", "terrain", "terrain_category", "biome_type",
        "continent_edge", "continent_distance", "river_mask", "river_zone",
        "temperature", "moisture", "erosion", "weirdness", "water_table",
        "terrain_region_id", "biome_region_id"
    );

    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-tile-cache", "1", request -> server -> {
            JsonObject config = request.config();
            if (!config.has("coordinates") || !config.get("coordinates").isJsonArray()) {
                throw new IllegalArgumentException("rtf-tile-cache requires coordinates");
            }
            JsonArray coordinates = config.getAsJsonArray("coordinates");
            if (coordinates.size() < 1 || coordinates.size() > 1024) {
                throw new IllegalArgumentException("coordinates must contain 1..1024 entries");
            }
            List<String> fields = fields(config);
            Object randomState = server.overworld().getChunkSource().randomState();
            if (!(randomState instanceof RTFRandomState rtfRandomState)) {
                return ProbeResult.partial(
                    ProbePhase.GENERATION, new JsonObject(), 0, coordinates.size(),
                    "overworld-random-state-is-not-rtf"
                );
            }
            GeneratorContext context = rtfRandomState.generatorContext();
            if (context == null || context.cache == null) {
                return ProbeResult.partial(
                    ProbePhase.GENERATION, new JsonObject(), 0, coordinates.size(),
                    "rtf-generator-context-or-tile-cache-unavailable"
                );
            }
            JsonArray samples = new JsonArray();
            long cacheStarted = System.nanoTime();
            for (int index = 0; index < coordinates.size(); index++) {
                JsonArray coordinate = coordinates.get(index).getAsJsonArray();
                if (coordinate.size() != 2) {
                    throw new IllegalArgumentException("each coordinate must contain block x,z");
                }
                int blockX = coordinate.get(0).getAsInt();
                int blockZ = coordinate.get(1).getAsInt();
                int chunkX = Math.floorDiv(blockX, 16);
                int chunkZ = Math.floorDiv(blockZ, 16);
                Tile tile = context.cache.provideAtChunk(chunkX, chunkZ);
                Cell cell = tile.getChunkReader(chunkX, chunkZ).getCell(blockX, blockZ);
                samples.add(sample(context, cell, blockX, blockZ, fields));
            }
            double cacheAccessMillis = (System.nanoTime() - cacheStarted) / 1_000_000.0D;
            JsonObject data = new JsonObject();
            data.addProperty("authority", "rtf-horizontal-cell-model");
            data.addProperty("server_thread", Thread.currentThread().getName());
            data.addProperty("cache_access_ms", cacheAccessMillis);
            data.add("fields", strings(fields));
            data.add("samples", samples);
            TerminalState state = TerminalState.PASS;
            if (config.has("expected")) {
                JsonArray expected = config.getAsJsonArray("expected");
                if (expected.size() != samples.size()) {
                    throw new IllegalArgumentException("expected and coordinates must have equal lengths");
                }
                double tolerance = config.has("tolerance")
                    ? config.get("tolerance").getAsDouble()
                    : 1.0E-6D;
                if (tolerance < 0.0D || !Double.isFinite(tolerance)) {
                    throw new IllegalArgumentException("tolerance must be finite and nonnegative");
                }
                JsonObject comparison = compare(expected, samples, fields, tolerance);
                data.add("comparison", comparison);
                if (comparison.get("mismatch_count").getAsInt() > 0) {
                    state = TerminalState.FAIL;
                }
            }
            return ProbeResult.complete(
                state, ProbePhase.GENERATION, data, coordinates.size()
            );
        });
    }

    private static List<String> fields(JsonObject config) {
        if (!config.has("fields")) {
            return DEFAULT_FIELDS;
        }
        List<String> result = new ArrayList<>();
        for (var element : config.getAsJsonArray("fields")) {
            String field = element.getAsString();
            if (!FIELDS.contains(field)) {
                throw new IllegalArgumentException("unknown RTF cell field: " + field);
            }
            result.add(field);
        }
        return result;
    }

    private static JsonObject sample(
        GeneratorContext context, Cell cell, int blockX, int blockZ, List<String> fields
    ) {
        JsonObject result = new JsonObject();
        result.addProperty("x", blockX);
        result.addProperty("z", blockZ);
        for (String field : fields) {
            switch (field) {
                case "height" -> result.addProperty(field, cell.height);
                case "height_blocks" -> result.addProperty(field, context.levels.scale(cell.height));
                case "terrain" -> result.addProperty(field, cell.terrain.getName());
                case "terrain_category" -> result.addProperty(field, cell.terrain.getCategory().name());
                case "biome_type" -> result.addProperty(field, cell.biome.name());
                case "continent_edge" -> result.addProperty(field, cell.continentEdge);
                case "continent_distance" -> result.addProperty(field, cell.continentDistance);
                case "river_mask" -> result.addProperty(field, cell.riverMask);
                case "river_zone" -> result.addProperty(field, cell.riverZone.name());
                case "temperature" -> result.addProperty(field, cell.temperature);
                case "moisture" -> result.addProperty(field, cell.moisture);
                case "erosion" -> result.addProperty(field, cell.erosion);
                case "weirdness" -> result.addProperty(field, cell.weirdness);
                case "water_table" -> result.addProperty(field, cell.waterTable);
                case "terrain_region_id" -> result.addProperty(field, cell.terrainRegionId);
                case "biome_region_id" -> result.addProperty(field, cell.biomeRegionId);
                default -> throw new IllegalArgumentException("unknown RTF cell field: " + field);
            }
        }
        return result;
    }

    private static JsonArray strings(List<String> values) {
        JsonArray result = new JsonArray();
        values.forEach(result::add);
        return result;
    }

    private static JsonObject compare(
        JsonArray expected, JsonArray actual, List<String> fields, double tolerance
    ) {
        JsonArray mismatches = new JsonArray();
        int mismatchCount = 0;
        for (int index = 0; index < expected.size(); index++) {
            JsonObject expectedSample = expected.get(index).getAsJsonObject();
            JsonObject actualSample = actual.get(index).getAsJsonObject();
            int expectedX = expectedSample.get("x").getAsInt();
            int expectedZ = expectedSample.get("z").getAsInt();
            if (expectedX != actualSample.get("x").getAsInt()
                    || expectedZ != actualSample.get("z").getAsInt()) {
                throw new IllegalArgumentException("expected sample coordinates must match coordinates order");
            }
            for (String field : fields) {
                JsonElement wanted = expectedSample.get(field);
                JsonElement observed = actualSample.get(field);
                boolean matches = wanted != null && observed != null && valuesEqual(wanted, observed, tolerance);
                if (!matches) {
                    mismatchCount++;
                    if (mismatches.size() < 100) {
                        JsonObject mismatch = new JsonObject();
                        mismatch.addProperty("x", expectedX);
                        mismatch.addProperty("z", expectedZ);
                        mismatch.addProperty("field", field);
                        mismatch.add("expected", wanted == null ? null : wanted.deepCopy());
                        mismatch.add("actual", observed == null ? null : observed.deepCopy());
                        mismatches.add(mismatch);
                    }
                }
            }
        }
        JsonObject result = new JsonObject();
        result.addProperty("matched", mismatchCount == 0);
        result.addProperty("expected_samples", expected.size());
        result.addProperty("compared_fields", fields.size());
        result.addProperty("mismatch_count", mismatchCount);
        result.addProperty("tolerance", tolerance);
        result.add("mismatches", mismatches);
        return result;
    }

    private static boolean valuesEqual(JsonElement left, JsonElement right, double tolerance) {
        if (left.isJsonPrimitive() && right.isJsonPrimitive()
                && left.getAsJsonPrimitive().isNumber()
                && right.getAsJsonPrimitive().isNumber()) {
            return Math.abs(left.getAsDouble() - right.getAsDouble()) <= tolerance;
        }
        return left.equals(right);
    }
}
