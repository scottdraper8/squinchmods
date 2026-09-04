package org.squinchmods.investigate.rtf.client.mixin;

import net.minecraft.server.MinecraftServer;
import org.squinchmods.investigate.rtf.client.WorldLifecycleProbe;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(MinecraftServer.class)
public abstract class MixinMinecraftServer {
	@Inject(method = "stopServer", at = @At("HEAD"))
	private void squinch$saveStarted(CallbackInfo callback) {
		WorldLifecycleProbe.saveStarted();
	}

	@Inject(method = "stopServer", at = @At("TAIL"))
	private void squinch$saveFinished(CallbackInfo callback) {
		WorldLifecycleProbe.saveFinished();
	}
}
