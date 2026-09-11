package org.squinchmods.investigate.rtf.preview;

import java.lang.ref.WeakReference;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicBoolean;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.worldselection.CreateWorldScreen;
import net.minecraft.client.server.IntegratedServer;
import net.minecraft.world.level.Level;
import raccoonman.reterraforged.client.gui.screen.presetconfig.IPreviewHandler;
import raccoonman.reterraforged.client.gui.screen.presetconfig.PresetConfigScreen;
import raccoonman.reterraforged.client.gui.screen.page.LinkedPageScreen.Page;

public final class LifecycleProbe {
	private static final AtomicBoolean FINISHED = new AtomicBoolean();
	private static final MemoryMXBean MEMORY = ManagementFactory.getMemoryMXBean();
	private static final Map<IPreviewHandler, String> HANDLERS = new IdentityHashMap<>();
	private static final Map<String, Integer> FRAMES = new java.util.LinkedHashMap<>();
	private static final List<JsonObject> UI_ROUNDS = new ArrayList<>();
	private static volatile CreateWorldScreen pendingScreen;
	private static volatile CreateWorldScreen stagingScreen;
	private static volatile Instant requestedAt;
	private static UiRound uiRound;
	private static Object uiPreset;
	private static int completedUiRounds;
	private static boolean reloadObserved;

	private LifecycleProbe() {
	}

	public static boolean uiLifecycleEnabled() {
		return System.getenv("SQUINCH_PRE_SERVER_UI_LIFECYCLE") != null;
	}

	public static void beginUiLifecycle(CreateWorldScreen parent, Object preset) {
		if (!uiLifecycleEnabled()) {
			throw new IllegalStateException("UI lifecycle automation is not enabled");
		}
		stagingScreen = parent;
		uiPreset = preset;
		openEditor(parent, preset, false);
	}

	public static synchronized void registerPreview(String label, IPreviewHandler handler) {
		UiRound round = uiRound;
		if (round == null || FINISHED.get()) {
			return;
		}
		try {
			if (field(handler.page(), "screen") != round.editor) {
				System.err.println("SQUINCH ignored preview handler from a non-lifecycle editor: " + label);
				return;
			}
		} catch (ReflectiveOperationException failure) {
			throw new IllegalStateException("cannot identify preview handler editor ownership", failure);
		}
		if (HANDLERS.containsValue(label)) {
			HANDLERS.clear();
			FRAMES.clear();
		}
		HANDLERS.put(handler, label);
		FRAMES.put(label, 0);
	}

	public static synchronized void frameApplied(
		String label,
		IPreviewHandler handler,
		IPreviewHandler.FrameResult frame
	) {
		if (uiRound == null || FINISHED.get() || !HANDLERS.containsKey(handler)) {
			return;
		}
		FRAMES.merge(label, 1, Integer::sum);
		uiRound.captureFrame(label, handler, frame);
	}

	public static void stagingStarted(CreateWorldScreen screen) {
		stagingScreen = screen;
	}

	public static synchronized void settingsReloaded() {
		CreateWorldScreen screen = stagingScreen;
		if (screen == null) {
			return;
		}
		if (uiLifecycleEnabled() && completedUiRounds == 1) {
			reloadObserved = true;
			return;
		}
		stagingScreen = null;
		pendingScreen = screen;
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
		String configured = System.getenv("SQUINCH_PRE_SERVER_CREATE_WORLD_RESULT");
		if (configured == null || FINISHED.get()) {
			return;
		}
		if (uiLifecycleEnabled()) {
			try {
				advanceUi(minecraft);
			} catch (Throwable failure) {
				finish(minecraft, configured, "fail", "UI lifecycle failed: " + failure, null);
				return;
			}
		}

		Instant started = requestedAt;
		if (started == null) {
			return;
		}
		IntegratedServer server = minecraft.getSingleplayerServer();
		if (server != null && server.getLevel(Level.OVERWORLD) != null && minecraft.level != null) {
			finish(minecraft, configured, "pass", null, server);
			return;
		}
		if (server != null && server.isStopped()) {
			finish(minecraft, configured, "fail", "integrated server stopped before creating overworld", server);
			return;
		}
		if (Duration.between(started, Instant.now()).toSeconds() >= 180L) {
			finish(minecraft, configured, "fail", "timed out waiting for integrated overworld", server);
		}
	}

	private static synchronized void advanceUi(Minecraft minecraft) throws Exception {
		UiRound round = uiRound;
		if (round == null) {
			if (completedUiRounds == 1 && reloadObserved) {
				reloadObserved = false;
				openEditor(stagingScreen, uiPreset, true);
			}
			return;
		}
		round.advance(minecraft);
	}

