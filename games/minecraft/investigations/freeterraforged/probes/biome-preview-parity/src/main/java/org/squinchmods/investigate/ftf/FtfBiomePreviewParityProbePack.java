package org.squinchmods.investigate.ftf;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Map;
import java.util.TreeMap;
import java.util.TreeSet;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.HolderLookup;
import net.minecraft.core.Holder;
import net.minecraft.core.BlockPos;
import net.minecraft.core.QuartPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.dimension.LevelStem;
import net.minecraft.world.level.levelgen.Heightmap;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;

import etcodehome.freeterraforged.data.worldgen.preset.settings.Preset;
import etcodehome.freeterraforged.registries.FTFRegistries;
import etcodehome.freeterraforged.world.worldgen.GeneratorContext;
import etcodehome.freeterraforged.world.worldgen.FTFRandomState;
import etcodehome.freeterraforged.world.worldgen.biome.BiomePreviewResolver;
import etcodehome.freeterraforged.world.worldgen.cell.Cell;
import etcodehome.freeterraforged.world.worldgen.densityfunction.tile.Tile;
import etcodehome.freeterraforged.world.worldgen.runtime.WorldgenPlans;
import etcodehome.freeterraforged.world.worldgen.runtime.WorldgenPlan;
import etcodehome.freeterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;
import etcodehome.freeterraforged.world.worldgen.runtime.WorldgenFingerprints;
import etcodehome.freeterraforged.world.worldgen.runtime.WorldgenCapabilityDiscovery;
import etcodehome.freeterraforged.world.worldgen.runtime.WorldgenContributionRevision;

