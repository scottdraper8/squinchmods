package com.squinchmods.treeify.common.mixin.yacl;

import com.squinchmods.treeify.common.TreeifyClient;
import dev.isxander.yacl3.gui.YACLScreen;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;


@Mixin(value = YACLScreen.class)
public abstract class YACLScreenMixin extends Screen
{
	protected YACLScreenMixin(Component component) {
		super(component);
	}

	@Inject(
		method = "onClose",
		at = @At("HEAD")
	)
	public void treeify$onCloseHead(CallbackInfo ci) {
		if (this.minecraft != null) {
			if (this.minecraft.screen instanceof YACLScreen yaclsScreen) {
				var configScreen = TreeifyClient.getConfigScreen();

				if (configScreen != null) {
					configScreen.saveScreenState(yaclsScreen);
				}
			}
		}
	}

	@Inject(
		method = "onClose",
		at = @At("TAIL")
	)
	public void treeify$onCloseTail(CallbackInfo ci) {
	}
}
