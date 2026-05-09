package com.squinchmods.treeify.neoforge;

import com.squinchmods.treeify.common.Treeify;
import com.squinchmods.treeify.common.registry.TreeifyRegistryManagerProvider;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.EventPriority;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.ModContainer;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.loading.FMLEnvironment;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.TagsUpdatedEvent;
import net.neoforged.neoforge.event.server.ServerAboutToStartEvent;

@Mod(Treeify.MOD_ID)
public final class TreeifyNeoForge
{
	public TreeifyNeoForge(ModContainer modContainer, IEventBus modEventBus) {
		var eventBus = NeoForge.EVENT_BUS;

		Treeify.init();

		//? if >= 1.21.9 {
		if (FMLEnvironment.getDist() == Dist.CLIENT)
		//?} else {
		/*if (FMLEnvironment.dist == Dist.CLIENT)
		*///?}
		{
			TreeifyNeoForgeClient.init(modEventBus, eventBus);
		}

		eventBus.addListener(EventPriority.LOWEST, TreeifyNeoForge::onResourceManagerReload);
		eventBus.addListener(EventPriority.LOWEST, TreeifyNeoForge::onServerAboutToStart);
	}

	private static void onResourceManagerReload(TagsUpdatedEvent event) {
		if (event.getUpdateCause() == TagsUpdatedEvent.UpdateCause.CLIENT_PACKET_RECEIVED) {
			return;
		}

		//? if >=1.21.3 {
		var registryAccess = event.getLookupProvider();
		TreeifyRegistryManagerProvider.setRegistryManager((net.minecraft.core.RegistryAccess) registryAccess);
		//?} else {
		/*var registryAccess = event.getRegistryAccess();
		TreeifyRegistryManagerProvider.setRegistryManager(registryAccess);
		*///?}
	}

	private static void onServerAboutToStart(ServerAboutToStartEvent event) {
		TreeifyRegistryManagerProvider.setRegistryManager(event.getServer().registryAccess());
	}
}
