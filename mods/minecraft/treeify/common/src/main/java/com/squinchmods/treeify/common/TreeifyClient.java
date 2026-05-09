package com.squinchmods.treeify.common;

import com.squinchmods.treeify.common.treeify.ui.screen.GlobalSettingsScreen;
import com.squinchmods.treeify.common.treeify.ui.screen.VegetationListScreen;
import com.squinchmods.treeify.common.treeify.ui.service.TreeifyConfigUiCatalogService;
import com.squinchmods.treeify.common.treeify.ui.service.TreeifyConfigUiEditService;
import com.squinchmods.treeify.common.treeify.ui.service.TreeifyConfigUiSaveService;
import com.squinchmods.treeify.common.treeify.ui.state.TreeifyConfigSessionImpl;
import com.squinchmods.treeify.common.treeify.ui.shell.TreeifyConfigScreen;
import com.squinchmods.treeify.common.treeify.ui.shell.TreeifyConfigScreenContext;
import com.squinchmods.treeify.common.treeify.ui.shell.TreeifyConfigTabComposer;
import com.squinchmods.treeify.common.treeify.worldgen.discovery.VegetationWorldgenDataProvider;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;
import org.jetbrains.annotations.Nullable;

import java.util.ArrayList;
import java.util.List;

public final class TreeifyClient
{
	private static TreeifyConfigScreen configScreen;

	public static void init() {
	}

	public static Screen getConfigScreen(Screen parent) {
		var index = VegetationWorldgenDataProvider.discover();
		
		var catalogService = new TreeifyConfigUiCatalogService(Treeify.getConfigService(), index);
		var editService = new TreeifyConfigUiEditService(Treeify.getConfigService(), index);
		var saveService = new TreeifyConfigUiSaveService(Treeify.getConfigService(), editService);
		var session = new TreeifyConfigSessionImpl();

		TreeifyConfigScreenContext[] contextHolder = new TreeifyConfigScreenContext[1];

		TreeifyConfigScreenContext context = new TreeifyConfigScreenContext(
			catalogService,
			editService,
			saveService,
			session,
			route -> {
				var detailScreen = new com.squinchmods.treeify.common.treeify.ui.screen.FeatureDetailScreen(route, contextHolder[0]);
				Minecraft.getInstance().setScreen(detailScreen.generateScreen(configScreen.generateScreen(parent)));
			}
		);
		contextHolder[0] = context;

		List<TreeifyConfigTabComposer> tabs = new ArrayList<>();
		tabs.add(new GlobalSettingsScreen(editService));
		tabs.add(new VegetationListScreen(catalogService, editService));

		configScreen = new TreeifyConfigScreen(context, tabs);
		return configScreen.generateScreen(parent);
	}

	@Nullable
	public static TreeifyConfigScreen getConfigScreen() {
		return configScreen;
	}
}
