package com.squinchmods.treeify.common.treeify.ui.option;

import com.squinchmods.treeify.common.api.TreeifyOption;
import dev.isxander.yacl3.api.LabelOption;
import net.minecraft.network.chat.Component;

public final class TreeifyLabelOptions
{
	private static final Component EMPTY_LABEL_CONTENT = Component.literal("\n");

	private TreeifyLabelOptions() {
	}

	public static LabelOption spacer() {
		return namedSpacer(Component.empty());
	}

	public static LabelOption namedSpacer(Component name) {
		LabelOption option = LabelOption.create(EMPTY_LABEL_CONTENT);

		if (option instanceof TreeifyOption namedOption) {
			namedOption.treeify$setName(name);
		}

		return option;
	}
}
