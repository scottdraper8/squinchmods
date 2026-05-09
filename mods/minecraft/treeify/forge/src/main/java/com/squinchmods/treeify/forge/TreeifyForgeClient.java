package com.squinchmods.treeify.forge;

import com.squinchmods.treeify.common.TreeifyClient;
import net.minecraftforge.client.ConfigScreenHandler;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.fml.ModLoadingContext;

public final class TreeifyForgeClient
{
	public static void init(IEventBus modEventBus, IEventBus eventBus) {
		TreeifyClient.init();

		ModLoadingContext.get().registerExtensionPoint(ConfigScreenHandler.ConfigScreenFactory.class, () -> 
			new ConfigScreenHandler.ConfigScreenFactory((mc, parent) -> TreeifyClient.getConfigScreen(parent))
		);

		eventBus.addListener(TreeifyForgeClient::onRenderLevelStage);
	}

	private static void onRenderLevelStage(RenderLevelStageEvent event) {
	}
}