	private static void openEditor(CreateWorldScreen parent, Object preset, boolean afterReload) {
		if (parent == null || preset == null) {
			throw new IllegalStateException("Preview UI lifecycle has no parent screen or preset");
		}
		Minecraft minecraft = Minecraft.getInstance();
		PresetConfigScreen editor = new PresetConfigScreen(parent);
		HANDLERS.clear();
		FRAMES.clear();
		uiRound = new UiRound(editor, parent, afterReload, heapAfterGc());
		minecraft.execute(() -> {
			minecraft.setScreen(editor);
			minecraft.execute(() -> {
				try {
					Class<?> entryClass = Class.forName(
						"raccoonman.reterraforged.client.gui.screen.presetconfig.PresetListPage$PresetEntry"
					);
					Class<?> pageClass = Class.forName(
						"raccoonman.reterraforged.client.gui.screen.presetconfig.WorldSettingsPage"
					);
					Object page = pageClass.getConstructor(PresetConfigScreen.class, entryClass)
						.newInstance(editor, preset);
					editor.setPage((Page) page);
				} catch (ReflectiveOperationException failure) {
					throw new IllegalStateException("failed opening the real preset editor page", failure);
				}
			});
		});
	}

	private static void finish(
		Minecraft minecraft,
		String configured,
		String status,
		String message,
		IntegratedServer server
	) {
		if (!FINISHED.compareAndSet(false, true)) {
			return;
		}
		JsonObject result = new JsonObject();
		result.addProperty("status", status);
		result.addProperty("server_present", server != null);
		result.addProperty("server_running", server != null && server.isRunning());
		result.addProperty("overworld_present", server != null && server.getLevel(Level.OVERWORLD) != null);
		result.addProperty("client_level_present", minecraft.level != null);
		result.addProperty("ui_lifecycle_enabled", uiLifecycleEnabled());
		result.addProperty("ui_rounds_completed", completedUiRounds);
		JsonArray rounds = new JsonArray();
		UI_ROUNDS.forEach(rounds::add);
		result.add("ui_rounds", rounds);
		if (requestedAt != null) {
			result.addProperty("elapsed_ms", Duration.between(requestedAt, Instant.now()).toMillis());
		}
		if (message != null) {
			result.addProperty("message", message);
		}
		try {
			Path destination = Path.of(configured).toAbsolutePath();
			Files.createDirectories(destination.getParent());
			Path temporary = destination.resolveSibling(destination.getFileName() + ".tmp");
			Files.writeString(temporary, result + "\n", StandardCharsets.UTF_8);
			Files.move(temporary, destination, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
		} catch (Exception failure) {
			throw new IllegalStateException("failed writing integrated lifecycle result", failure);
		} finally {
			minecraft.stop();
		}
	}

	private static long heapAfterGc() {
		for (int attempt = 0; attempt < 3; attempt++) {
			System.gc();
		}
		return MEMORY.getHeapMemoryUsage().getUsed();
	}

	private static Object field(Object target, String name) throws ReflectiveOperationException {
		for (Class<?> type = target.getClass(); type != null; type = type.getSuperclass()) {
			try {
				Field field = type.getDeclaredField(name);
				field.setAccessible(true);
				return field.get(target);
			} catch (NoSuchFieldException ignored) {
			}
		}
		throw new NoSuchFieldException(target.getClass().getName() + "." + name);
	}

	private static Object previewState(IPreviewHandler handler) throws ReflectiveOperationException {
		Method method = handler.getClass().getMethod("state");
		method.setAccessible(true);
		return method.invoke(handler);
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

	private enum UiStage {
		WAIT_INITIAL_FRAMES,
		WAIT_ACTIVE_REPLACEMENT,
		WAIT_FINAL_FRAMES,
		VERIFY_RETIRED_OWNERS
	}

	private static final class UiRound {
		private final PresetConfigScreen editor;
		private final CreateWorldScreen parent;
		private final boolean afterReload;
		private final long heapBefore;
		private final Instant started = Instant.now();
		private final List<WeakReference<Object>> retired = new ArrayList<>();
		private final Map<String, JsonObject> frameSnapshots = new java.util.LinkedHashMap<>();
		private UiStage stage = UiStage.WAIT_INITIAL_FRAMES;
		private Map<String, Integer> finalFrameBaseline = Map.of();
		private Object lastObservedKey;
		private int gcAttempts;

		private UiRound(
			PresetConfigScreen editor,
			CreateWorldScreen parent,
			boolean afterReload,
			long heapBefore
		) {
			this.editor = editor;
			this.parent = parent;
			this.afterReload = afterReload;
			this.heapBefore = heapBefore;
		}

		private void advance(Minecraft minecraft) throws Exception {
			if (Duration.between(this.started, Instant.now()).toSeconds() > 120L) {
				throw new IllegalStateException("timed out in UI stage " + this.stage);
			}
			if (minecraft.screen != this.editor || HANDLERS.size() < 2) {
				return;
			}
			if (!anyRunning()) {
				for (IPreviewHandler handler : HANDLERS.keySet()) {
					Object failure = field(previewState(handler), "previewFailure");
					if (failure != null) {
						throw new IllegalStateException(
							HANDLERS.get(handler) + " preview settled with " + failure.getClass().getName()
						);
					}
				}
			}
			switch (this.stage) {
				case WAIT_INITIAL_FRAMES -> this.beginReplacementWhenReady();
				case WAIT_ACTIVE_REPLACEMENT -> this.cancelActiveGenerationWhenReady();
				case WAIT_FINAL_FRAMES -> this.verifyFinalFramesWhenReady();
				case VERIFY_RETIRED_OWNERS -> this.verifyRetirementAndFinish();
			}
		}

		private void captureFrame(
			String label,
			IPreviewHandler handler,
			IPreviewHandler.FrameResult frame
		) {
			try {
				Object sidecar = field(frame, "biomes");
				if (sidecar == null) {
					throw new IllegalStateException(label + " applied a frame without biome selections");
				}
				int size = (int) field(sidecar, "size");
				String[] palette = (String[]) field(sidecar, "palette");
				short[] indices = (short[]) field(sidecar, "indices");
				int[] raster = (int[]) field(frame, "rasterPayload");
				if (size <= 0 || indices.length != Math.multiplyExact(size, size) || raster == null) {
					throw new IllegalStateException(label + " applied an invalid biome frame");
				}
				MessageDigest biomeDigest = sha256();
				Map<String, Integer> counts = new TreeMap<>();
				for (int z = 0; z < size; z++) {
					for (int x = 0; x < size; x++) {
						int index = indices[z * size + x] & 0xFFFF;
						if (index >= palette.length) {
							throw new IllegalStateException(label + " biome palette index is out of range");
						}
						String biome = palette[index];
						update(biomeDigest, x);
						update(biomeDigest, z);
						update(biomeDigest, biome);
						counts.merge(biome, 1, Integer::sum);
					}
				}
				MessageDigest rasterDigest = sha256();
				for (int pixel : raster) {
					update(rasterDigest, pixel);
				}
				Object cacheKey = field(previewState(handler), "cacheKey");
				JsonObject result = new JsonObject();
				result.addProperty("seed", seed(cacheKey));
				result.addProperty("center_x", (int) field(frame, "centerX"));
				result.addProperty("center_z", (int) field(frame, "centerZ"));
				result.addProperty("zoom", handler.getZoom());
				result.addProperty("width", size);
				result.addProperty("height", size);
				result.addProperty("sampled_pixels", indices.length);
				result.addProperty(
					"biome_grid_sha256", HexFormat.of().formatHex(biomeDigest.digest())
				);
				result.addProperty(
					"applied_raster_sha256", HexFormat.of().formatHex(rasterDigest.digest())
				);
				JsonObject biomeCounts = new JsonObject();
				counts.forEach(biomeCounts::addProperty);
				result.add("biome_counts", biomeCounts);
				this.frameSnapshots.put(label, result);
			} catch (ReflectiveOperationException failure) {
				throw new IllegalStateException("cannot capture applied " + label + " preview frame", failure);
			}
		}

		private void beginReplacementWhenReady() throws Exception {
			if (!framesAdvanced(Map.of("2d", 0, "3d", 0)) || anyRunning()) {
				return;
			}
			Object initialKey = commonCacheKey();
			this.lastObservedKey = initialKey;
			this.retired.add(new WeakReference<>(initialKey));
			Object requestPool = field(this.editor, "previewRequests");
			Object owner = field(requestPool, "current");
			if (owner == null) {
				throw new IllegalStateException("screen request pool has no prepared owner after initial frames");
			}
			this.retired.add(new WeakReference<>(owner));
			long seed = seed(initialKey);
			this.editor.setSeed(Long.toString(seed + 1L));
			HANDLERS.keySet().forEach(IPreviewHandler::regenerate);
			this.stage = UiStage.WAIT_ACTIVE_REPLACEMENT;
		}

		private void cancelActiveGenerationWhenReady() throws Exception {
			if (!anyRunning()) {
				return;
			}
			Object activeKey = activeCacheKey();
			if (activeKey == null) {
				return;
			}
			this.retired.add(new WeakReference<>(activeKey));
			long seed = seed(activeKey);
			this.editor.setSeed(Long.toString(seed + 1L));
			this.finalFrameBaseline = Map.copyOf(FRAMES);
			HANDLERS.keySet().forEach(IPreviewHandler::regenerate);
			this.lastObservedKey = null;
			this.stage = UiStage.WAIT_FINAL_FRAMES;
		}

		private void verifyFinalFramesWhenReady() throws Exception {
			if (anyRunning() || !framesAdvanced(this.finalFrameBaseline)) {
				return;
			}
			commonCacheKey();
			for (IPreviewHandler handler : HANDLERS.keySet()) {
				Object state = previewState(handler);
				if (field(state, "previewFailure") != null) {
					throw new IllegalStateException("preview widget retained a failure after replacement");
				}
				if ((boolean) field(state, "isDirty")) {
					return;
				}
			}
			this.stage = UiStage.VERIFY_RETIRED_OWNERS;
		}

		private void verifyRetirementAndFinish() throws Exception {
			this.gcAttempts++;
			long heapAfter = heapAfterGc();
			long retained = this.retired.stream().filter(reference -> reference.get() != null).count();
			if (retained > 0 && this.gcAttempts < 10) {
				return;
			}
			if (retained > 0) {
				throw new IllegalStateException(retained + " stale cache owners remain strongly reachable");
			}
			if (!this.frameSnapshots.keySet().containsAll(Set.of("2d", "3d"))) {
				throw new IllegalStateException("final applied biome frames are incomplete: " + this.frameSnapshots.keySet());
			}
			JsonObject result = new JsonObject();
			result.addProperty("after_datapack_reload", this.afterReload);
			result.addProperty("elapsed_ms", Duration.between(this.started, Instant.now()).toMillis());
			result.addProperty("heap_before_bytes", this.heapBefore);
			result.addProperty("heap_after_bytes", heapAfter);
			result.addProperty("heap_delta_bytes", heapAfter - this.heapBefore);
			result.addProperty("retired_owner_references", this.retired.size());
			result.addProperty("retired_owner_references_alive", 0);
			JsonObject frames = new JsonObject();
			FRAMES.forEach(frames::addProperty);
			result.add("frames", frames);
			JsonObject finalFrames = new JsonObject();
			this.frameSnapshots.forEach((label, frame) -> finalFrames.add(label, frame.deepCopy()));
			result.add("final_applied_frames", finalFrames);
			UI_ROUNDS.add(result);
			completedUiRounds++;
			uiRound = null;
			HANDLERS.clear();
			FRAMES.clear();
			if (!this.afterReload) {
				this.editor.onDone();
				this.editor.onClose();
			} else {
				this.editor.onClose();
				stagingScreen = null;
				pendingScreen = this.parent;
			}
		}

		private Object commonCacheKey() throws Exception {
			Object keyFactory = field(this.editor, "previewRequestKeys");
			Object found = field(keyFactory, "current");
			if (found == null) {
				throw new IllegalStateException("screen key factory has no current semantic request");
			}
			Object requestPool = field(this.editor, "previewRequests");
			Object owner = field(requestPool, "current");
			if (owner == null || field(owner, "cacheKey") != found) {
				throw new IllegalStateException("prepared owner does not share the current semantic request identity");
			}
			Object resultCache = field(this.editor, "previewCache");
			if (field(resultCache, "currentRevision") != found) {
				throw new IllegalStateException("result cache does not share the current semantic request identity");
			}
			return found;
		}

		private Object activeCacheKey() throws Exception {
			Object key = field(field(this.editor, "previewRequestKeys"), "current");
			if (key == null || key == this.lastObservedKey) {
				return null;
			}
			this.lastObservedKey = key;
			return key;
		}

		private boolean anyRunning() throws Exception {
			for (IPreviewHandler handler : HANDLERS.keySet()) {
				if ((boolean) field(previewState(handler), "isRunning")) {
					return true;
				}
			}
			return false;
		}

		private static long seed(Object key) throws ReflectiveOperationException {
			Method accessor = key.getClass().getDeclaredMethod("seed");
			accessor.setAccessible(true);
			return ((Number) accessor.invoke(key)).longValue();
		}

		private static boolean framesAdvanced(Map<String, Integer> baseline) {
			return FRAMES.getOrDefault("2d", 0) > baseline.getOrDefault("2d", 0)
				&& FRAMES.getOrDefault("3d", 0) > baseline.getOrDefault("3d", 0);
		}
	}
}
