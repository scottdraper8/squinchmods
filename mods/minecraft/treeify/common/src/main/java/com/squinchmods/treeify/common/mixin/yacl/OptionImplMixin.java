package com.squinchmods.treeify.common.mixin.yacl;

import com.squinchmods.treeify.common.api.TreeifyOption;
import dev.isxander.yacl3.impl.OptionImpl;
import net.minecraft.network.chat.Component;
import org.spongepowered.asm.mixin.*;


@Mixin(value = OptionImpl.class, remap = false)
public abstract class OptionImplMixin implements TreeifyOption
{
	@Mutable
	@Final
	@Shadow
	private Component name;

	@Unique
	public void treeify$setName(Component name) {
		this.name = name;
	}
}
