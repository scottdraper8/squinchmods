package org.squinchmods.investigate.ftf.flowstorage;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.zip.DeflaterOutputStream;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import io.netty.buffer.ByteBufUtil;
import io.netty.buffer.Unpooled;
import net.minecraft.core.RegistryAccess;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.ClientboundCustomPayloadPacket;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.network.protocol.game.GameProtocols;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkAccess;

public final class FlowStorageNetworkTelemetry {
	private static final String FLOW_FIELD_KEY = "FTFFlowField";
	private static final String FLOW_SETTINGS_KEY = "FTFFlowSettings";
	private static final byte ENABLED_SETTINGS = 7;
	private static final int NETWORK_COMPRESSION_THRESHOLD = 256;
	private static final int REGION_SECTOR_BYTES = 4096;
	private static final int REGION_CHUNK_HEADER_BYTES = 5;
	private static final Map<Long, ChunkMetrics> METRICS = new ConcurrentHashMap<>();
	private static final AtomicInteger ERRORS = new AtomicInteger();
	private static volatile List<Window> windows = List.of();
	private static volatile RegistryAccess registryAccess;

	private FlowStorageNetworkTelemetry() {
	}

	public static int arm(JsonObject config) {
		List<Window> parsed = parseWindows(config);
		METRICS.clear();
		ERRORS.set(0);
		registryAccess = null;
		windows = parsed;
		return parsed.stream().mapToInt(Window::chunks).sum();
	}

	public static int requestedChunks(JsonObject config) {
		return parseWindows(config).stream().mapToInt(Window::chunks).sum();
	}

	public static void observe(ServerLevel level, ChunkAccess chunk, CompoundTag tag) {
		ChunkPos pos = chunk.getPos();
		if (tag == null || windows.stream().noneMatch(window -> window.contains(pos.x, pos.z))) {
			return;
		}
		try {
			RegistryAccess registries = level.registryAccess();
			registryAccess = registries;
			METRICS.put(pos.toLong(), measure(pos, tag, registries));
		} catch (Throwable error) {
			ERRORS.incrementAndGet();
		}
	}

