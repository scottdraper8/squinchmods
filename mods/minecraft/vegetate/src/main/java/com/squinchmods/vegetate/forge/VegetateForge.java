package com.squinchmods.vegetate.forge;

import com.squinchmods.vegetate.common.Vegetate;
import com.squinchmods.vegetate.common.registry.VegetateRegistryManagerProvider;
import com.squinchmods.vegetate.forge.vegetate.worldgen.VegetateForgeWorldgen;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.TagsUpdatedEvent;
import net.minecraftforge.event.server.ServerAboutToStartEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.fml.ModLoadingContext;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import net.minecraftforge.fml.loading.FMLEnvironment;

@Mod(Vegetate.MOD_ID)
public final class VegetateForge
{
	// Forge 47.x (1.20.1) does not support constructor injection; these deprecated
	// static accessors are the only available path on this version.
	@SuppressWarnings("removal")
	public VegetateForge() {
		IEventBus modEventBus = FMLJavaModLoadingContext.get().getModEventBus();
		IEventBus eventBus = MinecraftForge.EVENT_BUS;

		Vegetate.init();
		VegetateForgeWorldgen.register(modEventBus);

		if (FMLEnvironment.dist == Dist.CLIENT) {
			VegetateForgeClient.init(modEventBus, eventBus);
		}

		eventBus.addListener(EventPriority.LOWEST, VegetateForge::onResourceManagerReload);
		eventBus.addListener(EventPriority.LOWEST, VegetateForge::onServerAboutToStart);
	}

	private static void onResourceManagerReload(TagsUpdatedEvent event) {
		if (event.getUpdateCause() == TagsUpdatedEvent.UpdateCause.CLIENT_PACKET_RECEIVED) {
			return;
		}

		VegetateRegistryManagerProvider.setRegistryManager(event.getRegistryAccess());
	}

	private static void onServerAboutToStart(ServerAboutToStartEvent event) {
		VegetateRegistryManagerProvider.setRegistryManager(event.getServer().registryAccess());
	}
}
