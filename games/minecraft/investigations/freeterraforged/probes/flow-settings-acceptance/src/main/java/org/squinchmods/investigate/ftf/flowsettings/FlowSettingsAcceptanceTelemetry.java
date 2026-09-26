package org.squinchmods.investigate.ftf.flowsettings;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import net.minecraft.network.protocol.Packet;
import net.minecraft.network.protocol.common.ClientboundCustomPayloadPacket;
import net.minecraft.server.level.ServerPlayer;
import etcodehome.freeterraforged.network.FlowSettingsSyncPayload;

public final class FlowSettingsAcceptanceTelemetry {
	private static UUID target;
	private static final List<Byte> SETTINGS = new ArrayList<>();

	private FlowSettingsAcceptanceTelemetry() {
	}

	public static synchronized void arm(UUID player) {
		target = player;
		SETTINGS.clear();
	}

	public static synchronized void capture(ServerPlayer player, Packet<?> packet) {
		if (target == null || !target.equals(player.getUUID())) {
			return;
		}
		if (packet instanceof ClientboundCustomPayloadPacket custom
			&& custom.payload() instanceof FlowSettingsSyncPayload settings) {
			SETTINGS.add(settings.settings().encode());
		}
	}

	public static synchronized List<Byte> finish() {
		List<Byte> result = List.copyOf(SETTINGS);
		target = null;
		SETTINGS.clear();
		return result;
	}
}
