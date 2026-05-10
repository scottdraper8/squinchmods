package com.squinchmods.vegetate.forge;

import com.squinchmods.vegetate.common.VegetateClient;
import net.minecraftforge.client.ConfigScreenHandler;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.fml.ModLoadingContext;

public final class VegetateForgeClient
{
	@SuppressWarnings("removal")
	public static void init(IEventBus modEventBus, IEventBus eventBus) {
		VegetateClient.init();

		ModLoadingContext.get().registerExtensionPoint(ConfigScreenHandler.ConfigScreenFactory.class, () ->
			new ConfigScreenHandler.ConfigScreenFactory((mc, parent) -> VegetateClient.getConfigScreen(parent))
		);

		eventBus.addListener(VegetateForgeClient::onRenderLevelStage);
	}

	private static void onRenderLevelStage(RenderLevelStageEvent event) {
	}
}
