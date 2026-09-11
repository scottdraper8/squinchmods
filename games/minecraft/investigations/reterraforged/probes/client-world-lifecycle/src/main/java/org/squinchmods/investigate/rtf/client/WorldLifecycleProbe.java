package org.squinchmods.investigate.rtf.client;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicBoolean;

import com.google.gson.JsonArray;
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
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.levelgen.Heightmap;
import raccoonman.reterraforged.client.gui.screen.presetconfig.IPreviewHandler;
import raccoonman.reterraforged.client.gui.screen.presetconfig.PresetConfigScreen;
import raccoonman.reterraforged.data.worldgen.preset.settings.Preset;

public final class WorldLifecycleProbe {
	private static final AtomicBoolean INSPECTION_STARTED = new AtomicBoolean();
	private static final AtomicBoolean STOP_REQUESTED = new AtomicBoolean();
	private static final Map<IPreviewHandler, String> PREVIEW_HANDLERS = new IdentityHashMap<>();
	private static final Map<String, PreviewFrame> PREVIEW_FRAMES = new LinkedHashMap<>();
	private static volatile CreateWorldScreen stagingScreen;
	private static volatile CreateWorldScreen pendingScreen;
	private static volatile PresetConfigScreen previewEditor;
	private static volatile boolean previewApplyRequested;
	private static volatile boolean previewReloadObserved;
	private static volatile Instant previewOpenedAt;
	private static volatile Instant previewApplyStartedAt;
	private static volatile Instant requestedAt;
	private static volatile JsonObject pendingResult;
	private static volatile long saveStartedNanos;

	private WorldLifecycleProbe() {
	}

	public static void stagingStarted(CreateWorldScreen screen) {
		stagingScreen = screen;
	}

	public static boolean previewParityEnabled() {
		return System.getenv("SQUINCH_CLIENT_PREVIEW_PARITY") != null;
	}

	public static void beginPreviewParity(CreateWorldScreen parent, Preset preset) {
		if (!previewParityEnabled()) {
			throw new IllegalStateException("preview parity automation is not enabled");
		}
		stagingScreen = parent;
		PresetConfigScreen editor = new PresetConfigScreen(parent);
		previewEditor = editor;
		previewOpenedAt = Instant.now();
		System.err.println("SQUINCH preview parity opened preset editor");
		Minecraft minecraft = Minecraft.getInstance();
		minecraft.execute(() -> {
			minecraft.setScreen(editor);
			minecraft.execute(() -> {
				editor.editPreset("squinch-default", Component.literal("squinch-default"), preset);
			});
		});
	}

	public static synchronized void registerPreview(String label, IPreviewHandler handler) {
		if (!previewParityEnabled() || previewEditor == null) {
			return;
		}
		PREVIEW_HANDLERS.put(handler, label);
		System.err.println(
			"SQUINCH preview parity registered " + label + "; handlers=" + PREVIEW_HANDLERS.size()
		);
	}

	public static synchronized void frameApplied(
		String label,
		IPreviewHandler handler,
		IPreviewHandler.FrameResult frame
	) {
		if (previewEditor == null || !label.equals(PREVIEW_HANDLERS.get(handler))) {
			return;
		}
		try {
			PreviewFrame captured = captureFrame(handler, frame);
			PREVIEW_FRAMES.put(label, captured);
			System.err.println(
				"SQUINCH preview parity captured " + label + " frame " + captured.biomeGridSha256
			);
		} catch (Throwable failure) {
			failAndStop(Minecraft.getInstance(), "preview frame capture failed: " + failure);
		}
	}

