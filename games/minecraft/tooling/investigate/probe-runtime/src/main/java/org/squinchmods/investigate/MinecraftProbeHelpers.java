package org.squinchmods.investigate;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.WorldGenRegion;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;

public final class MinecraftProbeHelpers {
    private MinecraftProbeHelpers() {
    }

    public static Optional<BlockState> guardedBlockState(WorldGenRegion region, BlockPos position) {
        int chunkX = Math.floorDiv(position.getX(), 16);
        int chunkZ = Math.floorDiv(position.getZ(), 16);
        return region.hasChunk(chunkX, chunkZ)
                ? Optional.of(region.getBlockState(position))
                : Optional.empty();
    }

    public static String blockId(BlockState state) {
        return BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString();
    }

    public static String biomeId(Holder<Biome> biome) {
        return biome.unwrapKey()
                .map(key -> key.location().toString())
                .orElse("unregistered:" + biome.value().getClass().getName());
    }

    public static int height(ServerLevel level, Heightmap.Types type, int blockX, int blockZ) {
        return level.getHeight(type, blockX, blockZ);
    }

    public static List<ChunkPos> forcedChunks(ServerLevel level) {
        List<ChunkPos> result = new ArrayList<>();
        level.getForcedChunks().forEach(value -> result.add(new ChunkPos(value)));
        result.sort(Comparator.comparingInt((ChunkPos pos) -> pos.x).thenComparingInt(pos -> pos.z));
        return List.copyOf(result);
    }

    public static <T> List<T> boundedExamples(Iterable<T> values, int limit) {
        if (limit < 0) {
            throw new IllegalArgumentException("limit must not be negative");
        }
        List<T> result = new ArrayList<>(limit);
        for (T value : values) {
            if (result.size() == limit) {
                break;
            }
            result.add(value);
        }
        return List.copyOf(result);
    }

    public static <T> Map<T, Long> topK(Map<T, Long> counts, int limit) {
        if (limit < 0) {
            throw new IllegalArgumentException("limit must not be negative");
        }
        List<Map.Entry<T, Long>> entries = new ArrayList<>(counts.entrySet());
        entries.sort(
                Map.Entry.<T, Long>comparingByValue().reversed()
                        .thenComparing(entry -> String.valueOf(entry.getKey())));
        Map<T, Long> result = new LinkedHashMap<>();
        for (int index = 0; index < Math.min(limit, entries.size()); index++) {
            Map.Entry<T, Long> entry = entries.get(index);
            result.put(entry.getKey(), entry.getValue());
        }
        return Collections.unmodifiableMap(result);
    }
}
