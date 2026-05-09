package com.squinchmods.treeify.common.treeify.ui.shell;

import dev.isxander.yacl3.api.ConfigCategory;
import dev.isxander.yacl3.api.LabelOption;
import dev.isxander.yacl3.api.OptionDescription;
import dev.isxander.yacl3.api.OptionGroup;
import dev.isxander.yacl3.api.YetAnotherConfigLib;
import dev.isxander.yacl3.gui.YACLScreen;
import java.util.List;
import java.util.Objects;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;

public final class TreeifyConfigScreen
{
	private final TreeifyConfigScreenContext context;
	private final List<TreeifyConfigTabComposer> tabComposers;

	public TreeifyConfigScreen(
		TreeifyConfigScreenContext context,
		List<TreeifyConfigTabComposer> tabComposers
	) {
		this.context = Objects.requireNonNull(context, "context cannot be null");
		this.tabComposers = List.copyOf(tabComposers);
	}

	public Screen generateScreen(Screen parent) {
		var catalogSnapshot = this.context.catalogService().getCatalogSnapshot();
		var yaclBuilder = YetAnotherConfigLib.createBuilder()
			.title(catalogSnapshot.title())
			.save(() -> this.context.saveService().savePendingChanges());

		if (this.tabComposers.isEmpty()) {
			this.composeEmptyTab(yaclBuilder);
		} else {
			for (var tabComposer : this.tabComposers) {
				tabComposer.compose(yaclBuilder, this.context);
			}
		}

		var yaclScreen = (YACLScreen) yaclBuilder.build().generateScreen(parent);
		this.context.session().loadInto(yaclScreen);

		return yaclScreen;
	}

	public void saveScreenState(YACLScreen screen) {
		this.context.session().saveFrom(screen);
	}

	private void composeEmptyTab(YetAnotherConfigLib.Builder yaclBuilder) {
		var categoryBuilder = ConfigCategory.createBuilder()
			.name(Component.translatable("gui.treeify.config.catalog.title"))
			.tooltip(Component.translatable("gui.treeify.config.catalog.description"));

		var groupBuilder = OptionGroup.createBuilder()
			.name(Component.translatable("gui.treeify.config.catalog.empty.title"))
			.description(OptionDescription.of(Component.translatable("gui.treeify.config.catalog.empty.description")));

		groupBuilder.option(LabelOption.create(Component.translatable("gui.treeify.config.catalog.empty.message")));
		categoryBuilder.group(groupBuilder.build());
		yaclBuilder.category(categoryBuilder.build());
	}
}
