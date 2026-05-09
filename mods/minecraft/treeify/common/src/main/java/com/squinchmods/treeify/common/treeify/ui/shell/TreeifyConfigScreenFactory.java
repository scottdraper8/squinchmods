package com.squinchmods.treeify.common.treeify.ui.shell;

import java.util.List;
import net.minecraft.client.gui.screens.Screen;

public final class TreeifyConfigScreenFactory
{
	private final TreeifyConfigScreen screen;

	public TreeifyConfigScreenFactory(
		TreeifyConfigScreenContext context,
		List<TreeifyConfigTabComposer> tabComposers
	) {
		this.screen = new TreeifyConfigScreen(context, tabComposers);
	}

	public Screen create(Screen parent) {
		return this.screen.generateScreen(parent);
	}

	public TreeifyConfigScreen screen() {
		return this.screen;
	}
}
