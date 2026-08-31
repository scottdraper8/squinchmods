package org.squinchmods.investigate.rtf;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import net.minecraft.core.Holder;
import net.minecraft.core.QuartPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Climate;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import raccoonman.reterraforged.world.worldgen.biome.UndergroundBiomeSurfaceProtection;
import raccoonman.reterraforged.world.worldgen.biome.UndergroundBiomeTags;

/** Broad, direct biome-source census which does not confuse biome labels with cave air. */
public final class RtfUndergroundBiomeDistributionProbePack implements ProbePack {
    private static final Set<String> DEFAULT_CAVE_BIOMES = Set.of(
        "minecraft:dripstone_caves",
        "minecraft:lush_caves",
        "minecraft:deep_dark"
    );

    @Override
    public void register() {
        ProbeRegistry.register(
            "squinch:rtf-underground-biome-distribution",
            "1",
            Distribution::new
        );
    }

    private static final class Distribution implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final int minX;
        private final int maxX;
        private final int minZ;
        private final int maxZ;
        private final int horizontalStep;
        private final int minY;
        private final int maxY;
        private final int verticalStep;
        private final Set<String> caveBiomes;
        private final List<Band> bands;
        private final boolean validateSurfaceProtection;
        private final boolean expectZeroCaveBiomes;
        private final boolean validateFinishedChunkParity;
        private final boolean reportVerticalRuns;

        private Distribution(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "rtf-underground-biome-distribution");
            this.minX = integer(config, "sample_min_x", -32768);
            this.maxX = integer(config, "sample_max_x", 32768);
            this.minZ = integer(config, "sample_min_z", -32768);
            this.maxZ = integer(config, "sample_max_z", 32768);
            this.horizontalStep = integer(config, "horizontal_step_blocks", 512);
            this.minY = integer(config, "sample_min_y", -64);
            this.maxY = integer(config, "sample_max_y", 63);
            this.verticalStep = integer(config, "vertical_step_blocks", 4);
            this.caveBiomes = caveBiomes(config);
            this.bands = bands(config);
            this.validateSurfaceProtection = bool(config, "validate_surface_protection", false);
            this.expectZeroCaveBiomes = bool(config, "expect_zero_cave_biomes", false);
            this.validateFinishedChunkParity = bool(config, "validate_finished_chunk_parity", true);
            this.reportVerticalRuns = bool(config, "report_vertical_runs", false);

