package com.squinchmods.treeify.common.treeify.ui.control;

import com.squinchmods.treeify.common.treeify.ui.service.BiomeChoiceProvider;
import dev.isxander.yacl3.api.Controller;
import dev.isxander.yacl3.api.Option;
import dev.isxander.yacl3.impl.controller.AbstractControllerBuilderImpl;
import org.apache.commons.lang3.Validate;

public final class TreeifyBiomeControllerBuilder extends AbstractControllerBuilderImpl<String>
{
	private final BiomeChoiceProvider choiceProvider;

	private TreeifyBiomeControllerBuilder(Option<String> option, BiomeChoiceProvider choiceProvider) {
		super(option);
		this.choiceProvider = Validate.notNull(choiceProvider, "`choiceProvider` cannot be null");
	}

	@Override
	public Controller<String> build() {
		return new TreeifyBiomeController(this.option, this.choiceProvider);
	}

	public static TreeifyBiomeControllerBuilder create(Option<String> option, BiomeChoiceProvider choiceProvider) {
		return new TreeifyBiomeControllerBuilder(option, choiceProvider);
	}
}