	public static Report report() {
		List<ChunkMetrics> chunks = new ArrayList<>(METRICS.values());
		chunks.sort(Comparator.comparingInt(ChunkMetrics::z).thenComparingInt(ChunkMetrics::x));
		long actualUncompressed = 0;
		long actualDeflated = 0;
		long normalizedWithSettingsUncompressed = 0;
		long normalizedWithSettingsDeflated = 0;
		long normalizedWithoutSettingsUncompressed = 0;
		long normalizedWithoutSettingsDeflated = 0;
		long actualRegionAllocated = 0;
		long normalizedWithSettingsRegionAllocated = 0;
		long normalizedWithoutSettingsRegionAllocated = 0;
		int settingsSectorBoundaryCrossings = 0;
		long flowPayloadBodyBytes = 0;
		long flowPayloadDeflatedBytes = 0;
		long flowPacketBytes = 0;
		long flowWireBytes = 0;
		int riverChunks = 0;
		int settingsTags = 0;
		List<Integer> payloadDeflated = new ArrayList<>();
		MessageDigest digest = sha256();
		for (ChunkMetrics chunk : chunks) {
			actualUncompressed += chunk.actualUncompressed();
			actualDeflated += chunk.actualDeflated();
			normalizedWithSettingsUncompressed += chunk.withSettingsUncompressed();
			normalizedWithSettingsDeflated += chunk.withSettingsDeflated();
			normalizedWithoutSettingsUncompressed += chunk.withoutSettingsUncompressed();
			normalizedWithoutSettingsDeflated += chunk.withoutSettingsDeflated();
			actualRegionAllocated += regionAllocatedBytes(chunk.actualDeflated());
			long withSettingsRegion = regionAllocatedBytes(chunk.withSettingsDeflated());
			long withoutSettingsRegion = regionAllocatedBytes(chunk.withoutSettingsDeflated());
			normalizedWithSettingsRegionAllocated += withSettingsRegion;
			normalizedWithoutSettingsRegionAllocated += withoutSettingsRegion;
			settingsSectorBoundaryCrossings += withSettingsRegion == withoutSettingsRegion ? 0 : 1;
			if (chunk.flowGrid() != null) {
				riverChunks++;
				settingsTags += chunk.hasSettings() ? 1 : 0;
				flowPayloadBodyBytes += chunk.payloadBodyBytes();
				flowPayloadDeflatedBytes += chunk.payloadDeflatedBytes();
				flowPacketBytes += chunk.packetBytes();
				flowWireBytes += chunk.wireBytes();
				payloadDeflated.add(chunk.payloadDeflatedBytes());
				digest.update(ByteBuffer.allocate(8).putInt(chunk.x()).putInt(chunk.z()).array());
				digest.update(chunk.flowGrid());
			}
		}

		JsonObject data = new JsonObject();
		data.addProperty("authority", "chunk-serializer-storage-network");
		data.addProperty("observed_chunks", chunks.size());
		data.addProperty("river_chunks", riverChunks);
		data.addProperty("chunks_with_flow_settings_nbt", settingsTags);
		data.addProperty("flow_grid_sha256", HexFormat.of().formatHex(digest.digest()));
		JsonObject storage = new JsonObject();
		storage.addProperty("actual_full_nbt_uncompressed_bytes", actualUncompressed);
		storage.addProperty("actual_full_nbt_deflated_bytes", actualDeflated);
		storage.addProperty("normalized_with_settings_uncompressed_bytes", normalizedWithSettingsUncompressed);
		storage.addProperty("normalized_with_settings_deflated_bytes", normalizedWithSettingsDeflated);
		storage.addProperty("normalized_without_settings_uncompressed_bytes", normalizedWithoutSettingsUncompressed);
		storage.addProperty("normalized_without_settings_deflated_bytes", normalizedWithoutSettingsDeflated);
		storage.addProperty("actual_region_allocated_bytes", actualRegionAllocated);
		storage.addProperty("normalized_with_settings_region_allocated_bytes", normalizedWithSettingsRegionAllocated);
		storage.addProperty("normalized_without_settings_region_allocated_bytes", normalizedWithoutSettingsRegionAllocated);
		storage.addProperty(
			"settings_uncompressed_delta_bytes",
			normalizedWithSettingsUncompressed - normalizedWithoutSettingsUncompressed
		);
		storage.addProperty(
			"settings_deflated_delta_bytes",
			normalizedWithSettingsDeflated - normalizedWithoutSettingsDeflated
		);
		storage.addProperty(
			"settings_region_allocated_delta_bytes",
			normalizedWithSettingsRegionAllocated - normalizedWithoutSettingsRegionAllocated
		);
		storage.addProperty("settings_sector_boundary_crossing_chunks", settingsSectorBoundaryCrossings);
		data.add("storage", storage);

		EncodedPayload settingsPayload = settingsPayload(registryAccess);
		JsonObject network = new JsonObject();
		network.addProperty("flow_payload_body_bytes", flowPayloadBodyBytes);
		network.addProperty("flow_payload_deflated_body_bytes", flowPayloadDeflatedBytes);
		network.addProperty("flow_packet_bytes", flowPacketBytes);
		network.addProperty("flow_wire_bytes_threshold_256", flowWireBytes);
		network.addProperty("settings_payload_body_bytes", settingsPayload.bodyBytes());
		network.addProperty("settings_packet_bytes", settingsPayload.packetBytes());
		network.addProperty("settings_wire_bytes_threshold_256", settingsPayload.wireBytes());
		network.add("flow_payload_deflated_distribution", distribution(payloadDeflated));
		data.add("network", network);
		data.addProperty("capture_errors", ERRORS.get());
		return new Report(data, chunks.size(), ERRORS.get());
	}

	private static ChunkMetrics measure(ChunkPos pos, CompoundTag source, RegistryAccess registries) throws Exception {
		CompoundTag actual = source.copy();
		int actualUncompressed = uncompressedSize(actual);
		int actualDeflated = deflatedSize(actual);
		boolean hasFlow = actual.contains(FLOW_FIELD_KEY);
		boolean hasSettings = actual.contains(FLOW_SETTINGS_KEY);
		int withSettingsUncompressed = actualUncompressed;
		int withSettingsDeflated = actualDeflated;
		int withoutSettingsUncompressed = actualUncompressed;
		int withoutSettingsDeflated = actualDeflated;
		byte[] flowGrid = null;
		int payloadBodyBytes = 0;
		int payloadDeflatedBytes = 0;
		int packetBytes = 0;
		int wireBytes = 0;
		if (hasFlow) {
			flowGrid = actual.getByteArray(FLOW_FIELD_KEY);
			CompoundTag counterfactual = actual.copy();
			if (hasSettings) {
				counterfactual.remove(FLOW_SETTINGS_KEY);
				withoutSettingsUncompressed = uncompressedSize(counterfactual);
				withoutSettingsDeflated = deflatedSize(counterfactual);
			} else {
				counterfactual.putByte(FLOW_SETTINGS_KEY, ENABLED_SETTINGS);
				withSettingsUncompressed = uncompressedSize(counterfactual);
				withSettingsDeflated = deflatedSize(counterfactual);
			}
			EncodedPayload payload = encodeFlowPayload(
				pos,
				flowGrid,
				hasSettings ? actual.getByte(FLOW_SETTINGS_KEY) : ENABLED_SETTINGS,
				registries
			);
			payloadBodyBytes = payload.bodyBytes();
			payloadDeflatedBytes = payload.deflatedBodyBytes();
			packetBytes = payload.packetBytes();
			wireBytes = payload.wireBytes();
		}
		return new ChunkMetrics(
			pos.x,
			pos.z,
			actualUncompressed,
			actualDeflated,
			withSettingsUncompressed,
			withSettingsDeflated,
			withoutSettingsUncompressed,
			withoutSettingsDeflated,
			hasSettings,
			flowGrid,
			payloadBodyBytes,
			payloadDeflatedBytes,
			packetBytes,
			wireBytes
		);
	}

