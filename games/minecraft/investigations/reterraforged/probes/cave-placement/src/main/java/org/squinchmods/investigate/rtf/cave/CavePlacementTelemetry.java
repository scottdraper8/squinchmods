package org.squinchmods.investigate.rtf.cave;

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.placement.PlacementContext;
import org.squinchmods.investigate.MinecraftProbeHelpers;

/** Hook-side aggregation only. Selection, bands, filters, and output limits remain probe config. */
public final class CavePlacementTelemetry {
    private static final ConcurrentHashMap<Key, Stats> STATS = new ConcurrentHashMap<>();
    private static final ThreadLocal<Deque<Run>> ACTIVE = ThreadLocal.withInitial(ArrayDeque::new);
    private static final ThreadMXBean THREADS = ManagementFactory.getThreadMXBean();

    private CavePlacementTelemetry() {
    }

    public static void begin(PlacedFeature feature, PlacementContext context, BlockPos origin) {
        String featureId = featureId(feature, context);
        long chunk = new ChunkPos(origin).toLong();
        Stats stats = STATS.computeIfAbsent(new Key(featureId, chunk), ignored -> new Stats());
        stats.invocations.increment();
        ACTIVE.get().push(new Run(featureId, chunk, cpuTime()));
    }

    public static void end(boolean successful) {
        Deque<Run> stack = ACTIVE.get();
        if (stack.isEmpty()) {
            return;
        }
        Run run = stack.pop();
        Stats stats = STATS.computeIfAbsent(new Key(run.featureId(), run.chunk()), ignored -> new Stats());
        stats.cpuNanos.add(Math.max(0L, cpuTime() - run.startedCpuNanos()));
        if (successful) {
            stats.successfulInvocations.increment();
        }
        if (stack.isEmpty()) {
            ACTIVE.remove();
        }
    }

    public static void countCandidate(int count) {
        Stats stats = activeStats();
        if (stats != null) {
            stats.countPlacementCalls.increment();
            stats.countCandidates.add(count);
        }
    }

    public static void heightCandidate(PlacementContext context, BlockPos position) {
        String featureId = context.topFeature().map(feature -> featureId(feature, context)).orElse(null);
        if (featureId == null) {
            return;
        }
        long chunk = new ChunkPos(position).toLong();
        Stats stats = STATS.computeIfAbsent(new Key(featureId, chunk), ignored -> new Stats());
        stats.heightCandidates.increment();
        stats.heightByY.computeIfAbsent(position.getY(), ignored -> new LongAdder()).increment();
    }

    public static void biomeCheck(PlacementContext context, BlockPos position, boolean passed) {
        String featureId = context.topFeature().map(feature -> featureId(feature, context)).orElse(null);
        if (featureId == null) {
            return;
        }
        long chunk = new ChunkPos(position).toLong();
        Stats stats = STATS.computeIfAbsent(new Key(featureId, chunk), ignored -> new Stats());
        stats.biomeChecks.increment();
        if (passed) {
            stats.biomePasses.increment();
            stats.biomePassByY.computeIfAbsent(position.getY(), ignored -> new LongAdder()).increment();
            Holder<Biome> biome = context.getLevel().getBiome(position);
            stats.passedBiomes.computeIfAbsent(
                MinecraftProbeHelpers.biomeId(biome), ignored -> new LongAdder()
            ).increment();
        }
    }

    public static void blockWrite(BlockPos position, BlockState state) {
        Deque<Run> stack = ACTIVE.get();
        if (stack.isEmpty()) {
            return;
        }
        Run run = stack.peek();
        long chunk = new ChunkPos(position).toLong();
        Stats stats = STATS.computeIfAbsent(new Key(run.featureId(), chunk), ignored -> new Stats());
        stats.blockWrites.increment();
        stats.blockWriteByY.computeIfAbsent(position.getY(), ignored -> new LongAdder()).increment();
        stats.writtenBlocks.computeIfAbsent(
            MinecraftProbeHelpers.blockId(state), ignored -> new LongAdder()
        ).increment();
    }

    public static Map<Key, Stats> stats() {
        return Map.copyOf(STATS);
    }

    private static Stats activeStats() {
        Deque<Run> stack = ACTIVE.get();
        if (stack.isEmpty()) {
            return null;
        }
        Run run = stack.peek();
        return STATS.computeIfAbsent(new Key(run.featureId(), run.chunk()), ignored -> new Stats());
    }

    private static String featureId(PlacedFeature feature, PlacementContext context) {
        Registry<PlacedFeature> registry = context.getLevel().registryAccess()
            .registryOrThrow(Registries.PLACED_FEATURE);
        ResourceLocation id = registry.getKey(feature);
        return id == null
            ? "unregistered@" + Integer.toHexString(System.identityHashCode(feature))
            : id.toString();
    }

    private static long cpuTime() {
        return THREADS.isCurrentThreadCpuTimeSupported() ? THREADS.getCurrentThreadCpuTime() : 0L;
    }

    public record Key(String featureId, long chunk) {
    }

    private record Run(String featureId, long chunk, long startedCpuNanos) {
    }

    public static final class Stats {
        public final LongAdder invocations = new LongAdder();
        public final LongAdder successfulInvocations = new LongAdder();
        public final LongAdder cpuNanos = new LongAdder();
        public final LongAdder countPlacementCalls = new LongAdder();
        public final LongAdder countCandidates = new LongAdder();
        public final LongAdder heightCandidates = new LongAdder();
        public final LongAdder biomeChecks = new LongAdder();
        public final LongAdder biomePasses = new LongAdder();
        public final LongAdder blockWrites = new LongAdder();
        public final ConcurrentHashMap<Integer, LongAdder> heightByY = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> biomePassByY = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> blockWriteByY = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<String, LongAdder> passedBiomes = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<String, LongAdder> writtenBlocks = new ConcurrentHashMap<>();
    }
}
