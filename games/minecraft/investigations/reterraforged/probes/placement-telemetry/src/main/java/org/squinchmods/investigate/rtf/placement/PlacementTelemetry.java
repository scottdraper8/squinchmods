package org.squinchmods.investigate.rtf.placement;

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
public final class PlacementTelemetry {
    private static final ConcurrentHashMap<Key, Stats> STATS = new ConcurrentHashMap<>();
    private static final ThreadLocal<Deque<Run>> ACTIVE = ThreadLocal.withInitial(ArrayDeque::new);
    private static final ThreadLocal<BlockPos> LAST_SECTION_POSITION = new ThreadLocal<>();
    private static final ThreadMXBean THREADS = ManagementFactory.getThreadMXBean();

    private PlacementTelemetry() {
    }

    public static void begin(PlacedFeature feature, PlacementContext context, BlockPos origin) {
        String featureId = featureId(feature, context);
        long chunk = new ChunkPos(origin).toLong();
        Stats stats = STATS.computeIfAbsent(new Key(featureId, chunk), ignored -> new Stats());
        stats.invocations.increment();
        ACTIVE.get().push(new Run(featureId, chunk, cpuTime(), origin.immutable()));
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
        Run root = stack.peekLast();
        if (root != null && root != run) {
            Stats rootStats = STATS.computeIfAbsent(
                new Key(root.featureId(), root.chunk()), ignored -> new Stats()
            );
            rootStats.descendantInvocations.increment();
            if (successful) {
                rootStats.successfulDescendantInvocations.increment();
                add(rootStats.descendantSuccessRelativeX, run.origin().getX() - ChunkPos.getX(root.chunk()) * 16);
                add(rootStats.descendantSuccessRelativeZ, run.origin().getZ() - ChunkPos.getZ(root.chunk()) * 16);
            }
        }
        if (stack.isEmpty()) {
            ACTIVE.remove();
            LAST_SECTION_POSITION.remove();
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
        Run run = stack.peekLast();
        Stats stats = STATS.computeIfAbsent(new Key(run.featureId(), run.chunk()), ignored -> new Stats());
        stats.blockWrites.increment();
        stats.blockWriteByY.computeIfAbsent(position.getY(), ignored -> new LongAdder()).increment();
        add(stats.blockWriteRelativeX, position.getX() - ChunkPos.getX(run.chunk()) * 16);
        add(stats.blockWriteRelativeZ, position.getZ() - ChunkPos.getZ(run.chunk()) * 16);
        stats.writtenBlocks.computeIfAbsent(
            MinecraftProbeHelpers.blockId(state), ignored -> new LongAdder()
        ).increment();
    }

    public static void randomOffset(BlockPos origin, BlockPos output) {
        Deque<Run> stack = ACTIVE.get();
        if (stack.isEmpty()) {
            return;
        }
        Run root = stack.peekLast();
        Stats stats = STATS.computeIfAbsent(new Key(root.featureId(), root.chunk()), ignored -> new Stats());
        stats.randomOffsetOutputs.increment();
        add(stats.randomOffsetDeltaX, output.getX() - origin.getX());
        add(stats.randomOffsetDeltaZ, output.getZ() - origin.getZ());
        add(stats.randomOffsetOutputRelativeX, output.getX() - ChunkPos.getX(root.chunk()) * 16);
        add(stats.randomOffsetOutputRelativeZ, output.getZ() - ChunkPos.getZ(root.chunk()) * 16);
        if (!new ChunkPos(origin).equals(new ChunkPos(output))) {
            stats.randomOffsetOutsideOriginChunk.increment();
        }
        if (new ChunkPos(output).toLong() != root.chunk()) {
            stats.randomOffsetOutsideRootChunk.increment();
        }
    }

    public static void worldGenWrite(BlockPos position, BlockState state) {
        Deque<Run> stack = ACTIVE.get();
        if (stack.isEmpty()) {
            return;
        }
        Run root = stack.peekLast();
        Stats stats = STATS.computeIfAbsent(new Key(root.featureId(), root.chunk()), ignored -> new Stats());
        stats.worldGenWrites.increment();
        add(stats.worldGenWriteRelativeX, position.getX() - ChunkPos.getX(root.chunk()) * 16);
        add(stats.worldGenWriteRelativeZ, position.getZ() - ChunkPos.getZ(root.chunk()) * 16);
        stats.worldGenWrittenPositions.put(position.asLong(), MinecraftProbeHelpers.blockId(state));
    }

    public static void sectionPosition(BlockPos position) {
        if (!ACTIVE.get().isEmpty()) {
            LAST_SECTION_POSITION.set(position.immutable());
        }
    }

    /**
     * Records a write made directly through a chunk section. Vanilla's
     * standard OreFeature uses this path instead of WorldGenRegion.setBlock.
     * BulkSectionAccess supplies the world-space position immediately before
     * vanilla writes through the section.
     */
    public static void blockWrite(BlockState state) {
        Deque<Run> stack = ACTIVE.get();
        if (stack.isEmpty()) {
            return;
        }
        BlockPos position = LAST_SECTION_POSITION.get();
        if (position == null) {
            Run run = stack.peekLast();
            Stats stats = STATS.computeIfAbsent(new Key(run.featureId(), run.chunk()), ignored -> new Stats());
            stats.blockWrites.increment();
            stats.writtenBlocks.computeIfAbsent(
                MinecraftProbeHelpers.blockId(state), ignored -> new LongAdder()
            ).increment();
            return;
        }
        blockWrite(position, state);
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

    private static void add(ConcurrentHashMap<Integer, LongAdder> values, int key) {
        values.computeIfAbsent(key, ignored -> new LongAdder()).increment();
    }

    private record Run(String featureId, long chunk, long startedCpuNanos, BlockPos origin) {
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
        public final LongAdder descendantInvocations = new LongAdder();
        public final LongAdder successfulDescendantInvocations = new LongAdder();
        public final LongAdder randomOffsetOutputs = new LongAdder();
        public final LongAdder randomOffsetOutsideOriginChunk = new LongAdder();
        public final LongAdder randomOffsetOutsideRootChunk = new LongAdder();
        public final LongAdder worldGenWrites = new LongAdder();
        public final ConcurrentHashMap<Integer, LongAdder> heightByY = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> biomePassByY = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> blockWriteByY = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> descendantSuccessRelativeX = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> descendantSuccessRelativeZ = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> randomOffsetDeltaX = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> randomOffsetDeltaZ = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> randomOffsetOutputRelativeX = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> randomOffsetOutputRelativeZ = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> blockWriteRelativeX = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> blockWriteRelativeZ = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> worldGenWriteRelativeX = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> worldGenWriteRelativeZ = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Long, String> worldGenWrittenPositions = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<String, LongAdder> passedBiomes = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<String, LongAdder> writtenBlocks = new ConcurrentHashMap<>();
    }
}
