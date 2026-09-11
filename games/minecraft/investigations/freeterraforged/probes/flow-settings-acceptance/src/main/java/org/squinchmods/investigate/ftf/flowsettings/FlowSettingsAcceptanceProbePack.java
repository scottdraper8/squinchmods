package org.squinchmods.investigate.ftf.flowsettings;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.lang.reflect.Method;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.authlib.GameProfile;
import io.netty.channel.embedded.EmbeddedChannel;
import net.minecraft.network.Connection;
import net.minecraft.network.protocol.PacketFlow;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ClientInformation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.CommonListenerCookie;
import net.minecraft.world.level.Level;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import etcodehome.freeterraforged.world.worldgen.FlowSettingsSnapshot;
import etcodehome.freeterraforged.world.worldgen.IFlowSettingsHolder;
import etcodehome.freeterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;
import etcodehome.freeterraforged.network.FlowSettingsSyncPayload;

public final class FlowSettingsAcceptanceProbePack implements ProbePack {
	private static Map<String, Snapshot> baseline;

	@Override
	public void register() {
		ProbeRegistry.register("squinch:ftf-flow-settings-acceptance", "1", Acceptance::new);
	}

	private static final class Acceptance implements ProbeExecution {
		private final int expectedOverworld;

		private Acceptance(ProbeRequest request) {
			this.expectedOverworld = request.config().get("expected_overworld_settings").getAsInt();
		}

		@Override
		public ProbeResult tick(MinecraftServer server) {
			JsonObject data = new JsonObject();
			try {
				Map<String, Snapshot> current = snapshots(server, data);
				validateInitialOwnership(server, current, this.expectedOverworld);
				if (baseline == null) {
					baseline = current;
					data.addProperty("stage", "armed-before-reload");
					return ProbeResult.complete(TerminalState.PASS, ProbePhase.FINISHED_CHUNK, data, current.size());
				}

				validateReload(current, baseline);
				data.addProperty("reload_preserved_snapshot_identity", true);
				data.add("captured_sync_settings", exercisePlayerSync(server));
				data.addProperty("stage", "accepted-after-reload");
				baseline = null;
				return ProbeResult.complete(TerminalState.PASS, ProbePhase.FINISHED_CHUNK, data, current.size());
			} catch (Throwable error) {
				baseline = null;
				data.addProperty("error", error.toString());
				return ProbeResult.complete(TerminalState.FAIL, ProbePhase.FINISHED_CHUNK, data, 0);
			}
		}
	}

	private static Map<String, Snapshot> snapshots(MinecraftServer server, JsonObject data) {
		Map<String, Snapshot> values = new LinkedHashMap<>();
		JsonArray levels = new JsonArray();
		for (ServerLevel level : server.getAllLevels()) {
			FlowSettingsSnapshot settings = ((IFlowSettingsHolder) level).freeterraforged$getFlowSettings();
			boolean ftf = level.getChunkSource().getGenerator() instanceof TerraForgedChunkGenerator;
			String dimension = level.dimension().location().toString();
			values.put(dimension, new Snapshot(settings, ftf));
			JsonObject entry = new JsonObject();
			entry.addProperty("dimension", dimension);
			entry.addProperty("ftf", ftf);
			entry.addProperty("settings", settings.encode());
			levels.add(entry);
		}
		data.add("levels", levels);
		return Map.copyOf(values);
	}

	private static void validateInitialOwnership(
		MinecraftServer server,
		Map<String, Snapshot> values,
		int expectedOverworld
	) {
		ServerLevel overworld = requireLevel(server, Level.OVERWORLD);
		Snapshot overworldSnapshot = values.get(overworld.dimension().location().toString());
		if (overworldSnapshot == null || !overworldSnapshot.ftf()) {
			throw new IllegalStateException("overworld is not owned by the FTF generator root");
		}
		if (Byte.toUnsignedInt(overworldSnapshot.settings().encode()) != expectedOverworld) {
			throw new IllegalStateException("unexpected overworld flow settings: " + overworldSnapshot.settings().encode());
		}
		for (Map.Entry<String, Snapshot> entry : values.entrySet()) {
			if (!entry.getValue().ftf() && entry.getValue().settings().encode() != 0) {
				throw new IllegalStateException("non-FTF level has enabled settings: " + entry.getKey());
			}
		}
	}

	private static void validateReload(Map<String, Snapshot> current, Map<String, Snapshot> before) {
		if (!current.keySet().equals(before.keySet())) {
			throw new IllegalStateException("dimension set changed across reload");
		}
		for (String dimension : current.keySet()) {
			Snapshot after = current.get(dimension);
			Snapshot original = before.get(dimension);
			if (after.settings() != original.settings() || after.ftf() != original.ftf()) {
				throw new IllegalStateException("flow settings ownership changed across reload for " + dimension);
			}
		}
	}

