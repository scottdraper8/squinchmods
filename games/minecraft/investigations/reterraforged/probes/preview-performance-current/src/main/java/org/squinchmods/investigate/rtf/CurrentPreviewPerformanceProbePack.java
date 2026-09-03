package org.squinchmods.investigate.rtf;

import java.lang.management.ManagementFactory;
import java.util.HashSet;
import java.util.Set;

import com.google.gson.JsonObject;

import net.minecraft.core.Holder;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.QuartPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.dimension.LevelStem;
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
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenFingerprints;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlan;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlans;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenContributionRevision;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenCapabilityDiscovery;

/** Stage and allocation breakdown for the compatibility runtime's preview query. */
public final class CurrentPreviewPerformanceProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-current-preview-performance", "1", PreviewPerformance::new);
    }

    private static final class PreviewPerformance implements ProbeExecution {
        private final int centerX;
        private final int centerZ;
        private final int zoom;

        private PreviewPerformance(ProbeRequest request) {
            JsonObject config = request.config();
            this.centerX = config.has("center_x") ? config.get("center_x").getAsInt() : 0;
            this.centerZ = config.has("center_z") ? config.get("center_z").getAsInt() : 0;
            this.zoom = config.has("zoom") ? config.get("zoom").getAsInt() : 150;
            if (this.zoom <= 0) {
                throw new IllegalArgumentException("zoom must be positive");
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            Object randomState = level.getChunkSource().randomState();
            if (!(randomState instanceof RTFRandomState rtfRandomState) || rtfRandomState.preset() == null) {
                return ProbeResult.partial(
                    ProbePhase.PREDICTION, new JsonObject(), 0, 1,
                    "rtf-preset-or-random-state-unavailable"
                );
            }
            Preset preset = rtfRandomState.preset();
            long started = System.nanoTime();
            HolderLookup.Provider provider = preset.buildPreviewLookups(server.registryAccess());
            try (GeneratorContext context = GeneratorContext.makeUncached(
                preset,
                provider.lookupOrThrow(RTFRegistries.NOISE),
                (int) level.getSeed(),
                4,
                0,
                6
            )) {
            long contextNanos = System.nanoTime() - started;

            started = System.nanoTime();
			var providers = WorldgenCapabilityDiscovery.discover(getClass().getClassLoader());
			var contributions = WorldgenContributionRevision.snapshot(LevelStem.OVERWORLD, providers);
			long capabilityNanos = System.nanoTime() - started;

			started = System.nanoTime();
            try (
                BiomePreviewResolver resolver = BiomePreviewResolver.create(
                    server.registryAccess(),
                    provider,
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
                )
            ) {
                long resolverNanos = System.nanoTime() - started;
                started = System.nanoTime();
                try (Tile tile = context.generator.generateZoomed(
                    this.centerX, this.centerZ, this.zoom, true, () -> false
                ).join()) {
                    long tileNanos = System.nanoTime() - started;
					return measure(
						resolver, tile, context, contextNanos, capabilityNanos, resolverNanos, tileNanos
					);
                }
            }
            }
        }

        @SuppressWarnings("unchecked")
        private ProbeResult measure(
            BiomePreviewResolver resolver,
            Tile tile,
            GeneratorContext context,
            long contextNanos,
			long capabilityNanos,
            long resolverNanos,
            long tileNanos
        ) {
            int size = tile.getBlockSize().size();
            int count = size * size;
            int border = tile.getBlockSize().border();
            int halfSize = size / 2;
            int[] quartXs = new int[count];
            int[] quartYs = new int[count];
            int[] quartZs = new int[count];
            long[] cellXs = new long[count];
            long[] cellZs = new long[count];
            Climate.TargetPoint[] targets = new Climate.TargetPoint[count];
            WorldgenPlans.SpatialResult[] spatial = new WorldgenPlans.SpatialResult[count];
            WorldgenPlans.ProviderResult[] providers = new WorldgenPlans.ProviderResult[count];
            Holder<Biome>[] decorated = new Holder[count];
            Holder<Biome>[] serial = new Holder[count];
            BiomePreviewResolver.TileBiomeRequest request = resolver.tileRequest(
                tile, this.centerX, this.centerZ, this.zoom
            );
            Climate.Sampler sampler = request.climateSampler();
            WorldgenPlan plan = resolver.plan();

            for (int z = 0; z < size; z++) {
                int blockZ = this.centerZ + (z - halfSize) * this.zoom;
                int row = z * size;
                for (int x = 0; x < size; x++) {
                    int blockX = this.centerX + (x - halfSize) * this.zoom;
                    int index = row + x;
                    Cell cell = tile.getCellRaw(border + x, border + z);
                    int minY = -context.levels.worldDepth;
                    int maxY = Math.max(minY, context.levels.terrainScaleFactor - 1);
                    int surfaceY = Math.max(minY, Math.min(maxY, context.levels.scale(cell.height)));
                    quartXs[index] = QuartPos.fromBlock(blockX);
                    quartYs[index] = QuartPos.fromBlock(surfaceY);
                    quartZs[index] = QuartPos.fromBlock(blockZ);
                    cellXs[index] = cell.biomeRegionX;
                    cellZs[index] = cell.biomeRegionZ;
                }
            }

            Stage samplerStage = stage(() -> {
                for (int index = 0; index < count; index++) {
                    targets[index] = sampler.sample(quartXs[index], quartYs[index], quartZs[index]);
                }
            });
            WorldgenPlans.SpatialResolver spatialResolver = plan.spatialOwnership().resolver().orElseThrow();
            Stage spatialStage = stage(() -> {
                for (int index = 0; index < count; index++) {
                    spatial[index] = spatialResolver.resolve(cellXs[index], cellZs[index]);
                }
            });
            Stage providerStage = stage(() -> {
                for (int index = 0; index < count; index++) {
                    providers[index] = plan.providerSelection()
                        .resolve(spatial[index].domain(), targets[index])
                        .orElseThrow();
                }
            });
            Stage decorationStage = stage(() -> {
                for (int index = 0; index < count; index++) {
                    decorated[index] = plan.selectionDecoration().apply(
                        providers[index], spatial[index], targets[index],
                        quartXs[index], quartYs[index], quartZs[index], sampler, context
                    );
                }
            });
            Stage serialStage = stage(() -> {
                for (int index = 0; index < count; index++) {
                    serial[index] = request.resolveQuart(quartXs[index], quartYs[index], quartZs[index]);
                }
            });
            long parallelStarted = System.nanoTime();
            BiomePreviewResolver.ResolvedTile parallel = resolver.resolveSurfaceTile(
                tile, this.centerX, this.centerZ, this.zoom, context.levels, () -> false
            );
            long parallelNanos = System.nanoTime() - parallelStarted;

            long decompositionMismatches = 0;
            long parallelMismatches = 0;
            Set<CellKey> uniqueCells = new HashSet<>();
            for (int index = 0; index < count; index++) {
                uniqueCells.add(new CellKey(cellXs[index], cellZs[index]));
                if (!decorated[index].equals(serial[index])) {
                    decompositionMismatches++;
                }
                if (!serial[index].equals(parallel.biomeAt(index % size, index / size))) {
                    parallelMismatches++;
                }
            }

            JsonObject data = new JsonObject();
            data.addProperty("authority", "compatibility-preview-stage-breakdown");
            data.addProperty("center_x", this.centerX);
            data.addProperty("center_z", this.centerZ);
            data.addProperty("zoom", this.zoom);
            data.addProperty("sampled_pixels", count);
            data.addProperty("unique_ftf_cells", uniqueCells.size());
            data.addProperty("provider_domains", plan.providerSelection().providers().size());
            data.addProperty("provider_candidates", plan.providerSelection().providers().stream()
                .mapToInt(domain -> domain.candidates().values().size()).sum());
            data.addProperty("decorator_stages", plan.selectionDecoration().stages().size());
            data.addProperty("context_millis", millis(contextNanos));
			data.addProperty("capability_millis", millis(capabilityNanos));
            data.addProperty("resolver_millis", millis(resolverNanos));
            data.addProperty("tile_millis", millis(tileNanos));
            addStage(data, "sampler", samplerStage);
            addStage(data, "spatial", spatialStage);
            addStage(data, "provider", providerStage);
            addStage(data, "decoration", decorationStage);
            addStage(data, "full_serial", serialStage);
            data.addProperty("full_parallel_millis", millis(parallelNanos));
            data.addProperty("decomposition_mismatch_count", decompositionMismatches);
            data.addProperty("parallel_mismatch_count", parallelMismatches);
            return ProbeResult.complete(
                decompositionMismatches == 0 && parallelMismatches == 0
                    ? TerminalState.PASS
                    : TerminalState.FAIL,
                ProbePhase.PREDICTION,
                data,
                count
            );
        }
    }

    private static Stage stage(Runnable action) {
        com.sun.management.ThreadMXBean bean = (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean();
        long thread = Thread.currentThread().threadId();
        long beforeBytes = bean.isThreadAllocatedMemorySupported() ? bean.getThreadAllocatedBytes(thread) : -1L;
        long before = System.nanoTime();
        action.run();
        long nanos = System.nanoTime() - before;
        long afterBytes = beforeBytes >= 0 ? bean.getThreadAllocatedBytes(thread) : -1L;
        return new Stage(nanos, beforeBytes >= 0 ? afterBytes - beforeBytes : -1L);
    }

    private static void addStage(JsonObject data, String name, Stage stage) {
        data.addProperty(name + "_millis", millis(stage.nanos()));
        data.addProperty(name + "_allocated_bytes", stage.allocatedBytes());
    }

    private static double millis(long nanos) {
        return nanos / 1_000_000.0D;
    }

    private record CellKey(long x, long z) {
    }

    private record Stage(long nanos, long allocatedBytes) {
    }
}
