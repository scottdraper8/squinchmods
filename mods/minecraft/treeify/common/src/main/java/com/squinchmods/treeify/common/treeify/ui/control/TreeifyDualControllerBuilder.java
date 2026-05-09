package com.squinchmods.treeify.common.treeify.ui.control;

import com.squinchmods.treeify.common.treeify.ui.option.TreeifyOptionPair;
import dev.isxander.yacl3.api.Controller;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.api.controller.ControllerBuilder;

public final class TreeifyDualControllerBuilder<K extends Option<?>, V extends Option<?>> implements ControllerBuilder<TreeifyOptionPair<K, V>>
{
	private final TreeifyOptionPair<K, V> optionPair;

	private TreeifyDualControllerBuilder(TreeifyOptionPair<K, V> optionPair) {
		this.optionPair = optionPair;
	}

	@Override
	public Controller<TreeifyOptionPair<K, V>> build() {
		return new TreeifyDualController<>(this.optionPair);
	}

	public static <K extends Option<?>, V extends Option<?>> TreeifyDualControllerBuilder<K, V> create(TreeifyOptionPair<K, V> optionPair) {
		return new TreeifyDualControllerBuilder<>(optionPair);
	}
}
