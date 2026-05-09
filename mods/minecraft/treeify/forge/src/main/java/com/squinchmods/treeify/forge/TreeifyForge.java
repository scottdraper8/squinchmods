package com.squinchmods.treeify.forge;

import com.squinchmods.treeify.common.Treeify;
import com.squinchmods.treeify.common.registry.TreeifyRegistryManagerProvider;
import com.squinchmods.treeify.forge.treeify.worldgen.TreeifyForgeWorldgen;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.TagsUpdatedEvent;
import net.minecraftforge.event.server.ServerAboutToStartEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import net.minecraftforge.fml.loading.FMLEnvironment;

@Mod(Treeify.MOD_ID)
public final class TreeifyForge
{
	public TreeifyForge() {
		IEventBus modEventBus = FMLJavaModLoadingContext.get().getModEventBus();
		IEventBus eventBus = MinecraftForge.EVENT_BUS;

		Treeify.init();
		TreeifyForgeWorldgen.register(modEventBus);

		if (FMLEnvironment.dist == Dist.CLIENT) {
			TreeifyForgeClient.init(modEventBus, eventBus);
		}

		eventBus.addListener(EventPriority.LOWEST, TreeifyForge::onResourceManagerReload);
		eventBus.addListener(EventPriority.LOWEST, TreeifyForge::onServerAboutToStart);
	}

	private static void onResourceManagerReload(TagsUpdatedEvent event) {
		if (event.getUpdateCause() == TagsUpdatedEvent.UpdateCause.CLIENT_PACKET_RECEIVED) {
			return;
		}

		TreeifyRegistryManagerProvider.setRegistryManager(event.getRegistryAccess());
	}

	private static void onServerAboutToStart(ServerAboutToStartEvent event) {
		TreeifyRegistryManagerProvider.setRegistryManager(event.getServer().registryAccess());
	}
}
