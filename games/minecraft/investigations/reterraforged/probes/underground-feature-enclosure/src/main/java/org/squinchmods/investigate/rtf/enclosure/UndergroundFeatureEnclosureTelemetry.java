package org.squinchmods.investigate.rtf.enclosure;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.ChunkPos;

/** External hook-side state; no instrumentation is compiled into ReTerraForged. */
public final class UndergroundFeatureEnclosureTelemetry {
    private static final int EXAMPLE_LIMIT = 32;
    private static final ConcurrentHashMap<Long, Stats> STATS = new ConcurrentHashMap<>();

    private UndergroundFeatureEnclosureTelemetry() {
    }

    public static void record(BlockPos position, boolean accepted) {
        Stats stats = STATS.computeIfAbsent(new ChunkPos(position).toLong(), ignored -> new Stats());
        stats.checked.increment();
        if (accepted) {
            stats.accepted.increment();
        } else {
            stats.rejected.increment();
        }
        synchronized (stats.examples) {
            if (stats.examples.size() < EXAMPLE_LIMIT) {
                stats.examples.add(new Example(position.immutable(), accepted));
            }
        }
    }

    public static Map<Long, Stats> stats() {
        return Map.copyOf(STATS);
    }

    public static final class Stats {
        public final LongAdder checked = new LongAdder();
        public final LongAdder accepted = new LongAdder();
        public final LongAdder rejected = new LongAdder();
        public final List<Example> examples = new ArrayList<>();
    }

    public record Example(BlockPos position, boolean accepted) {
    }
}
