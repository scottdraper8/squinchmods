package org.squinchmods.investigate.rtf;

import java.util.HashMap;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.HolderLookup;
import net.minecraft.core.Holder;
import net.minecraft.core.QuartPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
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

import raccoonman.reterraforged.data.worldgen.preset.settings.Preset;
import raccoonman.reterraforged.registries.RTFRegistries;
import raccoonman.reterraforged.world.worldgen.GeneratorContext;
import raccoonman.reterraforged.world.worldgen.RTFRandomState;
import raccoonman.reterraforged.world.worldgen.biome.BiomePreviewResolver;
import raccoonman.reterraforged.world.worldgen.cell.Cell;
import raccoonman.reterraforged.world.worldgen.densityfunction.tile.Tile;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlans;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlan;

/** Finished-chunk comparison for the exact resolver used by the preset previews. */
public final class RtfBiomePreviewParityProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-biome-preview-parity", "1", PreviewParity::new);
        ProbeRegistry.register("squinch:rtf-biome-preview-batch-parity", "1", PreviewParity::new);
        ProbeRegistry.register("squinch:rtf-biome-preview-batch-equivalence", "1", BatchEquivalence::new);
    }

    private static final class BatchEquivalence implements ProbeExecution {
        private final int centerX;
        private final int centerZ;
        private final int zoom;
        private final int exampleLimit;

        private BatchEquivalence(ProbeRequest request) {
            JsonObject config = request.config();
            this.centerX = config.has("center_x") ? config.get("center_x").getAsInt() : 0;
            this.centerZ = config.has("center_z") ? config.get("center_z").getAsInt() : 0;
            this.zoom = config.has("zoom") ? config.get("zoom").getAsInt() : 150;
            this.exampleLimit = config.has("example_limit")
                ? config.get("example_limit").getAsInt()
                : 64;
            if (this.zoom <= 0 || this.exampleLimit < 0 || this.exampleLimit > 1024) {
                throw new IllegalArgumentException("zoom must be positive and example_limit must be 0..1024");
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            Object randomState = level.getChunkSource().randomState();
            if (!(randomState instanceof RTFRandomState rtfRandomState)
                || rtfRandomState.preset() == null) {
                return ProbeResult.partial(
                    ProbePhase.PREDICTION, new JsonObject(), 0, 1,
                    "rtf-preset-or-random-state-unavailable"
                );
            }
            Preset preset = rtfRandomState.preset();
            HolderLookup.Provider previewProvider = preset.buildPreviewLookups(server.registryAccess());
            GeneratorContext context = GeneratorContext.makeUncached(
                preset,
                previewProvider.lookupOrThrow(RTFRegistries.NOISE),
                (int) level.getSeed(),
                4,
                0,
                6
            );
            JsonArray mismatchExamples = new JsonArray();
            long mismatches = 0L;
            long repeatMismatches = 0L;
            long parallelNanos;
            long repeatNanos;
            long serialNanos;
            int sampledPixels;
            TreeSet<String> palette = new TreeSet<>();
            boolean parallelEnabled;

            try (
                BiomePreviewResolver resolver = BiomePreviewResolver.create(
                    server.registryAccess(),
                    previewProvider,
                    level.dimensionTypeRegistration(),
                    level.getChunkSource().getGenerator(),
                    preset,
                    context,
                    level.getSeed()
                );
                Tile tile = context.generator.generateZoomed(
                    this.centerX, this.centerZ, this.zoom, true, () -> false
                ).join()
            ) {
                parallelEnabled = resolver.supportsParallelTileQueries();
                long started = System.nanoTime();
                BiomePreviewResolver.ResolvedTile parallel = resolver.resolveSurfaceTile(
                    tile, this.centerX, this.centerZ, this.zoom, context.levels, () -> false
                );
                parallelNanos = System.nanoTime() - started;

                started = System.nanoTime();
                BiomePreviewResolver.ResolvedTile repeated = resolver.resolveSurfaceTile(
                    tile, this.centerX, this.centerZ, this.zoom, context.levels, () -> false
                );
                repeatNanos = System.nanoTime() - started;

                int size = tile.getBlockSize().size();
                sampledPixels = Math.multiplyExact(size, size);
                int border = tile.getBlockSize().border();
                int halfSize = size / 2;
                BiomePreviewResolver.TileBiomeRequest serial = resolver.tileRequest(
                    tile, this.centerX, this.centerZ, this.zoom
                );
                started = System.nanoTime();
                for (int z = 0; z < size; z++) {
                    int blockZ = this.centerZ + (z - halfSize) * this.zoom;
                    for (int x = 0; x < size; x++) {
                        int blockX = this.centerX + (x - halfSize) * this.zoom;
                        Cell cell = tile.getCellRaw(border + x, border + z);
                        int minY = -context.levels.worldDepth;
                        int maxY = Math.max(minY, context.levels.terrainScaleFactor - 1);
                        int surfaceY = Math.max(
                            minY, Math.min(maxY, context.levels.scale(cell.height))
                        );
                        int quartX = QuartPos.fromBlock(blockX);
                        int quartY = QuartPos.fromBlock(surfaceY);
                        int quartZ = QuartPos.fromBlock(blockZ);
                        Holder<Biome> expected = serial.resolveQuart(quartX, quartY, quartZ);
                        Holder<Biome> actual = parallel.biomeAt(x, z);
                        Holder<Biome> repeatedValue = repeated.biomeAt(x, z);
                        palette.add(MinecraftProbeHelpers.biomeId(actual));
                        if (!actual.equals(expected)) {
                            mismatches++;
                            if (mismatchExamples.size() < this.exampleLimit) {
                                mismatchExamples.add(example(
                                    blockX,
                                    surfaceY,
                                    blockZ,
                                    MinecraftProbeHelpers.biomeId(expected),
                                    MinecraftProbeHelpers.biomeId(actual)
                                ));
                            }
                        }
                        if (!actual.equals(repeatedValue)) {
                            repeatMismatches++;
                        }
                    }
                }
                serialNanos = System.nanoTime() - started;
            }

            JsonObject data = new JsonObject();
            data.addProperty("authority", "exact-parallel-batch-vs-serial-request");
            data.addProperty("center_x", this.centerX);
            data.addProperty("center_z", this.centerZ);
            data.addProperty("zoom", this.zoom);
            data.addProperty("sampled_pixels", sampledPixels);
            data.addProperty("parallel_tile_queries", parallelEnabled);
            data.addProperty("parallel_millis", parallelNanos / 1_000_000.0D);
            data.addProperty("parallel_repeat_millis", repeatNanos / 1_000_000.0D);
            data.addProperty("serial_millis", serialNanos / 1_000_000.0D);
            data.addProperty("speedup", (double) serialNanos / (double) parallelNanos);
            data.addProperty("mismatch_count", mismatches);
            data.addProperty("repeat_mismatch_count", repeatMismatches);
            data.addProperty("palette_size", palette.size());
            JsonArray paletteValues = new JsonArray();
            palette.forEach(paletteValues::add);
            data.add("palette", paletteValues);
            data.add("mismatch_examples", mismatchExamples);
            return ProbeResult.complete(
                parallelEnabled && mismatches == 0L && repeatMismatches == 0L
                    ? TerminalState.PASS
                    : TerminalState.FAIL,
                ProbePhase.PREDICTION,
                data,
                1
            );
        }

        private static JsonObject example(
            int blockX,
            int blockY,
            int blockZ,
            String expected,
            String actual
        ) {
            JsonObject result = new JsonObject();
            result.addProperty("x", blockX);
            result.addProperty("y", blockY);
            result.addProperty("z", blockZ);
            result.addProperty("serial_biome_id", expected);
            result.addProperty("parallel_biome_id", actual);
            return result;
        }
    }

    private static final class PreviewParity implements ProbeExecution {
        private final FinishedChunkSelection selection;
        private final int horizontalQuartStep;
        private final int exampleLimit;
        private final boolean useServerGeneratorContext;
        private final boolean useTileAuthority;
        private final boolean useFullProvider;
        private final boolean useBatchAuthority;

        private PreviewParity(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "rtf-biome-preview-parity");
            this.horizontalQuartStep = config.has("horizontal_quart_step")
                ? config.get("horizontal_quart_step").getAsInt()
                : 1;
            this.exampleLimit = config.has("example_limit")
                ? config.get("example_limit").getAsInt()
                : 32;
            this.useServerGeneratorContext = config.has("use_server_generator_context")
                && config.get("use_server_generator_context").getAsBoolean();
            this.useTileAuthority = !config.has("use_tile_authority")
                || config.get("use_tile_authority").getAsBoolean();
            this.useFullProvider = !config.has("use_full_provider")
                || config.get("use_full_provider").getAsBoolean();
            this.useBatchAuthority = config.has("use_batch_authority")
                && config.get("use_batch_authority").getAsBoolean();
            if (this.horizontalQuartStep < 1 || this.horizontalQuartStep > 4
                || 4 % this.horizontalQuartStep != 0
                || this.exampleLimit < 0 || this.exampleLimit > 1024) {
                throw new IllegalArgumentException(
                    "horizontal_quart_step must divide four and example_limit must be 0..1024"
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
            if (!snapshot.complete()) {
                return this.selection.result(snapshot, new JsonObject());
            }

            Object randomState = level.getChunkSource().randomState();
            if (!(randomState instanceof RTFRandomState rtfRandomState)) {
                return ProbeResult.partial(
                    ProbePhase.FINISHED_CHUNK, new JsonObject(), 0, snapshot.requested(),
                    "overworld-random-state-is-not-rtf"
                );
            }
            Preset preset = rtfRandomState.preset();
            if (preset == null || rtfRandomState.generatorContext() == null) {
                return ProbeResult.partial(
                    ProbePhase.FINISHED_CHUNK, new JsonObject(), 0, snapshot.requested(),
                    "rtf-preset-or-generator-context-unavailable"
                );
            }

            HolderLookup.Provider previewProvider = this.useFullProvider
                ? preset.buildPreviewLookups(server.registryAccess())
                : preset.buildPatch(server.registryAccess());
            GeneratorContext context = this.useServerGeneratorContext
                ? rtfRandomState.generatorContext()
                : GeneratorContext.makeUncached(
                    preset,
                    previewProvider.lookupOrThrow(RTFRegistries.NOISE),
                    (int) level.getSeed(),
                    4,
                    0,
                    6
                );
            BiomePreviewResolver resolver = BiomePreviewResolver.create(
                server.registryAccess(),
                previewProvider,
                level.dimensionTypeRegistration(),
                level.getChunkSource().getGenerator(),
                preset,
                context,
                level.getSeed()
            );
            long sampled = 0;
            long mismatches = 0;
            long undergroundPreviewSelections = 0;
            Map<String, Long> biomeCounts = new TreeMap<>();
            Map<String, Long> providerDomainCounts = new TreeMap<>();
            long providerFallbacks = 0;
            JsonArray mismatchExamples = new JsonArray();
            Cell cell = new Cell();
            Map<Long, Tile> tiles = new HashMap<>();
            Map<Long, BiomePreviewResolver.TileBiomeRequest> tileRequests = new HashMap<>();
            Map<Long, BiomePreviewResolver.ResolvedTile> resolvedTiles = new HashMap<>();
            long batchResolutionNanos = 0L;
            try (resolver) {
                for (FinishedChunkSelection.ReadyChunk ready : snapshot.ready()) {
                    int chunkQuartX = ready.coordinate().x() * 4;
                    int chunkQuartZ = ready.coordinate().z() * 4;
                    for (int localQuartX = 0; localQuartX < 4; localQuartX += this.horizontalQuartStep) {
                        for (int localQuartZ = 0; localQuartZ < 4; localQuartZ += this.horizontalQuartStep) {
                            int quartX = chunkQuartX + localQuartX;
                            int quartZ = chunkQuartZ + localQuartZ;
                            int blockX = QuartPos.toBlock(quartX) + 2;
                            int blockZ = QuartPos.toBlock(quartZ) + 2;
                            Climate.Sampler sampler = null;
                            BiomePreviewResolver.TileBiomeRequest tileRequest = null;
                            BiomePreviewResolver.ResolvedTile resolvedTile = null;
                            int tileBlockX = 0;
                            int tileBlockZ = 0;
                            if (this.useTileAuthority) {
                                int tileSize = context.generator.getTileBlockSize();
                                int tileX = Math.floorDiv(blockX, tileSize);
                                int tileZ = Math.floorDiv(blockZ, tileSize);
                                long tileKey = ((long) tileX << 32) ^ (tileZ & 0xFFFFFFFFL);
                                Tile tile = tiles.computeIfAbsent(tileKey,
                                    ignored -> context.generator.generate(tileX, tileZ).join());
                                tileBlockX = tile.getBlockX();
                                tileBlockZ = tile.getBlockZ();
                                if (this.useBatchAuthority) {
                                    resolvedTile = resolvedTiles.get(tileKey);
                                    if (resolvedTile == null) {
                                        long batchStarted = System.nanoTime();
                                        resolvedTile = resolver.resolveSurfaceTile(
                                            tile,
                                            tileBlockX + tileSize / 2,
                                            tileBlockZ + tileSize / 2,
                                            1,
                                            context.levels,
                                            () -> false
                                        );
                                        batchResolutionNanos += System.nanoTime() - batchStarted;
                                        resolvedTiles.put(tileKey, resolvedTile);
                                    }
                                }
                                tileRequest = tileRequests.computeIfAbsent(tileKey,
                                    ignored -> resolver.tileRequestAtOrigin(
                                        tile, tile.getBlockX(), tile.getBlockZ(), 1
                                    ));
                                sampler = tileRequest.climateSampler();
                                cell.copyFrom(tile.lookup(blockX - tile.getBlockX(), blockZ - tile.getBlockZ()));
                            } else {
                                context.lookup.applyCell(cell.reset(), blockX, blockZ, true, false);
                            }
                            int surfaceY = clampSurfaceY(context, cell);
                            int quartY = QuartPos.fromBlock(surfaceY);

                            String stored = MinecraftProbeHelpers.biomeId(
                                ready.chunk().getNoiseBiome(quartX, quartY, quartZ)
                            );
                            Holder<Biome> previewHolder = sampler == null
                                ? resolver.resolveQuart(quartX, quartY, quartZ)
                                : resolvedTile == null
                                    ? tileRequest.resolveQuart(quartX, quartY, quartZ)
                                    : resolvedTile.biomeAt(blockX - tileBlockX, blockZ - tileBlockZ);
                            if (!resolver.plan().providerSelection().providers().isEmpty()) {
                                WorldgenPlans.ProviderResult selected = sampler == null
                                    ? resolver.inspectProviderSelection(quartX, quartY, quartZ)
                                    : tileRequest.inspectProviderSelection(quartX, quartY, quartZ);
                                providerDomainCounts.merge(selected.domain().toString(), 1L, Long::sum);
                                if (selected.usedFallback()) {
                                    providerFallbacks++;
                                }
                            }
                            String preview = MinecraftProbeHelpers.biomeId(previewHolder);
                            sampled++;
                            if (resolver.isUnderground(previewHolder)) {
                                undergroundPreviewSelections++;
                            }
                            biomeCounts.merge(stored, 1L, Long::sum);
                            if (!stored.equals(preview)) {
                                mismatches++;
                                if (mismatchExamples.size() < this.exampleLimit) {
                                    Holder<Biome> directPreviewHolder = resolver.resolveQuart(
                                        quartX, quartY, quartZ
                                    );
                                    Climate.Sampler liveSampler = level.getChunkSource()
                                        .randomState().sampler();
                                    Holder<Biome> liveServerHolder = level.getChunkSource().getGenerator()
                                        .getBiomeSource().getNoiseBiome(
                                            quartX,
                                            quartY,
                                            quartZ,
                                            liveSampler
                                        );
                                    JsonObject mismatch = example(
                                        blockX, surfaceY, blockZ, stored, preview
                                    );
                                    mismatch.addProperty(
                                        "direct_preview_biome_id",
                                        MinecraftProbeHelpers.biomeId(directPreviewHolder)
                                    );
                                    mismatch.addProperty(
                                        "live_server_biome_id",
                                        MinecraftProbeHelpers.biomeId(liveServerHolder)
                                    );
                                    mismatch.addProperty("preview_cell_x", cell.biomeRegionX);
                                    mismatch.addProperty("preview_cell_z", cell.biomeRegionZ);
                                    Cell liveCell = new Cell();
                                    rtfRandomState.generatorContext().lookup.applyCell(
                                        liveCell, blockX, blockZ, false, true
                                    );
                                    mismatch.addProperty("live_cell_x", liveCell.biomeRegionX);
                                    mismatch.addProperty("live_cell_z", liveCell.biomeRegionZ);
                                    Climate.TargetPoint previewTarget = sampler == null
                                        ? liveSampler.sample(quartX, quartY, quartZ)
                                        : sampler.sample(quartX, quartY, quartZ);
                                    Climate.TargetPoint liveTarget = liveSampler.sample(
                                        quartX, quartY, quartZ
                                    );
                                    mismatch.add("preview_target", target(previewTarget));
                                    mismatch.add("live_target", target(liveTarget));
                                    WorldgenPlan livePlan = rtfRandomState.plan();
                                    addSelection(
                                        mismatch,
                                        "preview_plan_preview_input",
                                        resolver.plan(),
                                        cell.biomeRegionX,
                                        cell.biomeRegionZ,
                                        previewTarget
                                    );
                                    addSelection(
                                        mismatch,
                                        "preview_plan_live_input",
                                        resolver.plan(),
                                        liveCell.biomeRegionX,
                                        liveCell.biomeRegionZ,
                                        liveTarget
                                    );
                                    addSelection(
                                        mismatch,
                                        "live_plan_preview_input",
                                        livePlan,
                                        cell.biomeRegionX,
                                        cell.biomeRegionZ,
                                        previewTarget
                                    );
                                    addSelection(
                                        mismatch,
                                        "live_plan_live_input",
                                        livePlan,
                                        liveCell.biomeRegionX,
                                        liveCell.biomeRegionZ,
                                        liveTarget
                                    );
                                    mismatchExamples.add(mismatch);
                                }
                            }
                        }
                    }
                }
            } finally {
                tiles.values().forEach(Tile::close);
            }

            JsonObject data = new JsonObject();
            data.addProperty("authority", "preview-resolver-vs-finished-chunk-quart-palette");
            data.addProperty(
                "query_path",
                this.useBatchAuthority
                    ? "request-owned exact parallel surface-tile resolver"
                    : this.useTileAuthority
                    ? "request-owned resolver with prepared FTF tile cell"
                    : "BiomeSource.getNoiseBiome(quartX,quartY,quartZ,sampler)"
            );
            data.addProperty("batch_tile_count", resolvedTiles.size());
            data.addProperty("batch_resolution_millis", batchResolutionNanos / 1_000_000.0D);
            data.addProperty("parallel_tile_queries", resolver.supportsParallelTileQueries());
            data.addProperty("surface_y_authority", this.useTileAuthority ? "prepared-preview-tile" : "rtf-preview-cell-model");
            data.addProperty("climate_sampler_authority", this.useTileAuthority ? "prepared-preview-tile" : "generator-context");
            data.addProperty(
                "provider_authority",
                this.useFullProvider ? "selected-graph-with-request-patches" : "patch-provider"
            );
            data.addProperty("active_preview_integrations", String.join(",", resolver.activeIntegrations()));
            JsonObject providerDomains = new JsonObject();
            providerDomainCounts.forEach(providerDomains::addProperty);
            data.add("selected_provider_domain_counts", providerDomains);
            data.addProperty("provider_selection_fallbacks", providerFallbacks);
            String generatorContextMode = this.useServerGeneratorContext
                ? "server-cached-context"
                : "uncached-editor-factor-4";
            data.addProperty("generator_context", generatorContextMode);
            data.addProperty("sampled_quart_columns", sampled);
            data.addProperty("mismatch_count", mismatches);
            data.addProperty("underground_preview_selection_count", undergroundPreviewSelections);
            data.addProperty("horizontal_quart_step", this.horizontalQuartStep);
            JsonObject storedBiomeCounts = new JsonObject();
            biomeCounts.forEach(storedBiomeCounts::addProperty);
            data.add("stored_biome_counts", storedBiomeCounts);
            data.add("mismatch_examples", mismatchExamples);
            return ProbeResult.complete(
                mismatches == 0 && undergroundPreviewSelections == 0 ? TerminalState.PASS : TerminalState.FAIL,
                ProbePhase.FINISHED_CHUNK,
                data,
                snapshot.ready().size()
            );
        }

        private static int clampSurfaceY(GeneratorContext context, Cell cell) {
            int minY = -context.levels.worldDepth;
            int maxY = Math.max(minY, context.levels.worldHeight - 1);
            return Math.max(minY, Math.min(maxY, context.levels.scale(cell.height)));
        }

        private static JsonObject example(
            int blockX,
            int blockY,
            int blockZ,
            String stored,
            String preview
        ) {
            JsonObject result = new JsonObject();
            result.addProperty("x", blockX);
            result.addProperty("y", blockY);
            result.addProperty("z", blockZ);
            result.addProperty("stored_biome_id", stored);
            result.addProperty("preview_biome_id", preview);
            return result;
        }

        private static JsonObject target(Climate.TargetPoint target) {
            JsonObject result = new JsonObject();
            result.addProperty("temperature", target.temperature());
            result.addProperty("humidity", target.humidity());
            result.addProperty("continentalness", target.continentalness());
            result.addProperty("erosion", target.erosion());
            result.addProperty("depth", target.depth());
            result.addProperty("weirdness", target.weirdness());
            return result;
        }

        private static void addSelection(
            JsonObject output,
            String name,
            WorldgenPlan plan,
            long cellX,
            long cellZ,
            Climate.TargetPoint target
        ) {
            WorldgenPlans.ProviderResult selection = plan.providerSelection()
                .resolve(cellX, cellZ, target)
                .orElseThrow();
            JsonObject result = new JsonObject();
            result.addProperty("domain", selection.domain().toString());
            result.addProperty("biome", MinecraftProbeHelpers.biomeId(selection.biome()));
            result.addProperty("fallback", selection.usedFallback());
            output.add(name, result);
        }
    }
}
