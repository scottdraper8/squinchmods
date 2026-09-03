package org.squinchmods.investigate.rtf;

import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.lang.ref.WeakReference;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import java.util.concurrent.locks.LockSupport;
import java.util.stream.IntStream;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.core.Holder;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.QuartPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Climate;
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
import raccoonman.reterraforged.world.worldgen.biome.BiomePreviewIntegration;
import raccoonman.reterraforged.world.worldgen.biome.BiomePreviewResolver;
import raccoonman.reterraforged.world.worldgen.cell.Cell;
import raccoonman.reterraforged.world.worldgen.cell.heightmap.Levels;
import raccoonman.reterraforged.world.worldgen.densityfunction.tile.Tile;

public final class UpstreamPreviewPerformanceProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:rtf-upstream-preview-performance", "2", PreviewPerformance::new);
    }

    private static final class PreviewPerformance implements ProbeExecution {
        private final int centerX;
        private final int centerZ;
        private final int zoom;
        private final int warmups;
        private final int repetitions;

        private PreviewPerformance(ProbeRequest request) {
            JsonObject config = request.config();
            this.centerX = integer(config, "center_x", 0);
            this.centerZ = integer(config, "center_z", 0);
            this.zoom = integer(config, "zoom", 150);
            this.warmups = integer(config, "warmups", 3);
            this.repetitions = integer(config, "repetitions", 12);
            if (this.zoom <= 0 || this.warmups < 0 || this.repetitions <= 0) {
                throw new IllegalArgumentException("zoom/repetitions must be positive and warmups non-negative");
            }
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            ServerLevel level = server.overworld();
            if (!((Object) level.getChunkSource().randomState() instanceof RTFRandomState randomState)
                    || randomState.preset() == null) {
                return ProbeResult.partial(
                    ProbePhase.PREDICTION, new JsonObject(), 0, 1,
                    "rtf-preset-or-random-state-unavailable"
                );
            }

            Preset preset = randomState.preset();
            List<RetiredOwner> retiredOwners = new ArrayList<>();
            long heapBefore = heapAfterGc();
            Sample cold = sample(server, level, preset, true, retiredOwners);
            for (int i = 0; i < this.warmups; i++) {
                sample(server, level, preset, false, retiredOwners);
            }
            long heapAfterWarmup = heapAfterGc();

            Sample[] samples = new Sample[this.repetitions];
            for (int i = 0; i < samples.length; i++) {
                samples[i] = sample(server, level, preset, false, retiredOwners);
            }
            long heapAfterRepeated = heapAfterGc();
            long retiredOwnersAlive = retiredOwners.stream().filter(RetiredOwner::alive).count();

            String expectedDigest = cold.digest();
            long mismatches = Arrays.stream(samples)
                .filter(sample -> !sample.digest().equals(expectedDigest))
                .count();

            JsonObject data = new JsonObject();
            data.addProperty("authority", "upstream-biome-preview-resolution-loop");
            data.addProperty("center_x", this.centerX);
            data.addProperty("center_z", this.centerZ);
            data.addProperty("zoom", this.zoom);
            data.addProperty("sampled_pixels", cold.sampledPixels());
            data.addProperty("warmups", this.warmups);
            data.addProperty("repetitions", this.repetitions);
            data.addProperty("cold_digest", expectedDigest);
            data.addProperty("repeat_digest_mismatch_count", mismatches);
            addSample(data, "cold", cold);
            addDistribution(data, "context", samples, Sample::contextNanos);
            addDistribution(data, "resolver", samples, Sample::resolverNanos);
            addDistribution(data, "tile", samples, Sample::tileNanos);
            addDistribution(data, "resolve", samples, Sample::resolveNanos);
            addDistribution(data, "full", samples, Sample::fullNanos);
            addDistribution(data, "full_allocated", samples, Sample::allocatedBytes);
            data.addProperty("heap_before_bytes", heapBefore);
            data.addProperty("heap_after_warmup_bytes", heapAfterWarmup);
            data.addProperty("heap_after_repeated_bytes", heapAfterRepeated);
            data.addProperty("heap_warmup_delta_bytes", heapAfterWarmup - heapBefore);
            data.addProperty("heap_repeat_delta_bytes", heapAfterRepeated - heapAfterWarmup);
            data.addProperty("retired_owner_reference_count", retiredOwners.size());
            data.addProperty("retired_owner_alive_after_gc", retiredOwnersAlive);
            data.addProperty("retired_context_alive_after_gc", alive(retiredOwners, "context"));
            data.addProperty("retired_resolver_alive_after_gc", alive(retiredOwners, "resolver"));
            data.addProperty("retired_tile_alive_after_gc", alive(retiredOwners, "tile"));
            return ProbeResult.complete(
                mismatches == 0 ? TerminalState.PASS : TerminalState.FAIL,
                ProbePhase.PREDICTION,
                data,
                cold.sampledPixels() * (long) (1 + this.warmups + this.repetitions)
            );
        }

        private Sample sample(
            net.minecraft.server.MinecraftServer server,
            ServerLevel level,
            Preset preset,
            boolean verifySerial,
            List<RetiredOwner> retiredOwners
        ) {
            long allocatedBefore = allocatedBytes();
            long fullStarted = System.nanoTime();

            long started = System.nanoTime();
            HolderLookup.Provider provider = preset.buildFullPatch(server.registryAccess());
            Preset prepared = provider.lookupOrThrow(RTFRegistries.PRESET)
                .getOrThrow(Preset.KEY).value();
            GeneratorContext context = GeneratorContext.makeUncached(
                prepared,
                provider.lookupOrThrow(RTFRegistries.NOISE),
                (int) level.getSeed(),
                4,
                0,
                6
            );
            retiredOwners.add(new RetiredOwner("context", new WeakReference<>(context)));
            long contextNanos = System.nanoTime() - started;

            started = System.nanoTime();
            BiomePreviewResolver resolver = BiomePreviewResolver.create(
                server.registryAccess(),
                provider,
                level.dimensionTypeRegistration(),
                level.getChunkSource().getGenerator(),
                prepared,
                context,
                level.getSeed()
            );
            retiredOwners.add(new RetiredOwner("resolver", new WeakReference<>(resolver)));
            long resolverNanos = System.nanoTime() - started;

            started = System.nanoTime();
            try (Tile tile = context.generator.generateZoomed(
                this.centerX, this.centerZ, this.zoom, true, () -> false
            ).join()) {
                retiredOwners.add(new RetiredOwner("tile", new WeakReference<>(tile)));
                long tileNanos = System.nanoTime() - started;
                started = System.nanoTime();
                Holder<Biome>[] parallel = resolve(resolver, tile, context.levels, true);
                long resolveNanos = System.nanoTime() - started;
                if (verifySerial) {
                    Holder<Biome>[] serial = resolve(resolver, tile, context.levels, false);
                    if (!Arrays.equals(parallel, serial)) {
                        throw new IllegalStateException("Upstream serial and parallel preview results differ");
                    }
                }
                long fullNanos = System.nanoTime() - fullStarted;
                return new Sample(
                    contextNanos,
                    resolverNanos,
                    tileNanos,
                    resolveNanos,
                    fullNanos,
                    allocatedBytes() - allocatedBefore,
                    parallel.length,
                    digest(parallel)
                );
            }
        }

        @SuppressWarnings("unchecked")
        private Holder<Biome>[] resolve(
            BiomePreviewResolver resolver,
            Tile tile,
            Levels levels,
            boolean parallel
        ) {
            int size = tile.getBlockSize().size();
            int border = tile.getBlockSize().border();
            int halfSize = size / 2;
            Holder<Biome>[] resolved = new Holder[size * size];
            Climate.Sampler sampler = resolver.tileClimateSampler(tile, this.centerX, this.centerZ, this.zoom);
            int rowBand = 16;
            int bands = (size + rowBand - 1) / rowBand;
            IntStream stream = IntStream.range(0, bands);
            if (parallel) {
                stream = stream.parallel();
            }
            try (BiomePreviewIntegration.Session ignored = resolver.openIntegrationSession()) {
                stream.forEach(band -> {
                    int startZ = band * rowBand;
                    int endZ = Math.min(size, startZ + rowBand);
                    for (int z = startZ; z < endZ; z++) {
                        int blockZ = this.centerZ + (z - halfSize) * this.zoom;
                        int row = z * size;
                        for (int x = 0; x < size; x++) {
                            int blockX = this.centerX + (x - halfSize) * this.zoom;
                            Cell cell = tile.getCellRaw(border + x, border + z);
                            resolved[row + x] = resolver.resolveQuart(
                                QuartPos.fromBlock(blockX),
                                QuartPos.fromBlock(surfaceY(cell, levels)),
                                QuartPos.fromBlock(blockZ),
                                sampler
                            );
                        }
                    }
                });
            }
            return resolved;
        }
    }

    private static int surfaceY(Cell cell, Levels levels) {
        int minY = -levels.worldDepth;
        int maxY = Math.max(minY, levels.terrainScaleFactor - 1);
        return Math.max(minY, Math.min(maxY, levels.scale(cell.height)));
    }

    private static int integer(JsonObject config, String key, int fallback) {
        return config.has(key) ? config.get(key).getAsInt() : fallback;
    }

    private static long heapAfterGc() {
        MemoryMXBean memory = ManagementFactory.getMemoryMXBean();
        long previous = Long.MAX_VALUE;
        long current = memory.getHeapMemoryUsage().getUsed();
        for (int i = 0; i < 5 && current < previous; i++) {
            previous = current;
            System.gc();
            LockSupport.parkNanos(50_000_000L);
            current = memory.getHeapMemoryUsage().getUsed();
        }
        return current;
    }

    private static long allocatedBytes() {
        com.sun.management.ThreadMXBean bean =
            (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean();
        if (!bean.isThreadAllocatedMemorySupported()) {
            return -1L;
        }
        long total = 0L;
        for (long value : bean.getThreadAllocatedBytes(bean.getAllThreadIds())) {
            if (value >= 0L) {
                total += value;
            }
        }
        return total;
    }

    private static long alive(List<RetiredOwner> owners, String type) {
        return owners.stream().filter(owner -> owner.type().equals(type) && owner.alive()).count();
    }

    private static String digest(Holder<Biome>[] values) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (Holder<Biome> value : values) {
                String id = value.unwrapKey().map(key -> key.location().toString())
                    .orElseGet(() -> value.value().toString());
                digest.update(id.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                digest.update((byte) 0);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static void addSample(JsonObject data, String prefix, Sample sample) {
        data.addProperty(prefix + "_context_millis", millis(sample.contextNanos()));
        data.addProperty(prefix + "_resolver_millis", millis(sample.resolverNanos()));
        data.addProperty(prefix + "_tile_millis", millis(sample.tileNanos()));
        data.addProperty(prefix + "_resolve_millis", millis(sample.resolveNanos()));
        data.addProperty(prefix + "_full_millis", millis(sample.fullNanos()));
        data.addProperty(prefix + "_allocated_bytes", sample.allocatedBytes());
    }

    private static void addDistribution(
        JsonObject data,
        String prefix,
        Sample[] samples,
        Metric metric
    ) {
        long[] values = Arrays.stream(samples).mapToLong(metric::value).sorted().toArray();
        JsonArray raw = new JsonArray();
        for (long value : values) {
            raw.add(prefix.equals("full_allocated") ? value : millis(value));
        }
        data.add(prefix + "_samples", raw);
        if (prefix.equals("full_allocated")) {
            data.addProperty(prefix + "_median_bytes", percentile(values, 0.5D));
            data.addProperty(prefix + "_p95_bytes", percentile(values, 0.95D));
        } else {
            data.addProperty(prefix + "_median_millis", millis(percentile(values, 0.5D)));
            data.addProperty(prefix + "_p95_millis", millis(percentile(values, 0.95D)));
        }
    }

    private static long percentile(long[] sorted, double percentile) {
        return sorted[(int) Math.ceil(percentile * sorted.length) - 1];
    }

    private static double millis(long nanos) {
        return nanos / 1_000_000.0D;
    }

    @FunctionalInterface
    private interface Metric {
        long value(Sample sample);
    }

    private record RetiredOwner(String type, WeakReference<Object> reference) {
        private boolean alive() {
            return this.reference.get() != null;
        }
    }

    private record Sample(
        long contextNanos,
        long resolverNanos,
        long tileNanos,
        long resolveNanos,
        long fullNanos,
        long allocatedBytes,
        int sampledPixels,
        String digest
    ) {
    }
}