	@SuppressWarnings({"rawtypes", "unchecked"})
	private static EncodedPayload encodeFlowPayload(
		ChunkPos pos,
		byte[] flowGrid,
		byte settings,
		RegistryAccess registries
	) throws Exception {
		Class<?> payloadType = Class.forName("etcodehome.freeterraforged.network.FlowFieldSyncPayload");
		Constructor<?> constructor = Arrays.stream(payloadType.getConstructors())
			.filter(value -> value.getParameterCount() == 2 || value.getParameterCount() == 3)
			.findFirst()
			.orElseThrow();
		Object payload = constructor.getParameterCount() == 3
			? constructor.newInstance(pos, flowGrid.clone(), settings)
			: constructor.newInstance(pos, flowGrid.clone());
		Field codecField = payloadType.getField("CODEC");
		StreamCodec codec = (StreamCodec) codecField.get(null);
		FriendlyByteBuf buffer = new FriendlyByteBuf(Unpooled.buffer());
		byte[] body;
		try {
			codec.encode(buffer, payload);
			body = ByteBufUtil.getBytes(buffer, buffer.readerIndex(), buffer.readableBytes(), false);
		} finally {
			buffer.release();
		}
		return encodedPayload((CustomPacketPayload) payload, body, registries);
	}

	@SuppressWarnings({"rawtypes", "unchecked"})
	private static EncodedPayload settingsPayload(RegistryAccess registries) {
		try {
			Class<?> payloadType = Class.forName("etcodehome.freeterraforged.network.FlowSettingsSyncPayload");
			Constructor<?> payloadConstructor = payloadType.getConstructors()[0];
			Class<?> snapshotType = payloadConstructor.getParameterTypes()[0];
			Object snapshot = snapshotType.getConstructor(boolean.class, boolean.class, boolean.class)
				.newInstance(true, true, true);
			Object payload = payloadConstructor.newInstance(snapshot);
			StreamCodec codec = (StreamCodec) payloadType.getField("CODEC").get(null);
			FriendlyByteBuf buffer = new FriendlyByteBuf(Unpooled.buffer());
			byte[] body;
			try {
				codec.encode(buffer, payload);
				body = ByteBufUtil.getBytes(buffer, buffer.readerIndex(), buffer.readableBytes(), false);
			} finally {
				buffer.release();
			}
			return encodedPayload((CustomPacketPayload) payload, body, registries);
		} catch (ClassNotFoundException absent) {
			return EncodedPayload.EMPTY;
		} catch (Exception error) {
			ERRORS.incrementAndGet();
			return EncodedPayload.ERROR;
		}
	}

	private static EncodedPayload encodedPayload(
		CustomPacketPayload payload,
		byte[] body,
		RegistryAccess registries
	) throws IOException {
		if (registries == null) {
			throw new IllegalStateException("registry access was not captured");
		}
		var protocol = GameProtocols.CLIENTBOUND_TEMPLATE.bind(RegistryFriendlyByteBuf.decorator(registries));
		var packet = new ClientboundCustomPayloadPacket(payload);
		var buffer = Unpooled.buffer();
		byte[] encodedPacket;
		try {
			protocol.codec().encode(buffer, packet);
			encodedPacket = ByteBufUtil.getBytes(buffer, buffer.readerIndex(), buffer.readableBytes(), false);
		} finally {
			buffer.release();
		}
		return new EncodedPayload(
			body.length,
			deflatedSize(body),
			encodedPacket.length,
			wireSize(encodedPacket, NETWORK_COMPRESSION_THRESHOLD)
		);
	}

	private static int wireSize(byte[] packet, int threshold) throws IOException {
		ByteArrayOutputStream framedPayload = new ByteArrayOutputStream();
		if (packet.length >= threshold) {
			writeVarInt(framedPayload, packet.length);
			try (DeflaterOutputStream compressed = new DeflaterOutputStream(framedPayload)) {
				compressed.write(packet);
			}
		} else {
			writeVarInt(framedPayload, 0);
			framedPayload.write(packet);
		}
		return varIntSize(framedPayload.size()) + framedPayload.size();
	}