            if (this.minX > this.maxX || this.minZ > this.maxZ || this.minY > this.maxY) {
                throw new IllegalArgumentException("sample minima must not exceed maxima");
            }
            if (this.horizontalStep < 4 || this.horizontalStep % 4 != 0
                || this.verticalStep < 4 || this.verticalStep % 4 != 0) {
                throw new IllegalArgumentException("sample steps must be positive multiples of four blocks");
            }
            long xSamples = ((long) this.maxX - this.minX) / this.horizontalStep + 1L;
            long zSamples = ((long) this.maxZ - this.minZ) / this.horizontalStep + 1L;
            long verticalSamples = ((long) this.maxY - this.minY) / this.verticalStep + 1L;
            long total = Math.multiplyExact(Math.multiplyExact(xSamples, zSamples), verticalSamples);
            if (total > 5_000_000L) {
                throw new IllegalArgumentException("direct biome census exceeds the 5M sample limit: " + total);
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(level);
            if (snapshot == null) {
                return null;
            }
            if (!snapshot.complete()) {
                return this.selection.result(snapshot, new JsonObject());
            }

            Climate.Sampler sampler = level.getChunkSource().randomState().sampler();
            BiomeSource biomeSource = level.getChunkSource().getGenerator().getBiomeSource();
            Counts all = new Counts();
            Map<String, Counts> byBand = new LinkedHashMap<>();
            List<ColumnTrace> directTraces = new ArrayList<>();
            this.bands.forEach(band -> byBand.put(band.id(), new Counts()));

            for (int blockX = this.minX; blockX <= this.maxX; blockX += this.horizontalStep) {
                int quartX = QuartPos.fromBlock(blockX);
                for (int blockZ = this.minZ; blockZ <= this.maxZ; blockZ += this.horizontalStep) {
                    int quartZ = QuartPos.fromBlock(blockZ);
                    ColumnTrace trace = this.reportVerticalRuns ? new ColumnTrace(blockX, blockZ) : null;
                    for (int blockY = this.minY; blockY <= this.maxY; blockY += this.verticalStep) {
                        int quartY = QuartPos.fromBlock(blockY);
                        Holder<Biome> selected = biomeSource.getNoiseBiome(quartX, quartY, quartZ, sampler);
                        String biome = MinecraftProbeHelpers.biomeId(selected);
                        boolean cave = this.caveBiomes.contains(biome);
                        all.add(biome, cave);
                        if (trace != null) {
                            trace.add(blockY, biome);
                        }
                        for (Band band : this.bands) {
                            if (band.includes(blockY)) {
                                byBand.get(band.id()).add(biome, cave);
                            }
                        }
                    }
                    if (trace != null) {
                        trace.finish(this.maxY);
                        directTraces.add(trace);
                    }
                }
            }

            long paritySamples = 0L;
            long parityMismatches = 0L;
            long recognizedCaveCells = 0L;
            long hardShellViolations = 0L;
            JsonArray parityExamples = new JsonArray();
            JsonArray hardShellExamples = new JsonArray();
            List<ColumnTrace> storedTraces = new ArrayList<>();
            for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                int chunkQuartX = ready.coordinate().x() * 4;
                int chunkQuartZ = ready.coordinate().z() * 4;
                for (int localQuartX = 0; localQuartX < 4; localQuartX++) {
                    int quartX = chunkQuartX + localQuartX;
                    for (int localQuartZ = 0; localQuartZ < 4; localQuartZ++) {
                        int quartZ = chunkQuartZ + localQuartZ;
                        ColumnTrace storedTrace = this.reportVerticalRuns
                            ? new ColumnTrace(QuartPos.toBlock(quartX) + 2, QuartPos.toBlock(quartZ) + 2)
                            : null;
                        for (int blockY = this.minY; blockY <= this.maxY; blockY += this.verticalStep) {
                            int quartY = QuartPos.fromBlock(blockY);
                            Holder<Biome> directHolder = biomeSource.getNoiseBiome(quartX, quartY, quartZ, sampler);
                            Holder<Biome> storedHolder = ready.chunk().getNoiseBiome(quartX, quartY, quartZ);
                            String direct = MinecraftProbeHelpers.biomeId(directHolder);
                            String stored = MinecraftProbeHelpers.biomeId(storedHolder);
                            if (storedTrace != null) {
                                storedTrace.add(blockY, stored);
                            }
                            paritySamples++;
                            if (!direct.equals(stored)) {
                                parityMismatches++;
                                if (parityExamples.size() < 32) {
                                    JsonObject example = new JsonObject();
                                    example.addProperty("x", QuartPos.toBlock(quartX) + 2);
                                    example.addProperty("y", blockY);
                                    example.addProperty("z", QuartPos.toBlock(quartZ) + 2);
                                    example.addProperty("direct_biome_id", direct);
                                    example.addProperty("stored_biome_id", stored);
                                    parityExamples.add(example);
                                }
                            }
                            if (UndergroundBiomeTags.isCave(storedHolder) || this.caveBiomes.contains(stored)) {
                                recognizedCaveCells++;
                                if (this.validateSurfaceProtection) {
                                    Climate.TargetPoint target = sampler.sample(quartX, quartY, quartZ);
                                    float factor = UndergroundBiomeSurfaceProtection.coverageFactor(
                                        sampler,
                                        target,
                                        quartX,
                                        quartY,
                                        quartZ
                                    );
                                    if (factor <= 0.0F) {
                                        hardShellViolations++;
                                        if (hardShellExamples.size() < 32) {
                                            JsonObject example = new JsonObject();
                                            example.addProperty("x", QuartPos.toBlock(quartX) + 2);
                                            example.addProperty("y", blockY);
                                            example.addProperty("z", QuartPos.toBlock(quartZ) + 2);
                                            example.addProperty("biome_id", stored);
                                            example.addProperty("surface_coverage_factor", factor);
                                            hardShellExamples.add(example);
                                        }
                                    }
                                }
                            }
                        }
                        if (storedTrace != null) {
                            storedTrace.finish(this.maxY);
                            storedTraces.add(storedTrace);
                        }
                    }
                }
            }

