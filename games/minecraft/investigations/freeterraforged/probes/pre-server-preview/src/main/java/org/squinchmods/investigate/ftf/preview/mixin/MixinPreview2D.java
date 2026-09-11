package org.squinchmods.investigate.ftf.preview.mixin;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.squinchmods.investigate.ftf.preview.LifecycleProbe;

import etcodehome.freeterraforged.client.gui.screen.presetconfig.IPreviewHandler;
import etcodehome.freeterraforged.client.gui.screen.presetconfig.PresetEditorPage;
import etcodehome.freeterraforged.client.gui.screen.presetconfig.Preview2D;

@Mixin(value = Preview2D.class, remap = false)
public abstract class MixinPreview2D {
	@Inject(method = "<init>", at = @At("TAIL"))
	private void squinch$register(PresetEditorPage page, int x, int y, int width, int height, CallbackInfo callback) {
		LifecycleProbe.registerPreview("2d", (IPreviewHandler) (Object) this);
	}

	@Inject(method = "applyGeneratedFrame", at = @At("TAIL"))
	private void squinch$observeFrame(IPreviewHandler.FrameResult result, CallbackInfo callback) {
		LifecycleProbe.frameApplied("2d", (IPreviewHandler) (Object) this, result);
	}
}
