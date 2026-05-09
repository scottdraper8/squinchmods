package com.squinchmods.treeify.fabric;

import com.squinchmods.treeify.common.TreeifyClient;
import net.fabricmc.api.ClientModInitializer;

public final class TreeifyFabricClient implements ClientModInitializer
{
	@Override
	public void onInitializeClient() {
		TreeifyClient.init();
	}
}