            JsonObject data = new JsonObject();
            data.addProperty("authority", "direct-biome-source-query");
            data.addProperty("measurement", "biome-labels-not-cave-air");
            JsonObject domain = new JsonObject();
            domain.addProperty("min_x", this.minX);
            domain.addProperty("max_x", this.maxX);
            domain.addProperty("min_z", this.minZ);
            domain.addProperty("max_z", this.maxZ);
            domain.addProperty("horizontal_step_blocks", this.horizontalStep);
            domain.addProperty("min_y", this.minY);
            domain.addProperty("max_y", this.maxY);
            domain.addProperty("vertical_step_blocks", this.verticalStep);
            data.add("domain", domain);
            JsonArray caveIds = new JsonArray();
            this.caveBiomes.forEach(caveIds::add);
            data.add("cave_biomes", caveIds);
            data.add("all", all.toJson());
            JsonObject bands = new JsonObject();
            byBand.forEach((id, counts) -> bands.add(id, counts.toJson()));
            data.add("bands", bands);
            if (this.reportVerticalRuns) {
                JsonObject verticalRuns = new JsonObject();
                verticalRuns.add("direct", verticalRunSummary(directTraces));
                verticalRuns.add("stored", verticalRunSummary(storedTraces));
                data.add("vertical_runs", verticalRuns);
            }
            JsonObject parity = new JsonObject();
            parity.addProperty("authority", "server-biome-source-vs-finished-chunk-quart-palette");
            parity.addProperty("enforced", this.validateFinishedChunkParity);
            parity.addProperty("sampled_cells", paritySamples);
            parity.addProperty("mismatch_count", parityMismatches);
            parity.add("mismatch_examples", parityExamples);
            data.add("finished_chunk_parity", parity);
            JsonObject surfaceProtection = new JsonObject();
            surfaceProtection.addProperty("enabled", this.validateSurfaceProtection);
            surfaceProtection.addProperty(
                "classification",
                "reterraforged-common-cave-biome-tags-plus-configured-validation-ids"
            );
            surfaceProtection.addProperty("recognized_cave_cells", recognizedCaveCells);
            surfaceProtection.addProperty("hard_shell_violations", hardShellViolations);
            surfaceProtection.add("hard_shell_violation_examples", hardShellExamples);
            surfaceProtection.addProperty("expected_zero_cave_biomes", this.expectZeroCaveBiomes);
            data.add("surface_protection", surfaceProtection);
            data.addProperty("requested_chunks", snapshot.requested());
            data.addProperty("ready_chunks", snapshot.ready().size());
            data.addProperty("poll_ticks", snapshot.pollTicks());
            data.add("not_ready_examples", snapshot.notReadyExamples().deepCopy());
            return ProbeResult.complete(
                (!this.validateFinishedChunkParity || parityMismatches == 0L)
                    && hardShellViolations == 0L
                    && (!this.expectZeroCaveBiomes || recognizedCaveCells == 0L)
                    ? TerminalState.PASS
                    : TerminalState.FAIL,
                ProbePhase.FINISHED_CHUNK,
                data,
                snapshot.ready().size()
            );
        }
    }

    private static int integer(JsonObject config, String key, int fallback) {
        return config.has(key) ? config.get(key).getAsInt() : fallback;
    }

    private static boolean bool(JsonObject config, String key, boolean fallback) {
        return config.has(key) ? config.get(key).getAsBoolean() : fallback;
    }

    private static Set<String> caveBiomes(JsonObject config) {
        if (!config.has("cave_biomes")) {
            return DEFAULT_CAVE_BIOMES;
        }
        Set<String> result = new LinkedHashSet<>();
        for (JsonElement element : config.getAsJsonArray("cave_biomes")) {
            String id = element.getAsString();
            if (id.isBlank()) {
                throw new IllegalArgumentException("cave biome IDs must not be blank");
            }
            result.add(id);
        }
        return Set.copyOf(result);
    }

    private static List<Band> bands(JsonObject config) {
        if (!config.has("bands")) {
            return List.of();
        }
        return config.getAsJsonArray("bands").asList().stream().map(element -> {
            JsonObject value = element.getAsJsonObject();
            Band band = new Band(
                value.get("id").getAsString(),
                value.get("min_y").getAsInt(),
                value.get("max_y").getAsInt()
            );
            if (band.id().isBlank() || band.minY() > band.maxY()) {
                throw new IllegalArgumentException("band id must be nonempty and min_y <= max_y");
            }
            return band;
        }).toList();
    }

    private record Band(String id, int minY, int maxY) {
        private boolean includes(int y) {
            return y >= this.minY && y <= this.maxY;
        }
    }

    private static JsonObject verticalRunSummary(List<ColumnTrace> traces) {
        JsonObject result = new JsonObject();
        result.addProperty("columns", traces.size());
        result.addProperty("transitions", traces.stream().mapToInt(ColumnTrace::transitions).sum());
        result.addProperty(
            "columns_with_transitions",
            traces.stream().filter(trace -> trace.transitions() > 0).count()
        );
        JsonArray examples = new JsonArray();
        traces.stream()
            .filter(trace -> trace.transitions() > 0)
            .sorted(Comparator.comparingInt(ColumnTrace::transitions).reversed())
            .limit(16)
            .forEach(trace -> examples.add(trace.toJson()));
        result.add("most_segmented_columns", examples);
        JsonArray samples = new JsonArray();
        traces.stream().limit(256).forEach(trace -> samples.add(trace.toJson()));
        result.add("sampled_columns", samples);
        return result;
    }

    private static final class ColumnTrace {
        private final int x;
        private final int z;
        private final List<VerticalRun> runs = new ArrayList<>();
        private int runStartY;
        private int lastY;
        private String biome;

        private ColumnTrace(int x, int z) {
            this.x = x;
            this.z = z;
        }

        private void add(int y, String nextBiome) {
            if (this.biome == null) {
                this.runStartY = y;
                this.lastY = y;
                this.biome = nextBiome;
            } else if (!this.biome.equals(nextBiome)) {
                this.runs.add(new VerticalRun(this.runStartY, this.lastY, this.biome));
                this.runStartY = y;
                this.biome = nextBiome;
            }
            this.lastY = y;
        }

        private void finish(int ignoredMaxY) {
            if (this.biome != null) {
                this.runs.add(new VerticalRun(this.runStartY, this.lastY, this.biome));
            }
        }

        private int transitions() {
            return Math.max(0, this.runs.size() - 1);
        }

        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("x", this.x);
            result.addProperty("z", this.z);
            result.addProperty("transitions", this.transitions());
            JsonArray runValues = new JsonArray();
            this.runs.forEach(run -> runValues.add(run.toJson()));
            result.add("runs", runValues);
            return result;
        }
    }

    private record VerticalRun(int minY, int maxY, String biome) {
        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("min_y", this.minY);
            result.addProperty("max_y", this.maxY);
            result.addProperty("biome", this.biome);
            return result;
        }
    }

    private static final class Counts {
        private final Map<String, Long> biomes = new LinkedHashMap<>();
        private long total;
        private long cave;

        private void add(String biome, boolean cave) {
            this.biomes.merge(biome, 1L, Long::sum);
            this.total++;
            this.cave += cave ? 1L : 0L;
        }

        private JsonObject toJson() {
            JsonObject result = new JsonObject();
            result.addProperty("sampled_cells", this.total);
            result.addProperty("cave_cells", this.cave);
            result.addProperty("background_cells", this.total - this.cave);
            result.addProperty("cave_share", this.total == 0L ? 0.0D : (double) this.cave / this.total);
            JsonObject biomeCounts = new JsonObject();
            this.biomes.forEach(biomeCounts::addProperty);
            result.add("biomes", biomeCounts);
            return result;
        }
    }
}
