package org.squinchmods.investigate.rtf.preview.mixin;

import java.util.concurrent.atomic.AtomicBoolean;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.TitleScreen;
import net.minecraft.client.gui.screens.worldselection.CreateWorldScreen;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.squinchmods.investigate.rtf.preview.LifecycleProbe;

@Mixin(Minecraft.class)
public abstract class MixinMinecraft {
	private static final AtomicBoolean SQUINCH_OPENED = new AtomicBoolean();

	@Inject(method = "setScreen", at = @At("TAIL"))
	private void squinch$openWorldCreation(Screen screen, CallbackInfo callback) {
		Minecraft minecraft = (Minecraft) (Object) this;
		if (System.getenv("SQUINCH_PRE_SERVER_PREVIEW_RESULT") == null
			|| !(screen instanceof TitleScreen)
			|| !SQUINCH_OPENED.compareAndSet(false, true)) {
			return;
		}
		minecraft.execute(() -> CreateWorldScreen.openFresh(minecraft, screen));
	}

	@Inject(method = "tick", at = @At("TAIL"))
	private void squinch$observeIntegratedLifecycle(CallbackInfo callback) {
		Minecraft minecraft = (Minecraft) (Object) this;
		LifecycleProbe.tick(minecraft);
		CreateWorldScreen pending = LifecycleProbe.takePending();
		if (pending != null) {
			LifecycleProbe.creationRequested();
			((CreateWorldScreenInvoker) pending).squinch$invokeCreate();
		}
	}
}