	public static void settingsReloaded() {
		CreateWorldScreen screen = stagingScreen;
		if (screen != null) {
			if (previewParityEnabled() && previewEditor != null) {
				previewReloadObserved = true;
				System.err.println("SQUINCH preview parity observed preset datapack reload");
				return;
			}
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
			if (previewParityEnabled()) {
				advancePreviewParity(minecraft);
			}
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

	private static synchronized void advancePreviewParity(Minecraft minecraft) {
		PresetConfigScreen editor = previewEditor;
		if (editor == null || !PREVIEW_HANDLERS.containsValue("2d")) {
			return;
		}
		if (!previewApplyRequested && minecraft.screen != editor) {
			return;
		}
		try {
			if (!PREVIEW_FRAMES.containsKey("2d")) {
				if (Duration.between(previewOpenedAt, Instant.now()).toSeconds() >= 120L) {
					failAndStop(minecraft, "timed out waiting for the applied 2D preview frame");
				}
				return;
			}
			if (!previewApplyRequested) {
				previewApplyRequested = true;
				previewApplyStartedAt = Instant.now();
				System.err.println("SQUINCH preview parity applying captured preset");
				editor.onDone();
				return;
			}
			if (previewReloadObserved) {
				CreateWorldScreen parent = stagingScreen;
				editor.onClose();
				previewEditor = null;
				stagingScreen = null;
				pendingScreen = parent;
				System.err.println("SQUINCH preview parity requesting world creation");
			} else if (Duration.between(previewApplyStartedAt, Instant.now()).toSeconds() >= 120L) {
				failAndStop(minecraft, "timed out waiting for the applied preset datapack reload");
			}
		} catch (Throwable failure) {
			failAndStop(minecraft, "preview UI parity setup failed: " + failure);
		}
	}

	private static void inspect(Minecraft minecraft, IntegratedServer server) {
		JsonObject result = new JsonObject();
		try {
			result.addProperty("status", "pass");
			result.addProperty("creation_elapsed_ms", Duration.between(requestedAt, Instant.now()).toMillis());
			ServerLevel level = server.overworld();
			if (previewParityEnabled()) {
				inspectPreviewParity(level, result);
			}
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

	private static void inspectPreviewParity(ServerLevel level, JsonObject result) {
		PreviewFrame frame = PREVIEW_FRAMES.get("2d");
		PreviewFrame frame3d = PREVIEW_FRAMES.get("3d");
		if (frame == null) {
			throw new IllegalStateException("the actual applied 2D preview frame was not captured");
		}
		JsonObject frames = new JsonObject();
		frames.add("2d", frame.toJson());
		if (frame3d != null) {
			frames.add("3d", frame3d.toJson());
		}
		result.add("actual_applied_preview_frames", frames);
		result.addProperty("world_seed", level.getSeed());
		result.addProperty("preview_seed_matches_world", frame.seed == level.getSeed());
		if (frame.seed != level.getSeed()) {
			throw new IllegalStateException(
				"applied preview seed " + frame.seed + " does not match world seed " + level.getSeed()
			);
		}

		var source = level.getChunkSource().getGenerator().getBiomeSource();
		var generator = level.getChunkSource().getGenerator();
		var randomState = level.getChunkSource().randomState();
		var sampler = randomState.sampler();
		if (frame.zoom < 4) {
			throw new IllegalStateException(
				"full-pixel parity requires a preview zoom of at least four blocks per pixel"
			);
		}

		MessageDigest previewDigest = sha256();
		MessageDigest runtimeDigest = sha256();
		MessageDigest runtimeHeightDigest = sha256();
		JsonArray runtimeMismatches = new JsonArray();
		JsonArray alignedRuntimeMismatches = new JsonArray();
		long[][] runtimeSamplesByQuartOffset = new long[4][4];
		long[][] runtimeMismatchesByQuartOffset = new long[4][4];
		long[][] runtimeHeightMismatchesByQuartOffset = new long[4][4];
		String[] runtimeBiomes = new String[Math.multiplyExact(frame.size, frame.size)];
		int half = frame.size / 2;
		long runtimeSampled = 0L;
		long runtimeMismatchCount = 0L;
		long runtimeHeightMismatchCount = 0L;
		long runtimeHeightAbsoluteDelta = 0L;
		int runtimeHeightMinimumDelta = Integer.MAX_VALUE;
		int runtimeHeightMaximumDelta = Integer.MIN_VALUE;
		for (int pixelZ = 0; pixelZ < frame.size; pixelZ++) {
			for (int pixelX = 0; pixelX < frame.size; pixelX++) {
				int blockX = frame.centerX + (pixelX - half) * frame.zoom;
				int blockZ = frame.centerZ + (pixelZ - half) * frame.zoom;
				int surfaceY = generator.getBaseHeight(
					blockX, blockZ, Heightmap.Types.WORLD_SURFACE_WG, level, randomState
				);
				int quartX = QuartPos.fromBlock(blockX);
				int quartY = QuartPos.fromBlock(surfaceY);
				int quartZ = QuartPos.fromBlock(blockZ);
				String expected = frame.biomeAt(pixelX, pixelZ);
				String direct = biomeId(source.getNoiseBiome(quartX, quartY, quartZ, sampler));
				runtimeBiomes[pixelZ * frame.size + pixelX] = direct;
				int quartOffsetX = Math.floorMod(blockX, 4);
				int quartOffsetZ = Math.floorMod(blockZ, 4);
				runtimeSamplesByQuartOffset[quartOffsetZ][quartOffsetX]++;
				int previewSurfaceY = frame.surfaceYAt(pixelX, pixelZ);
				int heightDelta = surfaceY - previewSurfaceY;
				runtimeHeightAbsoluteDelta += Math.abs((long) heightDelta);
				runtimeHeightMinimumDelta = Math.min(runtimeHeightMinimumDelta, heightDelta);
				runtimeHeightMaximumDelta = Math.max(runtimeHeightMaximumDelta, heightDelta);
				if (heightDelta != 0) {
					runtimeHeightMismatchCount++;
					runtimeHeightMismatchesByQuartOffset[quartOffsetZ][quartOffsetX]++;
				}
				update(previewDigest, blockX);
				update(previewDigest, blockZ);
				update(previewDigest, expected);
				update(runtimeDigest, blockX);
				update(runtimeDigest, blockZ);
				update(runtimeDigest, direct);
				update(runtimeHeightDigest, blockX);
				update(runtimeHeightDigest, blockZ);
				update(runtimeHeightDigest, surfaceY);
				runtimeSampled++;
				if (!expected.equals(direct)) {
					runtimeMismatchCount++;
					runtimeMismatchesByQuartOffset[quartOffsetZ][quartOffsetX]++;
					if (runtimeMismatches.size() < 32
							|| (quartOffsetX == 0 && quartOffsetZ == 0 && alignedRuntimeMismatches.size() < 32)) {
						JsonObject mismatch = new JsonObject();
						mismatch.addProperty("authority", "runtime-base-height");
						mismatch.addProperty("pixel_x", pixelX);
						mismatch.addProperty("pixel_z", pixelZ);
						mismatch.addProperty("block_x", blockX);
						mismatch.addProperty("preview_surface_y", previewSurfaceY);
						mismatch.addProperty("surface_y", surfaceY);
						mismatch.addProperty("block_z", blockZ);
						mismatch.addProperty("preview_biome", expected);
						mismatch.addProperty("direct_biome", direct);
						if (runtimeMismatches.size() < 32) {
							runtimeMismatches.add(mismatch);
						}
						if (quartOffsetX == 0 && quartOffsetZ == 0 && alignedRuntimeMismatches.size() < 32) {
							alignedRuntimeMismatches.add(mismatch.deepCopy());
						}
					}
				}
			}
		}
		result.addProperty("preview_runtime_surface_authority", "generator-base-height-world-surface-wg");
		result.addProperty("preview_runtime_sampled_pixels", runtimeSampled);
		result.addProperty("preview_runtime_mismatch_count", runtimeMismatchCount);
		result.add("preview_runtime_samples_by_quart_offset", quartOffsetCounts(runtimeSamplesByQuartOffset));
		result.add("preview_runtime_mismatches_by_quart_offset", quartOffsetCounts(runtimeMismatchesByQuartOffset));
		result.addProperty("preview_runtime_height_mismatch_count", runtimeHeightMismatchCount);
		result.addProperty("preview_runtime_height_absolute_delta", runtimeHeightAbsoluteDelta);
		result.addProperty("preview_runtime_height_minimum_delta", runtimeHeightMinimumDelta);
		result.addProperty("preview_runtime_height_maximum_delta", runtimeHeightMaximumDelta);
		result.add("preview_runtime_height_mismatches_by_quart_offset", quartOffsetCounts(runtimeHeightMismatchesByQuartOffset));
		result.add("preview_runtime_mismatch_examples", runtimeMismatches);
		result.add("preview_runtime_quart_aligned_mismatch_examples", alignedRuntimeMismatches);
		result.addProperty(
			"preview_runtime_expected_sha256", HexFormat.of().formatHex(previewDigest.digest())
		);
		result.addProperty(
			"preview_runtime_direct_sha256", HexFormat.of().formatHex(runtimeDigest.digest())
		);
		result.addProperty(
			"preview_runtime_height_sha256", HexFormat.of().formatHex(runtimeHeightDigest.digest())
		);

		boolean[] finishedPixels = finishedSurfacePixels(frame.size);
		MessageDigest finishedExpectedDigest = sha256();
		MessageDigest finishedStoredDigest = sha256();
		JsonArray finishedMismatches = new JsonArray();
		long finishedSampled = 0L;
		long finishedPreviewDirectMismatchCount = 0L;
		long finishedPreviewStoredMismatchCount = 0L;
		long finishedPreviewZoomedMismatchCount = 0L;
		long finishedDirectStoredMismatchCount = 0L;
		long finishedStoredZoomedMismatchCount = 0L;
		long finishedDirectRepeatMismatchCount = 0L;
		for (int pixelZ = 0; pixelZ < frame.size; pixelZ++) {
			for (int pixelX = 0; pixelX < frame.size; pixelX++) {
				if (!finishedPixels[pixelZ * frame.size + pixelX]) {
					continue;
				}
				int blockX = frame.centerX + (pixelX - half) * frame.zoom;
				int blockZ = frame.centerZ + (pixelZ - half) * frame.zoom;
				int chunkX = Math.floorDiv(blockX, 16);
				int chunkZ = Math.floorDiv(blockZ, 16);
				var chunk = level.getChunk(chunkX, chunkZ);
				int surfaceY = level.getHeight(Heightmap.Types.WORLD_SURFACE_WG, blockX, blockZ);
				int quartX = QuartPos.fromBlock(blockX);
				int quartY = QuartPos.fromBlock(surfaceY);
				int quartZ = QuartPos.fromBlock(blockZ);
				String expected = frame.biomeAt(pixelX, pixelZ);
				String directBeforeGeneration = runtimeBiomes[pixelZ * frame.size + pixelX];
				String direct = biomeId(source.getNoiseBiome(quartX, quartY, quartZ, sampler));
				String stored = biomeId(chunk.getNoiseBiome(quartX, quartY, quartZ));
				String zoomed = biomeId(level.getBiome(new BlockPos(blockX, surfaceY, blockZ)));
				update(finishedExpectedDigest, blockX);
				update(finishedExpectedDigest, blockZ);
				update(finishedExpectedDigest, expected);
				update(finishedStoredDigest, blockX);
				update(finishedStoredDigest, blockZ);
				update(finishedStoredDigest, stored);
				finishedSampled++;
				boolean previewDirectMismatch = !expected.equals(direct);
				boolean previewStoredMismatch = !expected.equals(stored);
				boolean previewZoomedMismatch = !expected.equals(zoomed);
				boolean directStoredMismatch = !direct.equals(stored);
				boolean storedZoomedMismatch = !stored.equals(zoomed);
				boolean directRepeatMismatch = !directBeforeGeneration.equals(direct);
				finishedPreviewDirectMismatchCount += previewDirectMismatch ? 1L : 0L;
				finishedPreviewStoredMismatchCount += previewStoredMismatch ? 1L : 0L;
				finishedPreviewZoomedMismatchCount += previewZoomedMismatch ? 1L : 0L;
				finishedDirectStoredMismatchCount += directStoredMismatch ? 1L : 0L;
				finishedStoredZoomedMismatchCount += storedZoomedMismatch ? 1L : 0L;
				finishedDirectRepeatMismatchCount += directRepeatMismatch ? 1L : 0L;
				if (previewDirectMismatch || previewStoredMismatch || previewZoomedMismatch
						|| directStoredMismatch || storedZoomedMismatch || directRepeatMismatch) {
					if (finishedMismatches.size() < 32) {
						JsonObject mismatch = new JsonObject();
						mismatch.addProperty("authority", "finished-world-surface");
						mismatch.addProperty("pixel_x", pixelX);
						mismatch.addProperty("pixel_z", pixelZ);
						mismatch.addProperty("block_x", blockX);
						mismatch.addProperty("surface_y", surfaceY);
						mismatch.addProperty("block_z", blockZ);
						mismatch.addProperty("preview_biome", expected);
						mismatch.addProperty("direct_before_generation_biome", directBeforeGeneration);
						mismatch.addProperty("direct_biome", direct);
						mismatch.addProperty("stored_biome", stored);
						mismatch.addProperty("zoomed_biome", zoomed);
						finishedMismatches.add(mismatch);
					}
				}
			}
		}
		result.addProperty("preview_finished_surface_authority", "finished-world-surface-wg");
		result.addProperty("preview_finished_surface_sampled_pixels", finishedSampled);
		result.addProperty("preview_finished_surface_mismatch_count", finishedPreviewStoredMismatchCount);
		result.addProperty("preview_finished_direct_mismatch_count", finishedPreviewDirectMismatchCount);
		result.addProperty("preview_finished_stored_mismatch_count", finishedPreviewStoredMismatchCount);
		result.addProperty("preview_finished_zoomed_mismatch_count", finishedPreviewZoomedMismatchCount);
		result.addProperty("finished_direct_stored_mismatch_count", finishedDirectStoredMismatchCount);
		result.addProperty("finished_stored_zoomed_mismatch_count", finishedStoredZoomedMismatchCount);
		result.addProperty("finished_direct_repeat_mismatch_count", finishedDirectRepeatMismatchCount);
		result.add("preview_finished_surface_mismatch_examples", finishedMismatches);
		result.addProperty(
			"preview_finished_surface_expected_sha256",
			HexFormat.of().formatHex(finishedExpectedDigest.digest())
		);
		result.addProperty(
			"preview_finished_surface_stored_sha256",
			HexFormat.of().formatHex(finishedStoredDigest.digest())
		);
		if (finishedDirectStoredMismatchCount != 0L || finishedDirectRepeatMismatchCount != 0L) {
			throw new IllegalStateException(
				finishedDirectStoredMismatchCount + " direct/stored and "
					+ finishedDirectRepeatMismatchCount + " repeated runtime biome mismatches"
			);
		}
	}

	private static JsonObject quartOffsetCounts(long[][] counts) {
		JsonObject result = new JsonObject();
		for (int z = 0; z < counts.length; z++) {
			for (int x = 0; x < counts[z].length; x++) {
				if (counts[z][x] != 0L) {
					result.addProperty("x" + x + "_z" + z, counts[z][x]);
				}
			}
		}
		return result;
	}

	private static boolean[] finishedSurfacePixels(int size) {
		boolean[] selected = new boolean[Math.multiplyExact(size, size)];
		int half = size / 2;
		for (int dz = -3; dz <= 3; dz++) {
			for (int dx = -3; dx <= 3; dx++) {
				selected[(half + dz) * size + half + dx] = true;
			}
		}
		return selected;
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

	private static PreviewFrame captureFrame(
		IPreviewHandler handler,
		IPreviewHandler.FrameResult frame
	) {
		IPreviewHandler.AppliedFrameSnapshot snapshot = frame.snapshot(handler.getZoom());
		int size = snapshot.biomeSize();
		String[] palette = snapshot.biomePalette();
		short[] indices = snapshot.biomeIndices();
		int[] raster = snapshot.rasterPayload();
		if (!snapshot.hasBiomePlane()) {
			return new PreviewFrame(
				snapshot.seed(), snapshot.centerX(), snapshot.centerZ(), snapshot.zoom(), 0,
				snapshot.rasterWidth(), snapshot.rasterHeight(),
				new String[0], new int[0], Map.of(), null, null, digest(raster)
			);
		}
			String[] biomes = new String[indices.length];
			int[] surfaceYs = snapshot.surfaceYs();
			Map<String, Integer> counts = new TreeMap<>();
			MessageDigest biomeDigest = sha256();
			MessageDigest surfaceHeightDigest = sha256();
			for (int z = 0; z < size; z++) {
				for (int x = 0; x < size; x++) {
					int offset = z * size + x;
					int paletteIndex = indices[offset] & 0xFFFF;
					if (paletteIndex >= palette.length) {
						throw new IllegalStateException("preview palette index is out of range");
					}
					String biome = palette[paletteIndex];
					biomes[offset] = biome;
					int surfaceY = surfaceYs[offset];
					update(biomeDigest, x);
					update(biomeDigest, z);
					update(biomeDigest, biome);
					update(surfaceHeightDigest, surfaceY);
					counts.merge(biome, 1, Integer::sum);
				}
			}
			MessageDigest rasterDigest = sha256();
			for (int pixel : raster) {
				update(rasterDigest, pixel);
			}
			return new PreviewFrame(
				snapshot.seed(), snapshot.centerX(), snapshot.centerZ(), snapshot.zoom(),
				size,
				snapshot.rasterWidth(), snapshot.rasterHeight(),
				biomes,
				surfaceYs,
				counts,
				HexFormat.of().formatHex(biomeDigest.digest()),
				HexFormat.of().formatHex(surfaceHeightDigest.digest()),
				HexFormat.of().formatHex(rasterDigest.digest())
			);
	}

	private static String digest(int[] values) {
		MessageDigest digest = sha256();
		for (int value : values) {
			update(digest, value);
		}
		return HexFormat.of().formatHex(digest.digest());
	}

	private static MessageDigest sha256() {
		try {
			return MessageDigest.getInstance("SHA-256");
		} catch (NoSuchAlgorithmException failure) {
			throw new IllegalStateException("SHA-256 is unavailable", failure);
		}
	}

	private static void update(MessageDigest digest, int value) {
		digest.update((byte) (value >>> 24));
		digest.update((byte) (value >>> 16));
		digest.update((byte) (value >>> 8));
		digest.update((byte) value);
	}

	private static void update(MessageDigest digest, String value) {
		byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
		update(digest, bytes.length);
		digest.update(bytes);
	}

	private record PreviewFrame(
		long seed,
		int centerX,
		int centerZ,
		int zoom,
		int size,
		int rasterWidth,
		int rasterHeight,
		String[] biomes,
		int[] surfaceYs,
		Map<String, Integer> biomeCounts,
		String biomeGridSha256,
		String surfaceHeightSha256,
		String rasterSha256
	) {
		private String biomeAt(int x, int z) {
			return this.biomes[z * this.size + x];
		}

		private int surfaceYAt(int x, int z) {
			return this.surfaceYs[z * this.size + x];
		}

		private JsonObject toJson() {
			JsonObject result = new JsonObject();
			result.addProperty("seed", this.seed);
			result.addProperty("center_x", this.centerX);
			result.addProperty("center_z", this.centerZ);
			result.addProperty("zoom", this.zoom);
			result.addProperty("biome_width", this.size);
			result.addProperty("biome_height", this.size);
			result.addProperty("raster_width", this.rasterWidth);
			result.addProperty("raster_height", this.rasterHeight);
			result.addProperty("sampled_pixels", this.biomes.length);
			result.addProperty("biome_grid_sha256", this.biomeGridSha256);
			result.addProperty("surface_height_sha256", this.surfaceHeightSha256);
			result.addProperty("applied_raster_sha256", this.rasterSha256);
			JsonObject counts = new JsonObject();
			this.biomeCounts.forEach(counts::addProperty);
			result.add("biome_counts", counts);
			return result;
		}
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