	private static void writeVarInt(ByteArrayOutputStream output, int value) {
		while ((value & -128) != 0) {
			output.write(value & 127 | 128);
			value >>>= 7;
		}
		output.write(value);
	}

	private static int varIntSize(int value) {
		int size = 1;
		while ((value & -128) != 0) {
			size++;
			value >>>= 7;
		}
		return size;
	}

	private static long regionAllocatedBytes(int deflatedBytes) {
		long recordBytes = (long) deflatedBytes + REGION_CHUNK_HEADER_BYTES;
		return ((recordBytes + REGION_SECTOR_BYTES - 1) / REGION_SECTOR_BYTES) * REGION_SECTOR_BYTES;
	}

	private static int uncompressedSize(CompoundTag tag) throws IOException {
		ByteArrayOutputStream bytes = new ByteArrayOutputStream();
		NbtIo.write(tag, new DataOutputStream(bytes));
		return bytes.size();
	}

	private static int deflatedSize(CompoundTag tag) throws IOException {
		ByteArrayOutputStream bytes = new ByteArrayOutputStream();
		try (DataOutputStream output = new DataOutputStream(new DeflaterOutputStream(bytes))) {
			NbtIo.write(tag, output);
		}
		return bytes.size();
	}

	private static int deflatedSize(byte[] value) throws IOException {
		ByteArrayOutputStream bytes = new ByteArrayOutputStream();
		try (DeflaterOutputStream output = new DeflaterOutputStream(bytes)) {
			output.write(value);
		}
		return bytes.size();
	}

	private static JsonObject distribution(List<Integer> values) {
		JsonObject result = new JsonObject();
		JsonArray observations = new JsonArray();
		values.forEach(observations::add);
		result.add("observations", observations);
		if (!values.isEmpty()) {
			List<Integer> ordered = values.stream().sorted().toList();
			result.addProperty("min", ordered.getFirst());
			result.addProperty("median", ordered.get(ordered.size() / 2));
			result.addProperty("max", ordered.getLast());
		}
		return result;
	}

	private static MessageDigest sha256() {
		try {
			return MessageDigest.getInstance("SHA-256");
		} catch (NoSuchAlgorithmException error) {
			throw new IllegalStateException(error);
		}
	}

	private static List<Window> parseWindows(JsonObject config) {
		if (!config.has("windows") || !config.get("windows").isJsonArray()) {
			throw new IllegalArgumentException("windows must be an array of inclusive chunk bounds");
		}
		List<Window> parsed = new ArrayList<>();
		for (var element : config.getAsJsonArray("windows")) {
			JsonArray bounds = element.getAsJsonArray();
			if (bounds.size() != 4) {
				throw new IllegalArgumentException("each window must contain four chunk coordinates");
			}
			Window window = new Window(
				bounds.get(0).getAsInt(),
				bounds.get(1).getAsInt(),
				bounds.get(2).getAsInt(),
				bounds.get(3).getAsInt()
			);
			if (window.maxX() < window.minX() || window.maxZ() < window.minZ()) {
				throw new IllegalArgumentException("window maxima must not precede minima");
			}
			parsed.add(window);
		}
		if (parsed.isEmpty()) {
			throw new IllegalArgumentException("at least one window is required");
		}
		return List.copyOf(parsed);
	}

	public record Report(JsonObject data, int observedChunks, int errors) {
	}

	private record Window(int minX, int minZ, int maxX, int maxZ) {
		private boolean contains(int x, int z) {
			return x >= this.minX && x <= this.maxX && z >= this.minZ && z <= this.maxZ;
		}

		private int chunks() {
			return (this.maxX - this.minX + 1) * (this.maxZ - this.minZ + 1);
		}
	}

	private record ChunkMetrics(
		int x,
		int z,
		int actualUncompressed,
		int actualDeflated,
		int withSettingsUncompressed,
		int withSettingsDeflated,
		int withoutSettingsUncompressed,
		int withoutSettingsDeflated,
		boolean hasSettings,
		byte[] flowGrid,
		int payloadBodyBytes,
		int payloadDeflatedBytes,
		int packetBytes,
		int wireBytes
	) {
	}

	private record EncodedPayload(int bodyBytes, int deflatedBodyBytes, int packetBytes, int wireBytes) {
		private static final EncodedPayload EMPTY = new EncodedPayload(0, 0, 0, 0);
		private static final EncodedPayload ERROR = new EncodedPayload(-1, -1, -1, -1);
	}
}
