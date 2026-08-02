package org.squinchmods.investigate.rtf;

import java.awt.image.BufferedImage;
import java.io.BufferedWriter;
import java.io.Reader;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileSystems;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.concurrent.TimeUnit;

import javax.imageio.ImageIO;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.serialization.JsonOps;

import net.minecraft.SharedConstants;
import net.minecraft.core.HolderGetter;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.RegistrySetBuilder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.Bootstrap;
import raccoonman.reterraforged.concurrent.ThreadPools;
import raccoonman.reterraforged.concurrent.cache.Cache;
import raccoonman.reterraforged.concurrent.cache.CacheManager;
import raccoonman.reterraforged.data.worldgen.preset.PresetNoiseData;
import raccoonman.reterraforged.data.worldgen.preset.settings.Preset;
import raccoonman.reterraforged.registries.RTFRegistries;
import raccoonman.reterraforged.world.worldgen.GeneratorContext;
import raccoonman.reterraforged.world.worldgen.cell.Cell;
import raccoonman.reterraforged.world.worldgen.densityfunction.tile.Tile;
import raccoonman.reterraforged.world.worldgen.noise.module.Noise;

public final class CellScanMain {
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();

    private CellScanMain() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            throw new IllegalArgumentException("expected request and result paths");
        }
        Path requestPath = Path.of(args[0]).toAbsolutePath().normalize();
        Path resultPath = Path.of(args[1]).toAbsolutePath().normalize();
        JsonObject request;
        try (Reader reader = Files.newBufferedReader(requestPath, StandardCharsets.UTF_8)) {
            request = JsonParser.parseReader(reader).getAsJsonObject();
        }

        long started = System.nanoTime();
        JsonObject output = new JsonObject();
        try {
            SharedConstants.tryDetectVersion();
            Bootstrap.bootStrap();
            long bootstrapped = System.nanoTime();

            Path presetPath = Path.of(request.get("preset_path").getAsString());
            Preset preset;
            try (Reader reader = Files.newBufferedReader(presetPath, StandardCharsets.UTF_8)) {
                preset = Preset.DIRECT_CODEC.parse(JsonOps.INSTANCE, JsonParser.parseReader(reader))
                    .getOrThrow(message -> new IllegalArgumentException("invalid RTF preset: " + message));
            }

            RegistryAccess builtIns = RegistryAccess.fromRegistryOfRegistries(BuiltInRegistries.REGISTRY);
            HolderLookup.Provider provider = new RegistrySetBuilder()
                .add(RTFRegistries.NOISE, context -> PresetNoiseData.bootstrap(preset, context))
                .build(builtIns);
            HolderGetter<Noise> noises = provider.lookupOrThrow(RTFRegistries.NOISE);
            long registryReady = System.nanoTime();

            int seed = request.get("seed").getAsInt();
            int tileSize = request.get("tile_size").getAsInt();
            int batchCount = request.get("batch_count").getAsInt();
            GeneratorContext previewContext = GeneratorContext.makeUncached(
                preset, noises, seed, tileSize, 0, batchCount
            );
            int runtimeBorder = Math.min(
                2, Math.max(1, preset.filters().erosion.dropletLifetime / 16)
            );
            String mode = request.get("mode").getAsString();
            boolean needsRuntimeTile = mode.equals("tile")
                || (mode.equals("adaptive") && request.get("exact_tile").getAsBoolean());
            GeneratorContext runtimeTileContext = needsRuntimeTile
                ? GeneratorContext.makeUncached(
                    preset, noises, seed, tileSize, runtimeBorder, batchCount
                )
                : previewContext;
            GeneratorContext context = mode.equals("tile") ? runtimeTileContext : previewContext;
            long contextReady = System.nanoTime();

            boolean retainGrid = request.get("grid_json").getAsBoolean()
                || request.get("grid_csv").getAsBoolean()
                || request.has("heatmap_field");
            ScanRun cold = scan(context, runtimeTileContext, request, retainGrid);
            long coldComplete = System.nanoTime();
            ScanRun warm = scan(context, runtimeTileContext, request, false);
            long warmComplete = System.nanoTime();
            String coldJson = GSON.toJson(cold.summary());
            String warmJson = GSON.toJson(warm.summary());
            if (!coldJson.equals(warmJson)) {
                throw new IllegalStateException("identical cold/warm scans produced different summaries");
            }

            JsonArray artifacts = writeOptionalArtifacts(request, cold);
            output.addProperty("authority", authority(request.get("mode").getAsString()));
            output.addProperty("mode", request.get("mode").getAsString());
            output.addProperty("preview_tile_border", 0);
            output.addProperty("runtime_tile_border", runtimeBorder);
            output.addProperty("minecraft_version", SharedConstants.getCurrentVersion().getName());
            output.addProperty("seed", seed);
            output.addProperty("deterministic_sha256", sha256(coldJson));
            output.addProperty("cold_warm_equal", true);
            output.add("scan", cold.summary());
            output.add("artifacts", artifacts);
            output.add("classpath", classpath());
            JsonObject timings = new JsonObject();
            timings.addProperty("bootstrap_ms", millis(started, bootstrapped));
            timings.addProperty("registry_ms", millis(bootstrapped, registryReady));
            timings.addProperty("context_ms", millis(registryReady, contextReady));
            timings.addProperty("cold_scan_ms", millis(contextReady, coldComplete));
            timings.addProperty("warm_scan_ms", millis(coldComplete, warmComplete));
            timings.addProperty("cold_total_ms", millis(started, coldComplete));
            timings.addProperty("total_ms", millis(started, warmComplete));
            output.add("timings", timings);
        } finally {
            CacheManager.clear();
            Cache.SCHEDULER.shutdown();
            ThreadPools.WORLD_GEN.shutdown();
            Cache.SCHEDULER.awaitTermination(30, TimeUnit.SECONDS);
            ThreadPools.WORLD_GEN.awaitTermination(30, TimeUnit.SECONDS);
        }

        Files.createDirectories(resultPath.getParent());
        try (Writer writer = Files.newBufferedWriter(resultPath, StandardCharsets.UTF_8)) {
            GSON.toJson(output, writer);
            writer.write("\n");
        }
    }

    private static ScanRun scan(
        GeneratorContext context, GeneratorContext runtimeTileContext,
        JsonObject request, boolean retainGrid
    ) {
        ScanAccumulator accumulator = new ScanAccumulator(context.levels, request, retainGrid);
        String mode = request.get("mode").getAsString();
        int step = request.get("sample_step").getAsInt();
        if (mode.equals("adaptive")) {
            return scanAdaptive(context, runtimeTileContext, request, retainGrid);
        } else if (mode.equals("preview")) {
            scanPreview(context, request, accumulator, step);
        } else if (mode.equals("tile")) {
            scanTiles(context, request, accumulator, step);
        } else {
            throw new IllegalArgumentException("unknown scan mode: " + mode);
        }
        return new ScanRun(accumulator.finish(), accumulator.grid());
    }

    private static ScanRun scanAdaptive(
        GeneratorContext context, GeneratorContext runtimeTileContext,
        JsonObject request, boolean retainGrid
    ) {
        ScanAccumulator coarse = new ScanAccumulator(context.levels, request, retainGrid);
        scanPreview(context, request, coarse, request.get("sample_step").getAsInt());
        JsonObject coarseSummary = coarse.finish();
        JsonArray candidates = coarseSummary.getAsJsonArray("top_candidates");
        JsonArray refinements = new JsonArray();
        int count = Math.min(request.get("refine_count").getAsInt(), candidates.size());
        double refineZoom = request.get("refine_zoom").getAsDouble();
        int width = (1 << request.get("tile_size").getAsInt()) << 4;
        for (int index = 0; index < count; index++) {
            JsonObject candidate = candidates.get(index).getAsJsonObject();
            JsonObject refinedRequest = request.deepCopy();
            double centerX = candidate.get("x").getAsDouble();
            double centerZ = candidate.get("z").getAsDouble();
            refinedRequest.addProperty("center_x", centerX);
            refinedRequest.addProperty("center_z", centerZ);
            refinedRequest.addProperty("zoom", refineZoom);
            refinedRequest.addProperty("sample_step", request.get("refine_step").getAsInt());
            double half = width * refineZoom / 2.0;
            JsonArray refinedBounds = new JsonArray();
            refinedBounds.add(centerX - half);
            refinedBounds.add(centerZ - half);
            refinedBounds.add(centerX + half);
            refinedBounds.add(centerZ + half);
            refinedRequest.add("bounds", refinedBounds);
            ScanAccumulator refined = new ScanAccumulator(context.levels, refinedRequest, false);
            scanPreview(context, refinedRequest, refined, refinedRequest.get("sample_step").getAsInt());
            JsonObject item = new JsonObject();
            item.add("coarse_candidate", candidate.deepCopy());
            JsonObject refinedSummary = refined.finish();
            item.add("scan", refinedSummary);
            if (request.get("exact_tile").getAsBoolean()
                && refinedSummary.getAsJsonArray("top_candidates").size() > 0) {
                JsonObject best = refinedSummary.getAsJsonArray("top_candidates")
                    .get(0).getAsJsonObject();
                item.add("exact_tile", exactTile(runtimeTileContext, request, best));
            }
            refinements.add(item);
        }
        JsonObject adaptive = new JsonObject();
        adaptive.addProperty("coarse_candidates", candidates.size());
        adaptive.addProperty("refined_regions", refinements.size());
        adaptive.addProperty("refine_zoom", refineZoom);
        adaptive.add("refinements", refinements);
        coarseSummary.add("adaptive", adaptive);
        return new ScanRun(coarseSummary, coarse.grid());
    }

    private static JsonObject exactTile(
        GeneratorContext context, JsonObject request, JsonObject candidate
    ) {
        int blockX = (int) Math.floor(candidate.get("x").getAsDouble());
        int blockZ = (int) Math.floor(candidate.get("z").getAsDouble());
        int blockWidth = (1 << request.get("tile_size").getAsInt()) << 4;
        int tileX = Math.floorDiv(blockX, blockWidth);
        int tileZ = Math.floorDiv(blockZ, blockWidth);
        try (Tile tile = context.generator.generate(tileX, tileZ).join()) {
            Cell cell = tile.lookup(blockX, blockZ);
            ScanAccumulator exact = new ScanAccumulator(context.levels, request, false);
            exact.accept(cell, blockX, blockZ, 0, 0);
            JsonObject result = exact.finish();
            result.addProperty("tile_x", tileX);
            result.addProperty("tile_z", tileZ);
            result.addProperty("block_x", blockX);
            result.addProperty("block_z", blockZ);
            return result;
        }
    }

    private static void scanPreview(
        GeneratorContext context, JsonObject request, ScanAccumulator accumulator, int step
    ) {
        float centerX = request.get("center_x").getAsFloat();
        float centerZ = request.get("center_z").getAsFloat();
        float zoom = request.get("zoom").getAsFloat();
        Bounds bounds = Bounds.from(request);
        try (Tile tile = context.generator.generateZoomed(centerX, centerZ, zoom, false).join()) {
            int width = tile.getBlockSize().size();
            int border = tile.getBlockSize().border();
            double translateX = centerX - width * zoom / 2.0;
            double translateZ = centerZ - width * zoom / 2.0;
            for (int bz = 0; bz < width; bz += step) {
                for (int bx = 0; bx < width; bx += step) {
                    double x = bx * zoom + translateX;
                    double z = bz * zoom + translateZ;
                    if (bounds.includes(x, z)) {
                        Cell cell = tile.getCellRaw(border + bx, border + bz);
                        accumulator.accept(cell, x, z, bx / step, bz / step);
                    }
                }
            }
        }
    }

    private static void scanTiles(
        GeneratorContext context, JsonObject request, ScanAccumulator accumulator, int step
    ) {
        Bounds bounds = Bounds.from(request);
        for (JsonElement element : request.getAsJsonArray("tiles")) {
            JsonObject coordinate = element.getAsJsonObject();
            int tileX = coordinate.get("x").getAsInt();
            int tileZ = coordinate.get("z").getAsInt();
            try (Tile tile = context.generator.generate(tileX, tileZ).join()) {
                int width = tile.getBlockSize().size();
                int border = tile.getBlockSize().border();
                for (int bz = 0; bz < width; bz += step) {
                    for (int bx = 0; bx < width; bx += step) {
                        int x = tile.getBlockX() + bx;
                        int z = tile.getBlockZ() + bz;
                        if (bounds.includes(x, z)) {
                            Cell cell = tile.getCellRaw(border + bx, border + bz);
                            int pixelX = (int) Math.floor((x - bounds.minX()) / step);
                            int pixelZ = (int) Math.floor((z - bounds.minZ()) / step);
                            accumulator.accept(cell, x, z, pixelX, pixelZ);
                        }
                    }
                }
            }
        }
    }

    private static JsonArray writeOptionalArtifacts(JsonObject request, ScanRun run) throws Exception {
        JsonArray artifacts = new JsonArray();
        List<JsonObject> grid = run.grid();
        if (request.get("grid_json").getAsBoolean()) {
            Path path = Path.of(request.get("grid_json_path").getAsString());
            Files.createDirectories(path.getParent());
            try (Writer writer = Files.newBufferedWriter(path, StandardCharsets.UTF_8)) {
                GSON.toJson(grid, writer);
                writer.write("\n");
            }
            artifacts.add(path.toString());
        }
        if (request.get("grid_csv").getAsBoolean()) {
            Path path = Path.of(request.get("grid_csv_path").getAsString());
            Files.createDirectories(path.getParent());
            writeCsv(path, request.getAsJsonArray("fields"), grid);
            artifacts.add(path.toString());
        }
        if (request.has("heatmap_field")) {
            Path path = Path.of(request.get("heatmap_path").getAsString());
            Files.createDirectories(path.getParent());
            writeHeatmap(path, request.get("heatmap_field").getAsString(), grid);
            artifacts.add(path.toString());
        }
        return artifacts;
    }

    private static void writeCsv(Path path, JsonArray fields, List<JsonObject> grid) throws Exception {
        try (BufferedWriter writer = Files.newBufferedWriter(path, StandardCharsets.UTF_8)) {
            writer.write("x,z");
            for (JsonElement field : fields) {
                writer.write("," + field.getAsString());
            }
            writer.newLine();
            for (JsonObject sample : grid) {
                writer.write(sample.get("x").getAsString() + "," + sample.get("z").getAsString());
                for (JsonElement field : fields) {
                    String value = sample.get(field.getAsString()).getAsString().replace("\"", "\"\"");
                    writer.write(",\"" + value + "\"");
                }
                writer.newLine();
            }
        }
    }

    private static void writeHeatmap(Path path, String field, List<JsonObject> grid) throws Exception {
        if (grid.isEmpty() || !grid.getFirst().get(field).isJsonPrimitive()
            || !grid.getFirst().getAsJsonPrimitive(field).isNumber()) {
            throw new IllegalArgumentException("heatmap field must be a sampled numeric field: " + field);
        }
        int width = grid.stream().mapToInt(item -> item.get("pixel_x").getAsInt()).max().orElse(0) + 1;
        int height = grid.stream().mapToInt(item -> item.get("pixel_z").getAsInt()).max().orElse(0) + 1;
        double min = grid.stream().mapToDouble(item -> item.get(field).getAsDouble()).min().orElse(0);
        double max = grid.stream().mapToDouble(item -> item.get(field).getAsDouble()).max().orElse(min);
        BufferedImage image = new BufferedImage(width, height, BufferedImage.TYPE_INT_ARGB);
        for (JsonObject sample : grid) {
            double value = sample.get(field).getAsDouble();
            double alpha = max == min ? 0.5 : (value - min) / (max - min);
            int red = (int) Math.round(255 * alpha);
            int blue = 255 - red;
            image.setRGB(
                sample.get("pixel_x").getAsInt(), sample.get("pixel_z").getAsInt(),
                0xFF000000 | red << 16 | blue
            );
        }
        ImageIO.write(image, "PNG", path.toFile());
    }

    private static String authority(String mode) {
        return mode.equals("tile") ? "rtf-horizontal-cell-model" : "prediction";
    }

    private static JsonArray classpath() {
        JsonArray result = new JsonArray();
        String separator = FileSystems.getDefault().getSeparator().equals("\\") ? ";" : ":";
        for (String entry : System.getProperty("java.class.path").split(separator)) {
            result.add(Path.of(entry).toAbsolutePath().normalize().toString());
        }
        return result;
    }

    private static String sha256(String value) throws Exception {
        return HexFormat.of().formatHex(
            MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))
        );
    }

    private static double millis(long start, long end) {
        return (end - start) / 1_000_000.0;
    }

    private record ScanRun(JsonObject summary, List<JsonObject> grid) {
    }

    private record Bounds(double minX, double minZ, double maxX, double maxZ) {
        static Bounds from(JsonObject request) {
            JsonArray bounds = request.getAsJsonArray("bounds");
            return new Bounds(
                bounds.get(0).getAsDouble(), bounds.get(1).getAsDouble(),
                bounds.get(2).getAsDouble(), bounds.get(3).getAsDouble()
            );
        }

        boolean includes(double x, double z) {
            return x >= this.minX && x <= this.maxX && z >= this.minZ && z <= this.maxZ;
        }
    }
}
