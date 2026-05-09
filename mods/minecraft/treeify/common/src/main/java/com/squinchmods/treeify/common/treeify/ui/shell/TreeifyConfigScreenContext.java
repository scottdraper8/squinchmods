package com.squinchmods.treeify.common.treeify.ui.shell;

import com.squinchmods.treeify.common.treeify.ui.model.ConfigUiDetailRoute;
import com.squinchmods.treeify.common.treeify.ui.service.ConfigUiCatalogService;
import com.squinchmods.treeify.common.treeify.ui.service.ConfigUiEditService;
import com.squinchmods.treeify.common.treeify.ui.service.ConfigUiSaveService;
import com.squinchmods.treeify.common.treeify.ui.service.TreeifyConfigSession;
import java.util.Objects;
import java.util.function.Consumer;

public record TreeifyConfigScreenContext(
	ConfigUiCatalogService catalogService,
	ConfigUiEditService editService,
	ConfigUiSaveService saveService,
	TreeifyConfigSession session,
	Consumer<ConfigUiDetailRoute> detailNavigator
)
{
	public TreeifyConfigScreenContext {
		Objects.requireNonNull(catalogService, "catalogService cannot be null");
		Objects.requireNonNull(editService, "editService cannot be null");
		Objects.requireNonNull(saveService, "saveService cannot be null");
		Objects.requireNonNull(session, "session cannot be null");
		Objects.requireNonNull(detailNavigator, "detailNavigator cannot be null");
	}

	public void openDetail(ConfigUiDetailRoute route) {
		this.detailNavigator.accept(route);
	}
}
