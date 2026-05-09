package com.squinchmods.treeify.fabric.modcompat;

import com.terraformersmc.modmenu.api.ConfigScreenFactory;
import com.terraformersmc.modmenu.api.ModMenuApi;
import com.squinchmods.treeify.common.TreeifyClient;

public final class ModMenuCompat implements ModMenuApi
{
	@Override
	public ConfigScreenFactory<?> getModConfigScreenFactory() {
		return TreeifyClient::getConfigScreen;
	}
}
