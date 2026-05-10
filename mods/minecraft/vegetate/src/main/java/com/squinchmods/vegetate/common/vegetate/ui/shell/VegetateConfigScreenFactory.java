package com.squinchmods.vegetate.common.vegetate.ui.shell;

import net.minecraft.client.gui.screens.Screen;

public final class VegetateConfigScreenFactory
{
	private final VegetateConfigScreen screen;

	public VegetateConfigScreenFactory(VegetateConfigScreenContext context) {
		this.screen = new VegetateConfigScreen(context);
	}

	public Screen create(Screen parent) {
		return this.screen.generateScreen(parent);
	}

	public VegetateConfigScreen screen() {
		return this.screen;
	}
}
