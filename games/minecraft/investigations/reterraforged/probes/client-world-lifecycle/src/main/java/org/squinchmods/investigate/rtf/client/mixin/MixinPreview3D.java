package org.squinchmods.investigate.rtf.client.mixin;

import org.squinchmods.investigate.rtf.client.WorldLifecycleProbe;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import raccoonman.reterraforged.client.gui.screen.presetconfig.IPreviewHandler;
import raccoonman.reterraforged.client.gui.screen.presetconfig.PresetEditorPage;
import raccoonman.reterraforged.client.gui.screen.presetconfig.Preview3D;

@Mixin(value = Preview3D.class, remap = false)
public abstract class MixinPreview3D {
	@Inject(method = "<init>", at = @At("TAIL"))
	private void squinch$register(PresetEditorPage page, int x, int y, int width, int height, CallbackInfo callback) {
		WorldLifecycleProbe.registerPreview("3d", (IPreviewHandler) (Object) this);
	}

	@Inject(method = "applyGeneratedFrame", at = @At("TAIL"))
	private void squinch$observeFrame(IPreviewHandler.FrameResult result, CallbackInfo callback) {
		WorldLifecycleProbe.frameApplied("3d", (IPreviewHandler) (Object) this, result);
	}
}
