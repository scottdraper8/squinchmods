package org.squinchmods.investigate.rtf.c2me;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import net.minecraft.core.QuartPos;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.levelgen.Heightmap;
import org.squinchmods.investigate.MinecraftProbeHelpers;

public final class NoiseStageTelemetry {
    private static final Map<Long, Snapshot> CHUNKS = new ConcurrentHashMap<>();

    private NoiseStageTelemetry() {
    }

    public static void capture(ChunkAccess chunk) {
        int chunkX = chunk.getPos().x;
        int chunkZ = chunk.getPos().z;
        MessageDigest heights = digest();
        MessageDigest biomes = digest();
        for (int localZ = 0; localZ < 16; localZ++) {
            for (int localX = 0; localX < 16; localX++) {
                update(heights, chunk.getHeight(Heightmap.Types.WORLD_SURFACE_WG, localX, localZ));
                update(heights, chunk.getHeight(Heightmap.Types.OCEAN_FLOOR_WG, localX, localZ));
            }
        }
        for (int localQuartZ = 0; localQuartZ < 4; localQuartZ++) {
            for (int localQuartX = 0; localQuartX < 4; localQuartX++) {
                int blockX = chunkX * 16 + localQuartX * 4 + 2;
                int blockZ = chunkZ * 16 + localQuartZ * 4 + 2;
                int surface = chunk.getHeight(
                    Heightmap.Types.WORLD_SURFACE_WG,
                    localQuartX * 4 + 2,
                    localQuartZ * 4 + 2
                );
                update(biomes, surface);
                update(biomes, MinecraftProbeHelpers.biomeId(chunk.getNoiseBiome(
                    QuartPos.fromBlock(blockX), QuartPos.fromBlock(surface), QuartPos.fromBlock(blockZ)
                )));
            }
        }
        CHUNKS.put(
            chunk.getPos().toLong(),
            new Snapshot(HexFormat.of().formatHex(heights.digest()), HexFormat.of().formatHex(biomes.digest()))
        );
    }

    public static Snapshot snapshot(int chunkX, int chunkZ) {
        return CHUNKS.get(net.minecraft.world.level.ChunkPos.asLong(chunkX, chunkZ));
    }

    private static MessageDigest digest() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException(exception);
        }
    }

    private static void update(MessageDigest digest, int value) {
        digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(value).array());
    }

    private static void update(MessageDigest digest, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        update(digest, bytes.length);
        digest.update(bytes);
    }

    public record Snapshot(String heightHash, String biomeHash) {
    }
}
