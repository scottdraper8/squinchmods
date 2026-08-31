package org.squinchmods.investigate.rtf.insquare;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.placement.PlacementContext;

/** External hook-side aggregation; no instrumentation is compiled into FreeTerraForged. */
public final class CaveInteractionTelemetry {
    private static final ConcurrentHashMap<Key, Stats> STATS = new ConcurrentHashMap<>();
    private static final ThreadLocal<ActiveRescue> ACTIVE_RESCUE = new ThreadLocal<>();
    private static final ThreadLocal<PendingRescuedPlacement> PENDING_RESCUED_PLACEMENT = new ThreadLocal<>();
    private static final ThreadLocal<Stats> ACTIVE_RESCUED_FEATURE = new ThreadLocal<>();

    private CaveInteractionTelemetry() {
    }

    public static void inSquareOutput(
        PlacementContext context,
        BlockPos origin,
        BlockPos output
    ) {
        context.topFeature().ifPresent(feature -> {
            Stats stats = stats(feature, context, origin);
            int dx = output.getX() - origin.getX();
            int dz = output.getZ() - origin.getZ();
            stats.inSquareOutputs.increment();
            stats.inSquareDx.computeIfAbsent(dx, ignored -> new LongAdder()).increment();
            stats.inSquareDz.computeIfAbsent(dz, ignored -> new LongAdder()).increment();
            if (dx < 2 || dx > 13 || dz < 2 || dz > 13) {
                stats.inSquareEdgeOutputs.increment();
            }
            if (dx < 0 || dx > 15 || dz < 0 || dz > 15) {
                stats.inSquareOutsideVanillaChunk.increment();
            }
        });
    }

    public static void inSquareCall(PlacementContext context, BlockPos origin) {
        context.topFeature().ifPresent(feature -> stats(feature, context, origin).inSquareCalls.increment());
    }

    public static void rescueEntry(
        PlacedFeature feature,
        PlacementContext context,
        BlockPos originalOrigin
    ) {
        Stats stats = stats(feature, context, originalOrigin);
        stats.failedScanRescueEntries.increment();
        stats.rescueEntryY.computeIfAbsent(originalOrigin.getY(), ignored -> new LongAdder()).increment();
        int localX = Math.floorMod(originalOrigin.getX(), 16);
        int localZ = Math.floorMod(originalOrigin.getZ(), 16);
        stats.rescueLocalX.computeIfAbsent(localX, ignored -> new LongAdder()).increment();
        stats.rescueLocalZ.computeIfAbsent(localZ, ignored -> new LongAdder()).increment();
        if (localX < 2 || localX > 13 || localZ < 2 || localZ > 13) {
            stats.rescueEdgeColumns.increment();
        }
        ACTIVE_RESCUE.set(new ActiveRescue(stats, originalOrigin.getY(), System.nanoTime()));
    }

    public static void budgetDecision(boolean scheduled) {
        ActiveRescue active = ACTIVE_RESCUE.get();
        if (active == null) {
            return;
        }
        active.budgetSeen = true;
        active.scheduled = scheduled;
        if (scheduled) {
            active.stats.scheduledColumnSearches.increment();
            active.stats.scheduledOriginY
                .computeIfAbsent(active.originY, ignored -> new LongAdder())
                .increment();
        } else {
            active.stats.budgetSkippedEntries.increment();
        }
    }

    public static void scanStart() {
        ActiveRescue active = ACTIVE_RESCUE.get();
        if (active == null) {
            return;
        }
        active.physicalScan = true;
        active.scanStartNanos = System.nanoTime();
        active.scanning = true;
        active.stats.physicalColumnScans.increment();
    }

    public static void eligibilityCheck() {
        ActiveRescue active = ACTIVE_RESCUE.get();
        if (active == null) {
            return;
        }
        if (active.scanning) {
            active.stats.scanPredicateChecks.increment();
        } else {
            active.stats.surfaceRechecks.increment();
        }
    }

    public static void scanEnd(long[] surfaces) {
        ActiveRescue active = ACTIVE_RESCUE.get();
        if (active == null) {
            return;
        }
        active.scanning = false;
        active.stats.scanNanos.add(System.nanoTime() - active.scanStartNanos);
        active.stats.discoveredSurfaces.add(surfaces.length);
    }

    public static void rescueResult(Optional<BlockPos> rescued) {
        ActiveRescue active = ACTIVE_RESCUE.get();
        if (active == null) {
            return;
        }
        if (!active.budgetSeen) {
            active.stats.preBudgetRejectedEntries.increment();
        } else if (active.scheduled && !active.physicalScan) {
            active.stats.cachedColumnReuses.increment();
        }
        if (rescued.isPresent()) {
            active.stats.rescueSuccesses.increment();
            active.stats.rescueY.computeIfAbsent(rescued.get().getY(), ignored -> new LongAdder()).increment();
            active.stats.rescuePositions
                .computeIfAbsent(rescued.get().asLong(), ignored -> new LongAdder())
                .increment();
            PENDING_RESCUED_PLACEMENT.set(new PendingRescuedPlacement(active.stats, rescued.get()));
        }
        active.stats.rescueNanos.add(System.nanoTime() - active.entryNanos);
        ACTIVE_RESCUE.remove();
    }

