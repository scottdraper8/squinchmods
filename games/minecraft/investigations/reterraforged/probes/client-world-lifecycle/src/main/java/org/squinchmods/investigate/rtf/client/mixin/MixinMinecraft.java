package org.squinchmods.investigate.rtf.client.mixin;

import java.util.concurrent.atomic.AtomicBoolean;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.gui.screens.worldselection.CreateWorldScreen;
import org.squinchmods.investigate.rtf.client.WorldLifecycleProbe;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(Minecraft.class)
public abstract class MixinMinecraft {
	private static final AtomicBoolean SQUINCH_OPENED = new AtomicBoolean();
	private static final AtomicBoolean SQUINCH_CRASHED = new AtomicBoolean();

	@Inject(method = "setScreen", at = @At("TAIL"))
	private void squinch$openWorldCreation(Screen screen, CallbackInfo callback) {
		Minecraft minecraft = (Minecraft) (Object) this;
		if (System.getenv("SQUINCH_CLIENT_WORLD_RESULT") == null
			|| !(screen instanceof TitleScreen)
			|| !SQUINCH_OPENED.compareAndSet(false, true)) {
			return;
		}
		minecraft.execute(() -> CreateWorldScreen.openFresh(minecraft, screen));
	}

	@Inject(method = "tick", at = @At("TAIL"))
	private void squinch$observeLifecycle(CallbackInfo callback) {
		if ("crash".equals(System.getenv("SQUINCH_CLIENT_CONTROL"))
			&& SQUINCH_CRASHED.compareAndSet(false, true)) {
			throw new IllegalStateException("controlled client crash");
		}
		Minecraft minecraft = (Minecraft) (Object) this;
		WorldLifecycleProbe.tick(minecraft);
		CreateWorldScreen pending = WorldLifecycleProbe.takePending();
		if (pending != null) {
			WorldLifecycleProbe.creationRequested();
			((CreateWorldScreenInvoker) pending).squinch$invokeCreate();
		}
	}
}
