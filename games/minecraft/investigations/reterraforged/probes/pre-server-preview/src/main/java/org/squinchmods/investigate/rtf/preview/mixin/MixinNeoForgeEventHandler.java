package org.squinchmods.investigate.rtf.preview.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Pseudo
@Mixin(targets = "net.neoforged.neoforge.common.NeoForgeEventHandler", remap = false)
public abstract class MixinNeoForgeEventHandler {
	@Inject(method = "onResourceReload", at = @At("HEAD"), remap = false, require = 0)
	private void squinch$reportReloadListenerEvent(CallbackInfo callback) {
		System.err.println("SQUINCH NeoForgeEventHandler received AddReloadListenerEvent");
	}

	@Inject(method = "tagsUpdated", at = @At("HEAD"), remap = false, require = 0)
	private void squinch$reportTagsUpdated(CallbackInfo callback) {
		System.err.println("SQUINCH NeoForgeEventHandler received TagsUpdatedEvent");
	}
}