	private static JsonArray exercisePlayerSync(MinecraftServer server) {
		ServerLevel overworld = requireLevel(server, Level.OVERWORLD);
		ServerLevel nether = requireLevel(server, Level.NETHER);
		IFlowSettingsHolder overworldHolder = (IFlowSettingsHolder) overworld;
		IFlowSettingsHolder netherHolder = (IFlowSettingsHolder) nether;
		FlowSettingsSnapshot overworldOriginal = overworldHolder.freeterraforged$getFlowSettings();
		FlowSettingsSnapshot netherOriginal = netherHolder.freeterraforged$getFlowSettings();
		FlowSettingsSnapshot overworldChanged = FlowSettingsSnapshot.decode((byte) (overworldOriginal.encode() ^ 1));
		FlowSettingsSnapshot netherChanged = FlowSettingsSnapshot.decode((byte) (netherOriginal.encode() ^ 2));
		GameProfile profile = new GameProfile(UUID.randomUUID(), "squinch-flow-settings");
		CommonListenerCookie cookie = CommonListenerCookie.createInitial(profile, false);
		ServerPlayer player = new ServerPlayer(server, overworld, profile, cookie.clientInformation());
		Connection connection = new Connection(PacketFlow.SERVERBOUND);
		EmbeddedChannel channel = new EmbeddedChannel(connection);
		advertiseNeoForgeChannelIfPresent(connection);
		boolean placed = false;
		try {
			server.getPlayerList().placeNewPlayer(connection, player, cookie);
			placed = true;
			FlowSettingsAcceptanceTelemetry.arm(player.getUUID());
			player.connection.chunkSender.sendNextChunks(player);
			player.connection.chunkSender.sendNextChunks(player);
			overworldHolder.freeterraforged$setFlowSettings(overworldChanged);
			player.connection.chunkSender.sendNextChunks(player);
			player.connection.chunkSender.sendNextChunks(player);
			overworldHolder.freeterraforged$setFlowSettings(overworldOriginal);
			player.connection.chunkSender.sendNextChunks(player);

			player.setServerLevel(nether);
			player.connection.chunkSender.sendNextChunks(player);
			player.connection.chunkSender.sendNextChunks(player);
			netherHolder.freeterraforged$setFlowSettings(netherChanged);
			if (overworldHolder.freeterraforged$getFlowSettings() != overworldOriginal) {
				throw new IllegalStateException("mutating nether settings changed overworld ownership");
			}
			player.connection.chunkSender.sendNextChunks(player);
			player.connection.chunkSender.sendNextChunks(player);

			player.setServerLevel(overworld);
			player.connection.chunkSender.sendNextChunks(player);
			player.connection.chunkSender.sendNextChunks(player);

			List<Byte> actual = FlowSettingsAcceptanceTelemetry.finish();
			List<Byte> expected = new ArrayList<>();
			if (overworldOriginal.encode() != 0) {
				expected.add(overworldOriginal.encode());
			}
			expected.add(overworldChanged.encode());
			expected.add(overworldOriginal.encode());
			if (netherOriginal.encode() != 0 || overworldOriginal.encode() > 0) {
				expected.add(netherOriginal.encode());
			}
			expected.add(netherChanged.encode());
			expected.add(overworldOriginal.encode());
			if (!actual.equals(expected)) {
				throw new IllegalStateException("unexpected settings synchronization sequence: " + actual + " expected " + expected);
			}
			JsonArray result = new JsonArray();
			actual.forEach(result::add);
			return result;
		} finally {
			FlowSettingsAcceptanceTelemetry.finish();
			overworldHolder.freeterraforged$setFlowSettings(overworldOriginal);
			netherHolder.freeterraforged$setFlowSettings(netherOriginal);
			player.setServerLevel(overworld);
			if (placed) {
				server.getPlayerList().remove(player);
			}
			channel.finishAndReleaseAll();
		}
	}

	@SuppressWarnings("unchecked")
	private static void advertiseNeoForgeChannelIfPresent(Connection connection) {
		try {
			Class<?> attributes = Class.forName(
				"net.neoforged.neoforge.network.registration.ChannelAttributes",
				false,
				FlowSettingsAcceptanceProbePack.class.getClassLoader()
			);
			Method channels = attributes.getMethod("getOrCreateAdHocChannels", Connection.class);
			((java.util.Set<net.minecraft.resources.ResourceLocation>) channels.invoke(null, connection))
				.add(FlowSettingsSyncPayload.TYPE.id());
		} catch (ClassNotFoundException absentOnFabric) {
			// Fabric does not require a negotiated-channel attribute for this embedded connection.
		} catch (ReflectiveOperationException error) {
			throw new IllegalStateException("Failed to advertise the NeoForge test client channel", error);
		}
	}

	private static ServerLevel requireLevel(MinecraftServer server, net.minecraft.resources.ResourceKey<Level> key) {
		ServerLevel level = server.getLevel(key);
		if (level == null) {
			throw new IllegalStateException("missing level " + key.location());
		}
		return level;
	}

	private record Snapshot(FlowSettingsSnapshot settings, boolean ftf) {
	}
}
