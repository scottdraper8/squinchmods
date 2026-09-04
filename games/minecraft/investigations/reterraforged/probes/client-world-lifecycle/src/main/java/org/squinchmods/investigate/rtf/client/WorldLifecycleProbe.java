package org.squinchmods.investigate.rtf.client;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicBoolean;

import com.google.gson.JsonObject;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.worldselection.CreateWorldScreen;
import net.minecraft.client.server.IntegratedServer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.core.QuartPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.Heightmap;

public final class WorldLifecycleProbe {
	private static final AtomicBoolean INSPECTION_STARTED = new AtomicBoolean();
	private static final AtomicBoolean STOP_REQUESTED = new AtomicBoolean();
	private static volatile CreateWorldScreen stagingScreen;
	private static volatile CreateWorldScreen pendingScreen;
	private static volatile Instant requestedAt;
	private static volatile JsonObject pendingResult;
	private static volatile long saveStartedNanos;

	private WorldLifecycleProbe() {
	}

	public static void stagingStarted(CreateWorldScreen screen) {
		stagingScreen = screen;
	}

	public static void settingsReloaded() {
		CreateWorldScreen screen = stagingScreen;
		if (screen != null) {
			stagingScreen = null;
			pendingScreen = screen;
		}
	}

	public static CreateWorldScreen takePending() {
		CreateWorldScreen screen = pendingScreen;
		pendingScreen = null;
		return screen;
	}

	public static void creationRequested() {
		requestedAt = Instant.now();
	}

	public static void tick(Minecraft minecraft) {
		if (System.getenv("SQUINCH_CLIENT_WORLD_RESULT") == null || STOP_REQUESTED.get()) {
			return;
		}
		Instant started = requestedAt;
		if (started == null) {
			return;
		}
		IntegratedServer server = minecraft.getSingleplayerServer();
		if (server != null && server.getLevel(Level.OVERWORLD) != null && minecraft.level != null) {
			if (INSPECTION_STARTED.compareAndSet(false, true)) {
				server.execute(() -> inspect(minecraft, server));
			}
			return;
		}
		if (server != null && server.isStopped()) {
			failAndStop(minecraft, "integrated server stopped before creating overworld");
		} else if (Duration.between(started, Instant.now()).toSeconds() >= 240L) {
			failAndStop(minecraft, "timed out waiting for integrated overworld");
		}
	}

	private static void inspect(Minecraft minecraft, IntegratedServer server) {
		JsonObject result = new JsonObject();
		try {
			result.addProperty("status", "pass");
			result.addProperty("creation_elapsed_ms", Duration.between(requestedAt, Instant.now()).toMillis());
			ServerLevel level = server.overworld();
			String configuredTarget = System.getenv("SQUINCH_TARGET_BIOME");
			if (configuredTarget != null && !configuredTarget.isBlank()) {
				inspectBiome(level, ResourceLocation.parse(configuredTarget), result);
			} else {
				int[] forceCenter = forceCenter();
				if (forceCenter != null) {
					forceChunks(level, forceCenter[0], forceCenter[1], result);
				}
			}
		} catch (Throwable failure) {
			result.addProperty("status", "fail");
			result.addProperty("exception", failure.getClass().getName());
			result.addProperty("message", String.valueOf(failure.getMessage()));
		}
		pendingResult = result;
		STOP_REQUESTED.set(true);
		minecraft.execute(minecraft::stop);
	}