    public static void rescuedBiomeResult(BlockPos position, boolean passed) {
        PendingRescuedPlacement pending = PENDING_RESCUED_PLACEMENT.get();
        if (pending == null) {
            return;
        }
        PENDING_RESCUED_PLACEMENT.remove();
        BlockPos target = pending.target();
        if (position.getX() != target.getX()
            || position.getZ() != target.getZ()
            || Math.abs(position.getY() - target.getY()) > 1) {
            pending.stats().rescuedPipelineMismatches.increment();
            return;
        }
        pending.stats().rescuedBiomeChecks.increment();
        if (passed) {
            pending.stats().rescuedBiomePasses.increment();
            PENDING_RESCUED_PLACEMENT.set(new PendingRescuedPlacement(pending.stats(), position.immutable()));
        }
    }

    public static void rescuedConfiguredFeatureStart(BlockPos position) {
        PendingRescuedPlacement pending = PENDING_RESCUED_PLACEMENT.get();
        if (pending == null || !pending.target().equals(position)) {
            return;
        }
        PENDING_RESCUED_PLACEMENT.remove();
        pending.stats().rescuedConfiguredFeatureCalls.increment();
        ACTIVE_RESCUED_FEATURE.set(pending.stats());
    }

    public static void rescuedConfiguredFeatureEnd(boolean successful) {
        Stats stats = ACTIVE_RESCUED_FEATURE.get();
        if (stats == null) {
            return;
        }
        if (successful) {
            stats.rescuedConfiguredFeatureSuccesses.increment();
        }
        ACTIVE_RESCUED_FEATURE.remove();
    }

    public static Map<Key, Stats> stats() {
        return Map.copyOf(STATS);
    }

    private static Stats stats(PlacedFeature feature, PlacementContext context, BlockPos position) {
        Registry<PlacedFeature> registry = context.getLevel().registryAccess()
            .registryOrThrow(Registries.PLACED_FEATURE);
        ResourceLocation id = registry.getKey(feature);
        String featureId = id == null
            ? "unregistered@" + Integer.toHexString(System.identityHashCode(feature))
            : id.toString();
        return STATS.computeIfAbsent(
            new Key(featureId, new ChunkPos(position).toLong()),
            ignored -> new Stats()
        );
    }

    public record Key(String featureId, long chunk) {
    }

    private static final class ActiveRescue {
        private final Stats stats;
        private final int originY;
        private final long entryNanos;
        private long scanStartNanos;
        private boolean budgetSeen;
        private boolean scheduled;
        private boolean physicalScan;
        private boolean scanning;

        private ActiveRescue(Stats stats, int originY, long entryNanos) {
            this.stats = stats;
            this.originY = originY;
            this.entryNanos = entryNanos;
        }
    }

    private record PendingRescuedPlacement(Stats stats, BlockPos target) {
    }

    public static final class Stats {
        public final LongAdder inSquareCalls = new LongAdder();
        public final LongAdder inSquareOutputs = new LongAdder();
        public final LongAdder inSquareEdgeOutputs = new LongAdder();
        public final LongAdder inSquareOutsideVanillaChunk = new LongAdder();
        public final LongAdder failedScanRescueEntries = new LongAdder();
        public final LongAdder preBudgetRejectedEntries = new LongAdder();
        public final LongAdder budgetSkippedEntries = new LongAdder();
        public final LongAdder scheduledColumnSearches = new LongAdder();
        public final LongAdder physicalColumnScans = new LongAdder();
        public final LongAdder cachedColumnReuses = new LongAdder();
        public final LongAdder scanPredicateChecks = new LongAdder();
        public final LongAdder surfaceRechecks = new LongAdder();
        public final LongAdder discoveredSurfaces = new LongAdder();
        public final LongAdder rescueNanos = new LongAdder();
        public final LongAdder scanNanos = new LongAdder();
        public final LongAdder rescueSuccesses = new LongAdder();
        public final LongAdder rescuedBiomeChecks = new LongAdder();
        public final LongAdder rescuedBiomePasses = new LongAdder();
        public final LongAdder rescuedConfiguredFeatureCalls = new LongAdder();
        public final LongAdder rescuedConfiguredFeatureSuccesses = new LongAdder();
        public final LongAdder rescuedPipelineMismatches = new LongAdder();
        public final LongAdder rescueEdgeColumns = new LongAdder();
        public final ConcurrentHashMap<Integer, LongAdder> inSquareDx = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> inSquareDz = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> rescueLocalX = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> rescueLocalZ = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> rescueEntryY = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> scheduledOriginY = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Integer, LongAdder> rescueY = new ConcurrentHashMap<>();
        public final ConcurrentHashMap<Long, LongAdder> rescuePositions = new ConcurrentHashMap<>();
    }
}
