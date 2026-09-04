package org.squinchmods.investigate.rtf.client.mixin;

import java.util.concurrent.atomic.AtomicBoolean;

import it.unimi.dsi.fastutil.booleans.BooleanConsumer;
import net.minecraft.client.gui.screens.ConfirmScreen;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ConfirmScreen.class)
public abstract class MixinConfirmScreen {
	private static final AtomicBoolean SQUINCH_CONFIRMED = new AtomicBoolean();

	@Shadow
	@Final
	protected BooleanConsumer callback;

	@Inject(method = "init", at = @At("TAIL"))
	private void squinch$confirmWorldCreationWarning(CallbackInfo callbackInfo) {
		if (System.getenv("SQUINCH_CLIENT_WORLD_RESULT") != null
			&& SQUINCH_CONFIRMED.compareAndSet(false, true)) {
			this.callback.accept(true);
		}
	}
}