	private static void inspectBiome(ServerLevel level, ResourceLocation id, JsonObject result) {
		Holder<Biome> target = level.registryAccess().registryOrThrow(Registries.BIOME)
			.getHolderOrThrow(ResourceKey.create(Registries.BIOME, id));
		var source = level.getChunkSource().getGenerator().getBiomeSource();
		var sampler = level.getChunkSource().randomState().sampler();
		long locateStarted = System.nanoTime();
		var located = level.findClosestBiome3d(target::equals, level.getSharedSpawnPos(), 6400, 32, 64);
		result.addProperty("locate_elapsed_ms", (System.nanoTime() - locateStarted) / 1_000_000L);
		result.addProperty("target", id.toString());
		result.addProperty("possible_output", source.possibleBiomes().contains(target));
		if (located == null) {
			throw new IllegalStateException("target biome was not found");
		}
		BlockPos locatedPos = located.getFirst();
		int chunkX = Math.floorDiv(locatedPos.getX(), 16);
		int chunkZ = Math.floorDiv(locatedPos.getZ(), 16);
		int[] forceCenter = forceCenter();
		forceChunks(
			level,
			forceCenter == null ? chunkX : forceCenter[0],
			forceCenter == null ? chunkZ : forceCenter[1],
			result
		);
		var locatedChunk = level.getChunk(chunkX, chunkZ);
		int surfaceY = level.getHeight(Heightmap.Types.WORLD_SURFACE, locatedPos.getX(), locatedPos.getZ());
		BlockPos surfacePos = new BlockPos(locatedPos.getX(), surfaceY, locatedPos.getZ());
		Holder<Biome> locatedQuery = source.getNoiseBiome(
			QuartPos.fromBlock(locatedPos.getX()), QuartPos.fromBlock(locatedPos.getY()),
			QuartPos.fromBlock(locatedPos.getZ()), sampler
		);
		Holder<Biome> surfaceQuery = source.getNoiseBiome(
			QuartPos.fromBlock(surfacePos.getX()), QuartPos.fromBlock(surfacePos.getY()),
			QuartPos.fromBlock(surfacePos.getZ()), sampler
		);
		Holder<Biome> locatedStored = locatedChunk.getNoiseBiome(
			QuartPos.fromBlock(locatedPos.getX()), QuartPos.fromBlock(locatedPos.getY()),
			QuartPos.fromBlock(locatedPos.getZ())
		);
		Holder<Biome> surfaceStored = locatedChunk.getNoiseBiome(
			QuartPos.fromBlock(surfacePos.getX()), QuartPos.fromBlock(surfacePos.getY()),
			QuartPos.fromBlock(surfacePos.getZ())
		);
		Holder<Biome> surfaceZoomed = level.getBiome(surfacePos);
		result.addProperty("x", locatedPos.getX());
		result.addProperty("y", locatedPos.getY());
		result.addProperty("z", locatedPos.getZ());
		result.addProperty("surface_y", surfaceY);
		result.addProperty("located_biome", biomeId(located.getSecond()));
		result.addProperty("located_query_biome", biomeId(locatedQuery));
		result.addProperty("located_stored_biome", biomeId(locatedStored));
		result.addProperty("surface_query_biome", biomeId(surfaceQuery));
		result.addProperty("surface_stored_biome", biomeId(surfaceStored));
		result.addProperty("surface_zoomed_biome", biomeId(surfaceZoomed));
		Map<String, Integer> palette = new TreeMap<>();
		for (int dz = -32; dz <= 32; dz += 8) {
			for (int dx = -32; dx <= 32; dx += 8) {
				int x = locatedPos.getX() + dx;
				int z = locatedPos.getZ() + dz;
				int y = level.getHeight(Heightmap.Types.WORLD_SURFACE, x, z);
				palette.merge(biomeId(level.getBiome(new BlockPos(x, y, z))), 1, Integer::sum);
			}
		}
		JsonObject paletteJson = new JsonObject();
		palette.forEach(paletteJson::addProperty);
		result.add("surface_palette", paletteJson);
		if (!target.equals(located.getSecond()) || !target.equals(locatedQuery)
			|| !target.equals(locatedStored)
			|| !target.equals(surfaceQuery) || !target.equals(surfaceStored)) {
			throw new IllegalStateException("located target does not match the finished surface chunk");
		}
	}

	private static void forceChunks(ServerLevel level, int chunkX, int chunkZ, JsonObject result) {
		long chunksStarted = System.nanoTime();
		for (int dz = -2; dz <= 2; dz++) {
			for (int dx = -2; dx <= 2; dx++) {
				level.getChunk(chunkX + dx, chunkZ + dz);
			}
		}
		result.addProperty("forced_chunks_elapsed_ms", (System.nanoTime() - chunksStarted) / 1_000_000L);
		result.addProperty("forced_chunk_x", chunkX);
		result.addProperty("forced_chunk_z", chunkZ);
	}

	private static int[] forceCenter() {
		String x = System.getenv("SQUINCH_FORCE_CHUNK_X");
		String z = System.getenv("SQUINCH_FORCE_CHUNK_Z");
		if (x == null && z == null) {
			return null;
		}
		if (x == null || z == null) {
			throw new IllegalStateException("both fixed force-chunk coordinates are required");
		}
		return new int[] {Integer.parseInt(x), Integer.parseInt(z)};
	}

	private static String biomeId(Holder<Biome> biome) {
		return biome.unwrapKey().map(ResourceKey::location).map(ResourceLocation::toString).orElse("unregistered");
	}

	private static void failAndStop(Minecraft minecraft, String message) {
		JsonObject result = new JsonObject();
		result.addProperty("status", "fail");
		result.addProperty("message", message);
		pendingResult = result;
		STOP_REQUESTED.set(true);
		minecraft.stop();
	}

	public static void saveStarted() {
		saveStartedNanos = System.nanoTime();
	}

	public static void saveFinished() {
		JsonObject result = pendingResult;
		if (result == null) {
			return;
		}
		result.addProperty("save_elapsed_ms", (System.nanoTime() - saveStartedNanos) / 1_000_000L);
		write(result);
	}

	private static void write(JsonObject result) {
		try {
			Path destination = Path.of(System.getenv("SQUINCH_CLIENT_WORLD_RESULT")).toAbsolutePath();
			Files.createDirectories(destination.getParent());
			Path temporary = destination.resolveSibling(destination.getFileName() + ".tmp");
			Files.writeString(temporary, result + "\n", StandardCharsets.UTF_8);
			Files.move(temporary, destination, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
		} catch (Exception failure) {
			throw new IllegalStateException("failed writing client world lifecycle result", failure);
		}
	}
}
