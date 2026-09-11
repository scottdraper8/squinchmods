package org.squinchmods.investigate.rtf.c2me;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

import com.google.gson.JsonObject;

import net.minecraft.world.level.levelgen.DensityFunction;

public final class NoiseChunkLifecycleTelemetry {
    private static final AtomicLong CONSTRUCTORS = new AtomicLong();
    private static final AtomicLong ZERO_INTERPOLATORS = new AtomicLong();
    private static final AtomicLong ZERO_CELL_CACHES = new AtomicLong();
    private static final AtomicLong ZERO_WRAPPED = new AtomicLong();
    private static final AtomicLong INTERPOLATORS = new AtomicLong();
    private static final AtomicLong CELL_CACHES = new AtomicLong();
    private static final AtomicLong WRAPPED = new AtomicLong();
    private static final AtomicLong WRAPPED_CELL_SAMPLERS = new AtomicLong();
    private static final AtomicLong ROUTER_MAP_BEFORE = new AtomicLong();
    private static final AtomicLong ROUTER_MAP_AFTER = new AtomicLong();
    private static final AtomicLong INVALID_ROUTER_MAP_CONSTRUCTORS = new AtomicLong();
    private static final Map<String, AtomicLong> INITIAL_DENSITY_CLASSES = new ConcurrentHashMap<>();

    private NoiseChunkLifecycleTelemetry() {
    }

    public static void observe(
        List<?> interpolators,
        List<?> cellCaches,
        Map<DensityFunction, DensityFunction> wrapped,
        DensityFunction initialDensity,
        int routerMapBefore,
        int routerMapAfter
    ) {
        CONSTRUCTORS.incrementAndGet();
        int interpolatorCount = interpolators.size();
        int cellCacheCount = cellCaches.size();
        int wrappedCount = wrapped.size();
        INTERPOLATORS.addAndGet(interpolatorCount);
        CELL_CACHES.addAndGet(cellCacheCount);
        WRAPPED.addAndGet(wrappedCount);
        ROUTER_MAP_BEFORE.addAndGet(routerMapBefore);
        ROUTER_MAP_AFTER.addAndGet(routerMapAfter);
        if (routerMapBefore != 1 || routerMapAfter != 1) {
            INVALID_ROUTER_MAP_CONSTRUCTORS.incrementAndGet();
        }
        if (interpolatorCount == 0) {
            ZERO_INTERPOLATORS.incrementAndGet();
        }
        if (cellCacheCount == 0) {
            ZERO_CELL_CACHES.incrementAndGet();
        }
        if (wrappedCount == 0) {
            ZERO_WRAPPED.incrementAndGet();
        }
        for (DensityFunction value : wrapped.values()) {
            if (value.getClass().getName().contains("CellSampler$CacheChunk")) {
                WRAPPED_CELL_SAMPLERS.incrementAndGet();
            }
        }
        INITIAL_DENSITY_CLASSES
            .computeIfAbsent(initialDensity.getClass().getName(), ignored -> new AtomicLong())
            .incrementAndGet();
    }

    public static JsonObject snapshot() {
        JsonObject result = new JsonObject();
        result.addProperty("constructors", CONSTRUCTORS.get());
        result.addProperty("zero_interpolator_constructors", ZERO_INTERPOLATORS.get());
        result.addProperty("zero_cell_cache_constructors", ZERO_CELL_CACHES.get());
        result.addProperty("zero_wrapped_constructors", ZERO_WRAPPED.get());
        result.addProperty("interpolator_total", INTERPOLATORS.get());
        result.addProperty("cell_cache_total", CELL_CACHES.get());
        result.addProperty("wrapped_total", WRAPPED.get());
        result.addProperty("wrapped_cell_sampler_total", WRAPPED_CELL_SAMPLERS.get());
        result.addProperty("router_map_before_total", ROUTER_MAP_BEFORE.get());
        result.addProperty("router_map_after_total", ROUTER_MAP_AFTER.get());
        result.addProperty("invalid_router_map_constructors", INVALID_ROUTER_MAP_CONSTRUCTORS.get());
        JsonObject classes = new JsonObject();
        INITIAL_DENSITY_CLASSES.entrySet().stream()
            .sorted(Map.Entry.comparingByKey())
            .forEach(entry -> classes.addProperty(entry.getKey(), entry.getValue().get()));
        result.add("initial_density_classes", classes);
        return result;
    }
}
