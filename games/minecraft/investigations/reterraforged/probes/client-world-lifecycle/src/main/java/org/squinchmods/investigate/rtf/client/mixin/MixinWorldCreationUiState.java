package org.squinchmods.investigate.rtf.client.mixin;

import net.minecraft.client.gui.screens.worldselection.WorldCreationContext;
import net.minecraft.client.gui.screens.worldselection.WorldCreationUiState;
import org.squinchmods.investigate.rtf.client.WorldLifecycleProbe;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(WorldCreationUiState.class)
public abstract class MixinWorldCreationUiState {
	@Inject(method = "setSettings", at = @At("TAIL"))
	private void squinch$settingsReloaded(WorldCreationContext context, CallbackInfo callback) {
		WorldLifecycleProbe.settingsReloaded();
	}
}