/** Finished-chunk comparison for the exact resolver used by the preset previews. */
public final class FtfBiomePreviewParityProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:ftf-biome-preview-parity", "1", PreviewParity::new);
        ProbeRegistry.register("squinch:ftf-biome-preview-batch-parity", "1", PreviewParity::new);
        ProbeRegistry.register("squinch:ftf-biome-preview-batch-equivalence", "1", BatchEquivalence::new);
        ProbeRegistry.register("squinch:ftf-runtime-biome-ownership", "1", RuntimeBiomeOwnership::new);
    }

    private static final class RuntimeBiomeOwnership implements ProbeExecution {
        private final java.util.List<ResourceLocation> targets;
        private final int radius;

        private RuntimeBiomeOwnership(ProbeRequest request) {
            JsonObject config = request.config();
            this.targets = config.getAsJsonArray("target_biomes").asList().stream()
                .map(value -> ResourceLocation.parse(value.getAsString()))
                .toList();
            this.radius = config.has("radius") ? config.get("radius").getAsInt() : 6400;
            if (this.targets.isEmpty() || this.radius <= 0) {
                throw new IllegalArgumentException("target_biomes must be non-empty and radius must be positive");
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            var generator = level.getChunkSource().getGenerator();
            var source = generator.getBiomeSource();
            var sampler = level.getChunkSource().randomState().sampler();
            var biomes = level.registryAccess().registryOrThrow(Registries.BIOME);
            BlockPos origin = level.getSharedSpawnPos();
            JsonArray results = new JsonArray();
            boolean passed = generator instanceof TerraForgedChunkGenerator;
            for (ResourceLocation id : this.targets) {
                Holder<Biome> target = biomes.getHolderOrThrow(ResourceKey.create(Registries.BIOME, id));
                var located = level.findClosestBiome3d(target::equals, origin, this.radius, 32, 64);
                JsonObject result = new JsonObject();
                result.addProperty("target", id.toString());
                result.addProperty("possible_output", source.possibleBiomes().contains(target));
                if (located == null) {
                    result.addProperty("found", false);
                    passed = false;
                    results.add(result);
                    continue;
                }
                BlockPos locatedPos = located.getFirst();
                Holder<Biome> locatedQuery = source.getNoiseBiome(
                    QuartPos.fromBlock(locatedPos.getX()),
                    QuartPos.fromBlock(locatedPos.getY()),
                    QuartPos.fromBlock(locatedPos.getZ()),
                    sampler
                );
                level.getChunk(
                    Math.floorDiv(locatedPos.getX(), 16),
                    Math.floorDiv(locatedPos.getZ(), 16)
                );
                int surfaceY = level.getHeight(
                    Heightmap.Types.WORLD_SURFACE,
                    locatedPos.getX(),
                    locatedPos.getZ()
                );
                BlockPos surfacePos = new BlockPos(locatedPos.getX(), surfaceY, locatedPos.getZ());
                Holder<Biome> surfaceQuery = source.getNoiseBiome(
                    QuartPos.fromBlock(surfacePos.getX()),
                    QuartPos.fromBlock(surfacePos.getY()),
                    QuartPos.fromBlock(surfacePos.getZ()),
                    sampler
                );
                Holder<Biome> surfaceStored = level.getBiome(surfacePos);
                boolean targetAtLocate = target.equals(located.getSecond()) && target.equals(locatedQuery);
                boolean targetAtSurface = target.equals(surfaceQuery) && target.equals(surfaceStored);
                result.addProperty("found", true);
                result.addProperty("x", locatedPos.getX());
                result.addProperty("y", locatedPos.getY());
                result.addProperty("z", locatedPos.getZ());
                result.addProperty("surface_y", surfaceY);
                result.addProperty("located_biome", MinecraftProbeHelpers.biomeId(located.getSecond()));
                result.addProperty("located_query_biome", MinecraftProbeHelpers.biomeId(locatedQuery));
                result.addProperty("surface_query_biome", MinecraftProbeHelpers.biomeId(surfaceQuery));
                result.addProperty("surface_stored_biome", MinecraftProbeHelpers.biomeId(surfaceStored));
                result.addProperty("target_at_located_coordinate", targetAtLocate);
                result.addProperty("target_at_surface_coordinate", targetAtSurface);
                passed &= source.possibleBiomes().contains(target) && targetAtLocate && targetAtSurface;
                results.add(result);
            }
            JsonObject data = new JsonObject();
            data.addProperty("runtime_generator_class", generator.getClass().getName());
            data.addProperty("runtime_biome_source_class", source.getClass().getName());
            if (generator instanceof TerraForgedChunkGenerator terraForged) {
                data.addProperty(
                    "acquisition_biome_source_class",
                    terraForged.acquisitionBiomeSource().getClass().getName()
                );
                passed &= source != terraForged.acquisitionBiomeSource();
            }
            data.add("targets", results);
            return ProbeResult.complete(
                passed ? TerminalState.PASS : TerminalState.FAIL,
                ProbePhase.FINISHED_CHUNK,
                data,
                this.targets.size()
            );
        }
    }

    private static final class BatchEquivalence implements ProbeExecution {
        private final int centerX;
        private final int centerZ;
        private final int zoom;
        private final int exampleLimit;
        private final java.util.List<String> requiredNamespaces;
        private final java.util.List<String> requiredTransitions;

        private BatchEquivalence(ProbeRequest request) {
            JsonObject config = request.config();
            this.centerX = config.has("center_x") ? config.get("center_x").getAsInt() : 0;
            this.centerZ = config.has("center_z") ? config.get("center_z").getAsInt() : 0;
            this.zoom = config.has("zoom") ? config.get("zoom").getAsInt() : 150;
            this.exampleLimit = config.has("example_limit")
                ? config.get("example_limit").getAsInt()
                : 64;
            this.requiredNamespaces = config.has("required_namespaces")
                ? config.getAsJsonArray("required_namespaces").asList().stream()
                    .map(value -> value.getAsString())
                    .toList()
                : java.util.List.of();
            this.requiredTransitions = config.has("required_transitions")
                ? config.getAsJsonArray("required_transitions").asList().stream()
                    .map(value -> value.getAsString())
                    .toList()
                : java.util.List.of();
            if (this.zoom <= 0 || this.exampleLimit < 0 || this.exampleLimit > 1024) {
                throw new IllegalArgumentException("zoom must be positive and example_limit must be 0..1024");
            }
            if (this.requiredNamespaces.stream().anyMatch(String::isBlank)) {
                throw new IllegalArgumentException("required_namespaces must contain non-empty namespace IDs");
            }
            if (this.requiredTransitions.stream().anyMatch(String::isBlank)) {
                throw new IllegalArgumentException("required_transitions must contain non-empty transitions");
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            Object randomState = level.getChunkSource().randomState();
            if (!(randomState instanceof FTFRandomState ftfRandomState)
                || ftfRandomState.preset() == null) {
                return ProbeResult.partial(
                    ProbePhase.PREDICTION, new JsonObject(), 0, 1,
                    "ftf-preset-or-random-state-unavailable"
                );
            }
            Preset preset = ftfRandomState.preset();
            HolderLookup.Provider previewProvider = preset.buildPreviewLookups(server.registryAccess());
            GeneratorContext context = GeneratorContext.makeUncached(
                preset,
                previewProvider.lookupOrThrow(FTFRegistries.NOISE),
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
            Map<String, Long> selectionTransitions = new TreeMap<>();
            boolean parallelEnabled;
            MessageDigest gridDigest = sha256();
			var providers = WorldgenCapabilityDiscovery.discover(getClass().getClassLoader());
			var contributions = WorldgenContributionRevision.snapshot(LevelStem.OVERWORLD, providers);

            try (
                BiomePreviewResolver resolver = BiomePreviewResolver.create(
                    server.registryAccess(),
                    previewProvider,
					LevelStem.OVERWORLD,
                    level.dimensionTypeRegistration(),
                    level.getChunkSource().getGenerator(),
                    preset,
                    context,
                    level.getSeed(),
                    level.dimension().location().toString(),
                    "server-registry-access",
					WorldgenFingerprints.tags(server.registryAccess()),
					contributions,
					providers
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
						String actualId = MinecraftProbeHelpers.biomeId(actual);
						String baseId = MinecraftProbeHelpers.biomeId(
							serial.inspectProviderSelection(quartX, quartY, quartZ).biome()
						);
						if (!baseId.equals(actualId)) {
							selectionTransitions.merge(baseId + " -> " + actualId, 1L, Long::sum);
						}
						String expectedId = MinecraftProbeHelpers.biomeId(expected);
						String repeatedId = MinecraftProbeHelpers.biomeId(repeatedValue);
						palette.add(actualId);
						gridDigest.update(actualId.getBytes(StandardCharsets.UTF_8));
						gridDigest.update((byte) 0);
						if (!actualId.equals(expectedId)) {
							mismatches++;
							if (mismatchExamples.size() < this.exampleLimit) {
								mismatchExamples.add(example(
									blockX,
									surfaceY,
									blockZ,
									expectedId,
									actualId
								));
							}
						}
						if (!actualId.equals(repeatedId)) {
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
            data.addProperty("grid_sha256", HexFormat.of().formatHex(gridDigest.digest()));
            data.addProperty("palette_size", palette.size());
            JsonArray paletteValues = new JsonArray();
            palette.forEach(paletteValues::add);
            data.add("palette", paletteValues);
            JsonObject namespacePresence = new JsonObject();
            boolean requiredNamespacesPresent = true;
            for (String namespace : this.requiredNamespaces) {
                boolean present = palette.stream().anyMatch(value -> value.startsWith(namespace + ":"));
                namespacePresence.addProperty(namespace, present);
                requiredNamespacesPresent &= present;
            }
            data.add("required_namespace_presence", namespacePresence);
            JsonObject transitions = new JsonObject();
            selectionTransitions.forEach(transitions::addProperty);
            data.add("selection_transition_counts", transitions);
            boolean requiredTransitionsPresent = this.requiredTransitions.stream()
                .allMatch(selectionTransitions::containsKey);
            JsonObject transitionPresence = new JsonObject();
            this.requiredTransitions.forEach(value -> transitionPresence.addProperty(
                value, selectionTransitions.containsKey(value)
            ));
            data.add("required_transition_presence", transitionPresence);
            data.add("mismatch_examples", mismatchExamples);
            return ProbeResult.complete(
                parallelEnabled && mismatches == 0L && repeatMismatches == 0L
                    && requiredNamespacesPresent && requiredTransitionsPresent
                    ? TerminalState.PASS
                    : TerminalState.FAIL,
                ProbePhase.PREDICTION,
                data,
                1
            );
        }

		private static MessageDigest sha256() {
			try {
				return MessageDigest.getInstance("SHA-256");
			} catch (NoSuchAlgorithmException exception) {
				throw new IllegalStateException(exception);
			}
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
        private final boolean useFinishedSurfaceAuthority;

        private PreviewParity(ProbeRequest request) {
            JsonObject config = request.config();
            this.selection = new FinishedChunkSelection(config, "ftf-biome-preview-parity");
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
            this.useFinishedSurfaceAuthority = config.has("use_finished_surface_authority")
                && config.get("use_finished_surface_authority").getAsBoolean();
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
            if (!(randomState instanceof FTFRandomState ftfRandomState)) {
                return ProbeResult.partial(
                    ProbePhase.FINISHED_CHUNK, new JsonObject(), 0, snapshot.requested(),
                    "overworld-random-state-is-not-ftf"
                );
            }
            Preset preset = ftfRandomState.preset();
            if (preset == null || ftfRandomState.generatorContext() == null) {
                return ProbeResult.partial(
                    ProbePhase.FINISHED_CHUNK, new JsonObject(), 0, snapshot.requested(),
                    "ftf-preset-or-generator-context-unavailable"
                );
            }

            HolderLookup.Provider previewProvider = this.useFullProvider
                ? preset.buildPreviewLookups(server.registryAccess())
                : preset.buildPatch(server.registryAccess());
            GeneratorContext context = this.useServerGeneratorContext
                ? ftfRandomState.generatorContext()
                : GeneratorContext.makeUncached(
                    preset,
                    previewProvider.lookupOrThrow(FTFRegistries.NOISE),
                    (int) level.getSeed(),
                    4,
                    0,
                    6
                );
			var providers = WorldgenCapabilityDiscovery.discover(getClass().getClassLoader());
			var contributions = WorldgenContributionRevision.snapshot(LevelStem.OVERWORLD, providers);
            BiomePreviewResolver resolver = BiomePreviewResolver.create(
                server.registryAccess(),
                previewProvider,
				LevelStem.OVERWORLD,
                level.dimensionTypeRegistration(),
                level.getChunkSource().getGenerator(),
                preset,
                context,
                level.getSeed(),
                level.dimension().location().toString(),
                "server-registry-access",
				WorldgenFingerprints.tags(server.registryAccess()),
				contributions,
				providers
            );
            long sampled = 0;
            long mismatches = 0;
            long undergroundPreviewSelections = 0;
            Map<String, Long> biomeCounts = new TreeMap<>();
            Map<String, Long> providerDomainCounts = new TreeMap<>();
            Map<String, Long> selectionTransitionCounts = new TreeMap<>();
            long providerFallbacks = 0;
            long selectionTransitions = 0;
            long surfaceHeightMismatches = 0;
            int maximumSurfaceHeightDelta = 0;
            JsonArray mismatchExamples = new JsonArray();
            JsonArray surfaceHeightMismatchExamples = new JsonArray();
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
                            int previewSurfaceY = clampSurfaceY(context, cell);
                            int finishedSurfaceY = this.useFinishedSurfaceAuthority
                                ? level.getHeight(Heightmap.Types.WORLD_SURFACE_WG, blockX, blockZ)
                                : previewSurfaceY;
                            int previewQuartY = QuartPos.fromBlock(previewSurfaceY);
                            int finishedQuartY = QuartPos.fromBlock(finishedSurfaceY);
                            int surfaceHeightDelta = Math.abs(finishedSurfaceY - previewSurfaceY);
                            if (surfaceHeightDelta != 0) {
                                surfaceHeightMismatches++;
                                maximumSurfaceHeightDelta = Math.max(
                                    maximumSurfaceHeightDelta, surfaceHeightDelta
                                );
                                if (surfaceHeightMismatchExamples.size() < this.exampleLimit) {
                                    JsonObject example = new JsonObject();
                                    example.addProperty("x", blockX);
                                    example.addProperty("z", blockZ);
                                    example.addProperty("preview_surface_y", previewSurfaceY);
                                    example.addProperty("finished_surface_y", finishedSurfaceY);
                                    example.addProperty("absolute_delta", surfaceHeightDelta);
                                    surfaceHeightMismatchExamples.add(example);
                                }
                            }

                            String stored = MinecraftProbeHelpers.biomeId(
                                ready.chunk().getNoiseBiome(quartX, finishedQuartY, quartZ)
                            );
                            Holder<Biome> previewHolder = sampler == null
                                ? resolver.resolveQuart(quartX, previewQuartY, quartZ)
                                : resolvedTile == null
                                    ? tileRequest.resolveQuart(quartX, previewQuartY, quartZ)
                                    : resolvedTile.biomeAt(blockX - tileBlockX, blockZ - tileBlockZ);
                            if (!resolver.plan().providerSelection().providers().isEmpty()) {
                                WorldgenPlans.ProviderResult selected = sampler == null
                                    ? resolver.inspectProviderSelection(quartX, previewQuartY, quartZ)
                                    : tileRequest.inspectProviderSelection(quartX, previewQuartY, quartZ);
                                providerDomainCounts.merge(selected.domain().toString(), 1L, Long::sum);
                                if (selected.usedFallback()) {
                                    providerFallbacks++;
                                }
                                String before = MinecraftProbeHelpers.biomeId(selected.biome());
                                String after = MinecraftProbeHelpers.biomeId(previewHolder);
                                if (!before.equals(after)) {
                                    selectionTransitions++;
                                    selectionTransitionCounts.merge(before + " -> " + after, 1L, Long::sum);
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
                                        quartX, previewQuartY, quartZ
                                    );
                                    Climate.Sampler liveSampler = level.getChunkSource()
                                        .randomState().sampler();
                                    Holder<Biome> liveServerHolder = level.getChunkSource().getGenerator()
                                        .getBiomeSource().getNoiseBiome(
                                            quartX,
                                            finishedQuartY,
                                            quartZ,
                                            liveSampler
                                        );
                                    JsonObject mismatch = example(
                                        blockX, finishedSurfaceY, blockZ, stored, preview
                                    );
                                    mismatch.addProperty("preview_surface_y", previewSurfaceY);
                                    mismatch.addProperty("finished_surface_y", finishedSurfaceY);
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
                                    ftfRandomState.generatorContext().lookup.applyCell(
                                        liveCell, blockX, blockZ, false, true
                                    );
                                    mismatch.addProperty("live_cell_x", liveCell.biomeRegionX);
                                    mismatch.addProperty("live_cell_z", liveCell.biomeRegionZ);
                                    Climate.TargetPoint previewTarget = sampler == null
                                        ? liveSampler.sample(quartX, previewQuartY, quartZ)
                                        : sampler.sample(quartX, previewQuartY, quartZ);
                                    Climate.TargetPoint liveTarget = liveSampler.sample(
                                        quartX, finishedQuartY, quartZ
                                    );
                                    mismatch.add("preview_target", target(previewTarget));
                                    mismatch.add("live_target", target(liveTarget));
                                    WorldgenPlan livePlan = ftfRandomState.plan();
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
            data.addProperty(
                "preview_surface_y_authority",
                this.useTileAuthority ? "prepared-preview-tile" : "ftf-preview-cell-model"
            );
            data.addProperty(
                "stored_surface_y_authority",
                this.useFinishedSurfaceAuthority ? "finished-world-surface-wg" : "prepared-preview-tile"
            );
            data.addProperty("climate_sampler_authority", this.useTileAuthority ? "prepared-preview-tile" : "generator-context");
            data.addProperty(
                "provider_authority",
                this.useFullProvider ? "selected-graph-with-request-patches" : "patch-provider"
            );
            JsonObject providerDomains = new JsonObject();
            providerDomainCounts.forEach(providerDomains::addProperty);
            data.add("selected_provider_domain_counts", providerDomains);
            data.addProperty("provider_selection_fallbacks", providerFallbacks);
            data.addProperty("selection_transition_count", selectionTransitions);
            JsonObject transitions = new JsonObject();
            selectionTransitionCounts.forEach(transitions::addProperty);
            data.add("selection_transition_counts", transitions);
            JsonArray decorators = new JsonArray();
            resolver.plan().selectionDecoration().orderedDecorators().forEach(value -> decorators.add(value.toString()));
            data.add("ordered_selection_decorators", decorators);
            JsonArray compositionStages = new JsonArray();
            resolver.plan().biomeComposition().stages().forEach(value -> compositionStages.add(value.id().toString()));
            data.add("pending_composition_stages", compositionStages);
            data.addProperty("normalized_candidate_count", resolver.plan().biomeComposition().entries().size());
            Map<String, Long> candidateNamespaces = new TreeMap<>();
            resolver.plan().biomeComposition().entries().forEach(entry -> entry.getSecond().unwrapKey().ifPresent(key ->
                candidateNamespaces.merge(key.location().getNamespace(), 1L, Long::sum)
            ));
            JsonObject namespaces = new JsonObject();
            candidateNamespaces.forEach(namespaces::addProperty);
            data.add("normalized_candidate_namespaces", namespaces);
            data.add("plan_diagnostics", resolver.plan().diagnostics().toJson());
            String generatorContextMode = this.useServerGeneratorContext
                ? "server-cached-context"
                : "uncached-editor-factor-4";
            data.addProperty("generator_context", generatorContextMode);
            data.addProperty("sampled_quart_columns", sampled);
            data.addProperty("mismatch_count", mismatches);
            data.addProperty("underground_preview_selection_count", undergroundPreviewSelections);
            data.addProperty("surface_height_mismatch_count", surfaceHeightMismatches);
            data.addProperty("maximum_surface_height_delta", maximumSurfaceHeightDelta);
            data.add("surface_height_mismatch_examples", surfaceHeightMismatchExamples);
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
