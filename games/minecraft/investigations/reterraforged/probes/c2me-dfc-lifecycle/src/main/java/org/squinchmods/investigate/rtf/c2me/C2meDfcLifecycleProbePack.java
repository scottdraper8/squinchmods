package org.squinchmods.investigate.rtf.c2me;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import com.google.gson.JsonObject;

import net.minecraft.core.QuartPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.level.levelgen.Heightmap;
import org.squinchmods.investigate.FinishedChunkSelection;
import org.squinchmods.investigate.MinecraftProbeHelpers;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;

public final class C2meDfcLifecycleProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:ftf-c2me-dfc-lifecycle", "1", LifecycleProbe::new);
    }

    private static final class LifecycleProbe implements ProbeExecution {
        private final FinishedChunkSelection selection;

        private LifecycleProbe(ProbeRequest request) {
            this.selection = new FinishedChunkSelection(request.config(), "ftf-c2me-dfc-lifecycle");
        }

        @Override
        public ProbeResult tick(net.minecraft.server.MinecraftServer server) {
            FinishedChunkSelection.Snapshot snapshot = this.selection.poll(server.overworld());
            if (snapshot == null) {
                return null;
            }
            List<FinishedChunkSelection.ReadyChunk> chunks = new ArrayList<>(snapshot.ready());
            chunks.sort(Comparator
                .comparingInt((FinishedChunkSelection.ReadyChunk ready) -> ready.coordinate().x())
                .thenComparingInt(ready -> ready.coordinate().z()));
            MessageDigest heights = digest();
            MessageDigest materials = digest();
            MessageDigest biomes = digest();
            MessageDigest noiseStageHeights = digest();
            MessageDigest noiseStageBiomes = digest();
            JsonObject chunkHeightHashes = new JsonObject();
            JsonObject chunkBiomeHashes = new JsonObject();
            JsonObject chunkNoiseStageHeightHashes = new JsonObject();
            JsonObject chunkNoiseStageBiomeHashes = new JsonObject();
            Map<Integer, Long> surfaceHistogram = new TreeMap<>();
            Map<String, Long> topBlocks = new TreeMap<>();
            long columns = 0L;
            long surfaceSum = 0L;
            int surfaceMin = Integer.MAX_VALUE;
            int surfaceMax = Integer.MIN_VALUE;
            for (FinishedChunkSelection.ReadyChunk ready : chunks) {
                int chunkX = ready.coordinate().x();
                int chunkZ = ready.coordinate().z();
                MessageDigest chunkHeights = digest();
                MessageDigest chunkBiomes = digest();
                update(heights, chunkX);
                update(heights, chunkZ);
                update(materials, chunkX);
                update(materials, chunkZ);
                update(biomes, chunkX);
                update(biomes, chunkZ);
                NoiseStageTelemetry.Snapshot noiseStage = NoiseStageTelemetry.snapshot(chunkX, chunkZ);
                if (noiseStage == null) {
                    throw new IllegalStateException("Missing pre-surface noise-stage capture for chunk " + chunkX + "," + chunkZ);
                }
                update(noiseStageHeights, chunkX);
                update(noiseStageHeights, chunkZ);
                update(noiseStageHeights, noiseStage.heightHash());
                update(noiseStageBiomes, chunkX);
                update(noiseStageBiomes, chunkZ);
                update(noiseStageBiomes, noiseStage.biomeHash());
                for (int localZ = 0; localZ < 16; localZ++) {
                    for (int localX = 0; localX < 16; localX++) {
                        int surface = ready.chunk().getHeight(Heightmap.Types.WORLD_SURFACE_WG, localX, localZ);
                        int oceanFloor = ready.chunk().getHeight(Heightmap.Types.OCEAN_FLOOR_WG, localX, localZ);
                        update(heights, localX);
                        update(heights, localZ);
                        update(heights, surface);
                        update(heights, oceanFloor);
                        update(chunkHeights, surface);
                        update(chunkHeights, oceanFloor);
                        var top = ready.chunk().getBlockState(
                            new net.minecraft.core.BlockPos(chunkX * 16 + localX, surface - 1, chunkZ * 16 + localZ)
                        );
                        String topBlock = BuiltInRegistries.BLOCK.getKey(top.getBlock()).toString();
                        update(materials, localX);
                        update(materials, localZ);
                        update(materials, topBlock);
                        topBlocks.merge(topBlock, 1L, Long::sum);
                        surfaceHistogram.merge(surface, 1L, Long::sum);
                        surfaceSum += surface;
                        surfaceMin = Math.min(surfaceMin, surface);
                        surfaceMax = Math.max(surfaceMax, surface);
                        columns++;
                    }
                }
                for (int localQuartZ = 0; localQuartZ < 4; localQuartZ++) {
                    for (int localQuartX = 0; localQuartX < 4; localQuartX++) {
                        int blockX = chunkX * 16 + localQuartX * 4 + 2;
                        int blockZ = chunkZ * 16 + localQuartZ * 4 + 2;
                        int surface = ready.chunk().getHeight(
                            Heightmap.Types.WORLD_SURFACE_WG,
                            localQuartX * 4 + 2,
                            localQuartZ * 4 + 2
                        );
                        String biome = MinecraftProbeHelpers.biomeId(ready.chunk().getNoiseBiome(
                            QuartPos.fromBlock(blockX), QuartPos.fromBlock(surface), QuartPos.fromBlock(blockZ)
                        ));
                        update(biomes, blockX);
                        update(biomes, blockZ);
                        update(biomes, surface);
                        update(biomes, biome);
                        update(chunkBiomes, surface);
                        update(chunkBiomes, biome);
                    }
                }
                chunkHeightHashes.addProperty(
                    chunkX + "," + chunkZ,
                    HexFormat.of().formatHex(chunkHeights.digest())
                );
                chunkBiomeHashes.addProperty(
                    chunkX + "," + chunkZ,
                    HexFormat.of().formatHex(chunkBiomes.digest())
                );
                chunkNoiseStageHeightHashes.addProperty(chunkX + "," + chunkZ, noiseStage.heightHash());
                chunkNoiseStageBiomeHashes.addProperty(chunkX + "," + chunkZ, noiseStage.biomeHash());
            }
            JsonObject data = new JsonObject();
            data.addProperty("authority", "finished-chunk-terrain-and-biomes");
            data.addProperty("columns", columns);
            if (columns > 0) {
                data.addProperty("surface_min", surfaceMin);
                data.addProperty("surface_max", surfaceMax);
                data.addProperty("surface_sum", surfaceSum);
            }
            data.addProperty("height_sha256", HexFormat.of().formatHex(heights.digest()));
            data.addProperty("surface_material_sha256", HexFormat.of().formatHex(materials.digest()));
            data.addProperty("surface_biome_sha256", HexFormat.of().formatHex(biomes.digest()));
            data.addProperty("noise_stage_height_sha256", HexFormat.of().formatHex(noiseStageHeights.digest()));
            data.addProperty("noise_stage_biome_sha256", HexFormat.of().formatHex(noiseStageBiomes.digest()));
            data.add("chunk_height_sha256", chunkHeightHashes);
            data.add("chunk_surface_biome_sha256", chunkBiomeHashes);
            data.add("chunk_noise_stage_height_sha256", chunkNoiseStageHeightHashes);
            data.add("chunk_noise_stage_biome_sha256", chunkNoiseStageBiomeHashes);
            data.add("surface_height_histogram", counts(surfaceHistogram));
            data.add("top_blocks", counts(topBlocks));
            data.add("noise_chunk_lifecycle", NoiseChunkLifecycleTelemetry.snapshot());
            return this.selection.result(snapshot, data);
        }
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

    private static JsonObject counts(Map<?, Long> counts) {
        JsonObject result = new JsonObject();
        counts.forEach((key, value) -> result.addProperty(key.toString(), value));
        return result;
    }
}
