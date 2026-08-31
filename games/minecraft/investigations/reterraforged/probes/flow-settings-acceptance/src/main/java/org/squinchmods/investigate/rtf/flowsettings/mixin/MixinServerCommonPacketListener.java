package org.squinchmods.investigate.rtf.flowsettings.mixin;

import net.minecraft.network.protocol.Packet;
import net.minecraft.server.network.ServerCommonPacketListenerImpl;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import org.squinchmods.investigate.rtf.flowsettings.FlowSettingsAcceptanceTelemetry;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ServerCommonPacketListenerImpl.class)
public abstract class MixinServerCommonPacketListener {
	@Inject(method = "send(Lnet/minecraft/network/protocol/Packet;)V", at = @At("HEAD"))
	private void squinch$captureFlowSettingsPayload(Packet<?> packet, CallbackInfo callback) {
		if ((Object) this instanceof ServerGamePacketListenerImpl listener) {
			FlowSettingsAcceptanceTelemetry.capture(listener.player, packet);
		}
	}
}
