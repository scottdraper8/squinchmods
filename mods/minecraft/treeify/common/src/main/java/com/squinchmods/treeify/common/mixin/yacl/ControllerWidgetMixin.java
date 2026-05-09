package com.squinchmods.treeify.common.mixin.yacl;

import com.llamalad7.mixinextras.injector.wrapmethod.WrapMethod;
import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import dev.isxander.yacl3.api.Controller;
import dev.isxander.yacl3.api.utils.Dimension;
import dev.isxander.yacl3.gui.YACLScreen;
import dev.isxander.yacl3.gui.controllers.ControllerWidget;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Make search also work with descriptions
 */
@Mixin(value = ControllerWidget.class, remap = false)
public abstract class ControllerWidgetMixin
{
	@Unique
	protected String treeify$optionNameString = "";

	@Unique
	protected String treeify$optionDescriptionString = "";

	@Inject(method = "<init>", at = @At("TAIL"))
	public void treeify$init(Controller control, YACLScreen screen, Dimension dim, CallbackInfo ci) {
		this.treeify$optionNameString = control.option().name().getString().toLowerCase();
		this.treeify$optionDescriptionString = control.option().description().text().getString().toLowerCase();
	}

	@WrapMethod(
		method = "matchesSearch"
	)
	public boolean treeify$matchesSearch(String query, Operation<Boolean> original) {
		if (original.call(query)) {
			return true;
		}

		if (this.treeify$optionNameString == "" || this.treeify$optionDescriptionString == "") {
			return true;
		}

		return this.treeify$optionDescriptionString.contains(query.toLowerCase());
	}
}
