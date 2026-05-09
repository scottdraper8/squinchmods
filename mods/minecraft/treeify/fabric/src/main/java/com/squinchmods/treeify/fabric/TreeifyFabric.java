package com.squinchmods.treeify.fabric;

import com.squinchmods.treeify.common.Treeify;
import com.squinchmods.treeify.common.registry.TreeifyRegistryManagerProvider;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.CommonLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.minecraft.core.RegistryAccess;
import net.minecraft.server.MinecraftServer;

public final class TreeifyFabric implements ModInitializer
{
	@Override
	public void onInitialize() {
		Treeify.init();

		CommonLifecycleEvents.TAGS_LOADED.register(this::onDatapackReload);
		ServerLifecycleEvents.SERVER_STARTING.register(this::onServerStart);
	}

	private void onDatapackReload(RegistryAccess registryAccess, boolean isClient) {
		if (isClient) {
			return;
		}

		TreeifyRegistryManagerProvider.setRegistryManager(registryAccess);
	}

	private void onServerStart(MinecraftServer minecraftServer) {
		TreeifyRegistryManagerProvider.setRegistryManager(minecraftServer.registryAccess());
	}
}
